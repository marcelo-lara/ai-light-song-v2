// runRequest.ts — `PUT /api/run-request/<song>`, writing
// artifacts/_run_request.json = `{song, requested_at}`. Split out of
// vite.config.ts (v3.9 item 7) with no behaviour change.

import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";

import { analysisRoot, writeJsonFile } from "./shared";
import { validateRunRequestSong } from "./runRequestGuard";

// `artifacts/_run_request.json` — written by this handler and by
// `mcp/runs.py`'s `request_analysis` tool (v3.8 item 3); read by the
// host-side `./analysis-watcher` (v3.8 item 1), which deletes it once a run
// is picked up. Not `reference/human/` material and never a delivery
// artifact.
export function runRequestFilePath(song: unknown): string {
  const safeSong = validateRunRequestSong(song);
  return path.join(analysisRoot, safeSong, "artifacts", "_run_request.json");
}

// v3.8 item 2 — writes artifacts/_run_request.json = {song, requested_at}.
// Never touches artifacts/_run_progress.json (the host-side
// ./analysis-watcher's own write, read here only via the plain /data static
// mount, like any other artifact).
export async function handleRunRequest(
  song: string,
  _request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const filePath = runRequestFilePath(song);
    const payload = {
      song: validateRunRequestSong(song),
      requested_at: new Date().toISOString(),
    };
    await writeJsonFile(filePath, payload);
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(payload));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to request an analysis run.",
    );
  }
}
