/// <reference types="vitest/config" />
import type { IncomingMessage, ServerResponse } from "node:http";

import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

import { handleDataMount } from "./server/dataMount";
import { handleHumanHints } from "./server/humanHints";
import { handleHumanSections } from "./server/humanSections";
import { handleSongFacts } from "./server/songFacts";
import { handleBlockEnergy } from "./server/blockEnergy";
import { handleLyricValidations } from "./server/lyricValidations";
import { handleBlockReviews } from "./server/blockReviews";
import { handleProposalDecision } from "./server/proposalDecision";
import { handleRunRequest } from "./server/runRequest";

// Target: Chrome 151 only (the operator's browser). No cross-browser fallbacks,
// polyfills or autoprefixer — build to esnext and use modern web APIs freely.
//
// The dev-server `/data` static mount + directory listing and the
// `PUT /api/human-hints/<song>` handler below are ported byte-for-byte (in
// behaviour) from the previous app's vite.config.js, plan item 2. The `PUT
// /api/song-facts/<song>` handler is added by plan item 7. The `PUT
// /api/block-energy/<song>` handler (v3.4 item 4) mirrors both: same
// path-escape guard, 400-on-bad-payload, pretty JSON + trailing newline,
// dev-only (production Nginx has no handler — the rating UI is dev-only, like
// the hint editor). The `PUT /api/lyric-validations/<song>` handler (v3.4 item
// 5) mirrors the guard/400/pretty-JSON shape but writes PER-CLICK, not on an
// explicit Save (D5.1) — a rapid token-by-token verification pass. The `PUT
// /api/human-sections/<song>` handler mirrors the human-hints handler exactly
// (explicit Save, same guard/400/pretty-JSON shape) but writes segments.json,
// a bare array (no `{song_name, ...}` wrapper).
//
// The debugger writes exactly six `reference/human/` files: human_hints.json,
// segments.json, song_facts.json, block_energy.json, lyric_validations.json
// and block_reviews.json. Nothing in `src/` or `mcp/` reads any of them. Any
// other write is a new contract — stop and ask.
//
// The `PUT /api/block-reviews/<song>` handler (v3.7 item 1) mirrors
// lyric-validations: per-click, not explicit-Save — each verdict click PUTs
// the FULL `reviews` array (the join key is `(lane_id, start)`, not an
// index) and this handler replaces the file.
//
// v3.7 item 11 adds `PUT /api/proposal-decision/<song>`: flips ONE
// `reference/proposals/pending.json` entry's status by id (never appends —
// only mcp/proposals.py's two MCP tools do that, over stdio, never through
// this server). It does NOT re-run the analyzer stage that republishes the
// human file — a Docker-outside-of-docker trigger was tried and reverted
// (mounting the host's docker socket into this dev container was judged too
// broad a grant for what it bought, and doesn't work on a rootless Docker
// host anyway). The panel shows a reminder naming the `--stage` to run by
// hand, same as any other `reference/human/` edit.
//
// v3.9 item 6 (bugfix): approving used to be two round trips from the
// browser — PUT the human file (via `loadHumanHints`/`saveHumanHints` in the
// panel), THEN PUT this decision — with no locking on either side. Two
// approvals fired close together could both read the SAME stale
// human_hints.json before either write landed, and the later write replaced
// the file wholesale, discarding the earlier approval's hint entirely (lost
// six of nineteen on *Tutta L'Italia*). This handler now does the human-file
// write itself, from its OWN fresh read, inside `withSongLock` — which
// serializes every decision for one song so a later read always sees an
// earlier write — and only flips the proposal to "approved" once that write
// has succeeded, so the two can never diverge. See
// `server/proposalDecisionMerge.ts` for the merge/id logic and its tests.
//
// v3.8 item 2 adds `PUT /api/run-request/<song>`: writes
// `artifacts/_run_request.json` = `{song, requested_at}` — a NEW write
// outside every `reference/human/` file named above. Picked up by the
// host-side `./analysis-watcher` (v3.8 item 1), which runs `./analyze` for
// the song and reports progress to the sibling `artifacts/_run_progress.json`
// (read-only from this server — served by the plain `/data` static mount,
// same as any other artifact). This is the same request file
// `request_analysis` (v3.8 item 3, `mcp/runs.py`) writes over stdio — one
// mechanism, two callers. Neither `_run_*` file is `reference/human/`
// material and neither is a delivery artifact (`docs/mcp-exposes-only-top-
// level-song-json`).
//
// v3.9 item 7 — each endpoint's file-path helper + normalizer + handler now
// lives in its own module under `server/`; this file only registers them.

type Handler = (
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
) => Promise<void>;

const PUT_ENDPOINTS: Array<{ prefix: string; handle: Handler }> = [
  { prefix: "/api/human-hints/", handle: handleHumanHints },
  { prefix: "/api/human-sections/", handle: handleHumanSections },
  { prefix: "/api/song-facts/", handle: handleSongFacts },
  { prefix: "/api/block-energy/", handle: handleBlockEnergy },
  { prefix: "/api/lyric-validations/", handle: handleLyricValidations },
  { prefix: "/api/block-reviews/", handle: handleBlockReviews },
  { prefix: "/api/proposal-decision/", handle: handleProposalDecision },
  { prefix: "/api/run-request/", handle: handleRunRequest },
];

function dataMountPlugin(): Plugin {
  return {
    name: "data-mount-plugin",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const requestUrl = request.url
          ? new URL(request.url, "http://localhost")
          : null;

        if (requestUrl && request.method === "PUT") {
          for (const { prefix, handle } of PUT_ENDPOINTS) {
            if (requestUrl.pathname.startsWith(prefix)) {
              const song = decodeURIComponent(
                requestUrl.pathname.slice(prefix.length),
              );
              await handle(song, request, response);
              return;
            }
          }
        }

        if (!requestUrl || !requestUrl.pathname.startsWith("/data")) {
          next();
          return;
        }

        await handleDataMount(request, response, requestUrl.pathname);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), dataMountPlugin()],
  build: {
    target: "esnext",
  },
  server: {
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    allowedHosts: ["s2.local"],
    watch: {
      usePolling: true,
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    css: true,
  },
});
