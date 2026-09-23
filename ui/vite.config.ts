/// <reference types="vitest/config" />
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";

import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

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
// this server). Approving a proposal writes the human file through the
// existing handlers above; it does NOT re-run the analyzer stage that
// republishes it — a Docker-outside-of-docker trigger was tried and reverted
// (mounting the host's docker socket into this dev container was judged too
// broad a grant for what it bought, and doesn't work on a rootless Docker
// host anyway). The panel shows a reminder naming the `--stage` to run by
// hand, same as any other `reference/human/` edit.

const dataRoot = "/data";
const analysisRoot = path.join(dataRoot, "analysis");

function contentTypeFor(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();
  switch (extension) {
    case ".json":
      return "application/json; charset=utf-8";
    case ".mp3":
      return "audio/mpeg";
    case ".wav":
      return "audio/wav";
    case ".html":
      return "text/html; charset=utf-8";
    case ".css":
      return "text/css; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    default:
      return "application/octet-stream";
  }
}

function normalizeDataPath(urlPath: string): string {
  const relativePath = decodeURIComponent(urlPath.replace(/^\/data\/?/, ""));
  return path.join(dataRoot, relativePath);
}

function renderDirectoryListing(urlPath: string, entries: fs.Dirent[]): string {
  const normalizedUrl = urlPath.endsWith("/") ? urlPath : `${urlPath}/`;
  const parentPath =
    normalizedUrl === "/data/" ? null : normalizedUrl.replace(/[^/]+\/$/, "");
  const items: string[] = [];
  if (parentPath) {
    items.push(`<li><a href="../">../</a></li>`);
  }
  for (const entry of entries.sort((left, right) =>
    left.name.localeCompare(right.name),
  )) {
    const suffix = entry.isDirectory() ? "/" : "";
    items.push(
      `<li><a href="${encodeURIComponent(entry.name)}${suffix}">${entry.name}${suffix}</a></li>`,
    );
  }
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Index of ${normalizedUrl}</title>
  </head>
  <body>
    <h1>Index of ${normalizedUrl}</h1>
    <ul>
      ${items.join("\n")}
    </ul>
  </body>
</html>`;
}

async function readJsonBody(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(chunk as Buffer);
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  return raw ? JSON.parse(raw) : {};
}

type NormalizedHint = {
  id: string;
  title: string;
  start_time: number;
  end_time: number;
  summary: string;
  lighting_hint: string;
  captured_from?: string;
  type?: "hint" | "review" | "vocal";
};

function normalizeHumanHintPayload(payload: unknown): {
  song_name: string;
  human_hints: NormalizedHint[];
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Human hints payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const humanHints = Array.isArray(record.human_hints) ? record.human_hints : null;
  if (!humanHints) {
    throw new Error("Human hints payload must include a human_hints array.");
  }

  return {
    song_name: String(record.song_name || ""),
    human_hints: humanHints.map((hint: unknown, index: number) => {
      const h = (hint && typeof hint === "object" ? hint : {}) as Record<
        string,
        unknown
      >;
      const capturedFrom =
        typeof h.captured_from === "string" ? h.captured_from.trim() : "";
      const hintType =
        h.type === "hint" || h.type === "review" || h.type === "vocal"
          ? h.type
          : undefined;
      return {
        id: String(h.id ?? `human-hint-${index + 1}`),
        title: String(h.title ?? h.label ?? `Hint ${index + 1}`),
        start_time: Number(h.start_time ?? h.start_s ?? h.start ?? 0),
        end_time: Number(h.end_time ?? h.end_s ?? h.end ?? 0),
        summary: typeof h.summary === "string" ? h.summary : "",
        lighting_hint: typeof h.lighting_hint === "string" ? h.lighting_hint : "",
        // Informative note (plan v1.5 D11) — pass through only when non-empty.
        ...(capturedFrom ? { captured_from: capturedFrom } : {}),
        // Keep explicit non-default types (e.g. "review", "vocal") on save;
        // omit "hint" for canonical parity with the editor payload.
        ...(hintType && hintType !== "hint" ? { type: hintType } : {}),
      };
    }),
  };
}

// Path-escape guard: the resolved file must stay inside <analysisRoot>/<song>/.
function referenceHumanFilePath(song: unknown, fileName: string): string {
  const safeSong = path.basename(String(song || "").trim());
  if (!safeSong) {
    throw new Error("Song name is required.");
  }
  const songDir = path.join(analysisRoot, safeSong);
  const filePath = path.join(songDir, "reference", "human", fileName);
  const relativePath = path.relative(songDir, filePath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    throw new Error("Song path is outside the reference data root.");
  }
  return filePath;
}

function humanHintsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "human_hints.json");
}

// Kept in sync by hand with ui/src/data/segmentFunctions.ts (itself copied from
// docs/segments-vocabulary.md) — this file is Node-side config, not part of
// the src/ bundle, so it cannot import that module.
const SEGMENT_FUNCTION_NAMES = [
  "Intro",
  "Outro",
  "Verse",
  "Main",
  "Pre-Chorus",
  "Chorus",
  "Chorus (Inst)",
  "Post-Chorus",
  "Refrain",
  "Breakdown",
  "Break",
  "Pre-Build",
  "Build-Up",
  "Build",
  "Fill",
  "Pre-Drop",
  "Drop",
  "Extended Drop",
  "Bridge",
  "Mid-Intro",
];

// segments.json — editable, hand-authored section segmentation. Same
// writable-lane conventions as human_hints.json (explicit Save only; the
// analyzer never writes reference/), but a bare array on disk, not
// `{song_name, ...}`. `label` is a fixed value, optional, one of the names in
// docs/segments-vocabulary.md (mirrored in ui/src/data/segmentFunctions.ts) —
// never free text; it is the section's identity, not a caption, so a set
// value must come from the vocabulary. `description` is optional free text,
// never validated against the vocabulary. `energy`/`tension`, when present,
// are an integer 1-5 (same D4.2 convention as block_energy.json) — a missing
// axis is omitted, never defaulted. `rhythm` (v3.6 item 4) is optional: one
// SEGMENT_RHYTHM_VALUES name per source (`drums`/`bass`/`harmonic`/`vocals`),
// an unmarked source omitted entirely — mirrors the editor's per-source
// draft-vs-saved review (segments.seed.json, experiments/segment_seeds).
type NormalizedSegment = {
  start: number;
  end: number;
  label?: string;
  description?: string;
  energy?: number;
  tension?: number;
  rhythm?: Record<string, string>;
};

const SEGMENT_RHYTHM_KEYS = ["drums", "bass", "harmonic", "vocals"] as const;
const SEGMENT_RHYTHM_VALUES = [
  "half",
  "quarter",
  "eighth",
  "sixteenth",
  "eighth_triplet",
  "none",
] as const;

function normalizeSegmentRating(value: unknown, axis: string): number | undefined {
  if (value === undefined || value === null) return undefined;
  const n = Number(value);
  if (!Number.isInteger(n) || n < 1 || n > 5) {
    throw new Error(`Segment ${axis} must be an integer 1-5.`);
  }
  return n;
}

function normalizeSegmentLabel(value: unknown): string | undefined {
  const name = String(value ?? "").trim();
  if (!name) return undefined;
  if (!SEGMENT_FUNCTION_NAMES.includes(name)) {
    throw new Error(`Segment label "${name}" is not in segments-vocabulary.md, and free text is not allowed.`);
  }
  return name;
}

function normalizeSegmentRhythm(value: unknown): Record<string, string> | undefined {
  if (value === undefined || value === null) return undefined;
  const o = (typeof value === "object" ? value : {}) as Record<string, unknown>;
  const out: Record<string, string> = {};
  for (const key of SEGMENT_RHYTHM_KEYS) {
    const raw = o[key];
    if (raw === undefined || raw === null || raw === "") continue;
    const name = String(raw).trim();
    if (!(SEGMENT_RHYTHM_VALUES as readonly string[]).includes(name)) {
      throw new Error(
        `Segment rhythm.${key} must be one of ${SEGMENT_RHYTHM_VALUES.join(", ")}, or unset.`,
      );
    }
    out[key] = name;
  }
  return Object.keys(out).length ? out : undefined;
}

function normalizeHumanSegmentsPayload(payload: unknown): NormalizedSegment[] {
  if (!Array.isArray(payload)) {
    throw new Error("Human sections payload must be a JSON array.");
  }
  return payload.map((segment: unknown) => {
    const s = (segment && typeof segment === "object" ? segment : {}) as Record<
      string,
      unknown
    >;
    const energy = normalizeSegmentRating(s.energy, "energy");
    const tension = normalizeSegmentRating(s.tension, "tension");
    const description = String(s.description ?? "").trim();
    const label = normalizeSegmentLabel(s.label);
    const rhythm = normalizeSegmentRhythm(s.rhythm);
    return {
      start: Number(s.start ?? 0),
      end: Number(s.end ?? 0),
      ...(label ? { label } : {}),
      ...(description ? { description } : {}),
      ...(energy !== undefined ? { energy } : {}),
      ...(tension !== undefined ? { tension } : {}),
      ...(rhythm ? { rhythm } : {}),
    };
  });
}

function humanSectionsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "segments.json");
}

// v1.1 Story 8.10 — song_facts.json is written ONLY by an explicit human Save
// (the same rule Story 8.8 applies to human hints); the analyzer never writes
// `reference/`. Only the whole-song review-queue answers land here.
function songFactsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "song_facts.json");
}

// v3.4 item 4 — block_energy.json is written ONLY by an explicit human Save in
// the Human Hints events panel (the same rule human hints / song facts follow);
// the analyzer never writes `reference/`. One producer (the operator), so there
// is no `field_sources` / `source` attribution here. Nothing in `src/` or
// `mcp/` reads it. Production Nginx has no handler — the rating UI is dev-only,
// exactly like the hint editor.
function blockEnergyFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "block_energy.json");
}

// Each axis, when present, is an integer 1-5 (D4.2); a missing axis is omitted,
// never defaulted. An out-of-range or non-integer axis is rejected (400).
function normalizeBlockEnergyAxis(
  value: unknown,
  axis: string,
  hintId: string,
): number | undefined {
  if (value === undefined || value === null) return undefined;
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < 1 ||
    value > 5
  ) {
    throw new Error(`Block "${hintId}" ${axis} must be an integer 1-5.`);
  }
  return value;
}

function normalizeBlockEnergyPayload(payload: unknown): {
  schema_version: string;
  song_name: string;
  ratings: Array<{ hint_id: string; energy?: number; tension?: number }>;
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Block energy payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const ratingsIn = Array.isArray(record.ratings) ? record.ratings : null;
  if (!ratingsIn) {
    throw new Error("Block energy payload must include a ratings array.");
  }
  const ratings: Array<{ hint_id: string; energy?: number; tension?: number }> =
    [];
  for (const entry of ratingsIn) {
    const e = (entry && typeof entry === "object" ? entry : {}) as Record<
      string,
      unknown
    >;
    const hintId = String(e.hint_id ?? "").trim();
    if (!hintId) {
      throw new Error("Each block-energy rating must include a hint_id.");
    }
    const energy = normalizeBlockEnergyAxis(e.energy, "energy", hintId);
    const tension = normalizeBlockEnergyAxis(e.tension, "tension", hintId);
    if (energy === undefined && tension === undefined) continue;
    ratings.push({
      hint_id: hintId,
      ...(energy !== undefined ? { energy } : {}),
      ...(tension !== undefined ? { tension } : {}),
    });
  }
  return {
    schema_version: "1.0",
    song_name: String(record.song_name || ""),
    ratings,
  };
}

// v3.4 item 5 — lyric_validations.json is written PER-CLICK by the Moises
// Lyrics events panel's ✔ button (D5.1 / D6). This diverges from the
// explicit-Save pattern the other reference/human/ writers (human hints, song
// facts, block energy) use: a rapid token-by-token verification pass should not
// need a Save button. Each toggle PUTs the FULL `validated_ids` array and this
// handler replaces the file. Overlay only — nothing here touches
// reference/moises/lyrics.json, which stays read-only. Dev-only (production
// Nginx has no handler). Nothing in src/ or mcp/ reads the file.
function lyricValidationsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "lyric_validations.json");
}

function normalizeLyricValidationsPayload(payload: unknown): {
  schema_version: string;
  song_name: string;
  validated_ids: number[];
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Lyric validations payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const idsIn = Array.isArray(record.validated_ids) ? record.validated_ids : null;
  if (!idsIn) {
    throw new Error(
      "Lyric validations payload must include a validated_ids array.",
    );
  }
  const seen = new Set<number>();
  for (const value of idsIn) {
    if (typeof value !== "number" || !Number.isInteger(value)) {
      throw new Error("Each validated_id must be an integer.");
    }
    seen.add(value);
  }
  return {
    schema_version: "1.0",
    song_name: String(record.song_name || ""),
    validated_ids: [...seen].sort((a, b) => a - b),
  };
}

// v3.7 item 1 — block_reviews.json is written PER-CLICK by the verdict
// control in the block inspector / lane events panel, mirroring
// lyric_validations.json's pattern (D5.1: a rapid review pass should not need
// a Save button). Each toggle PUTs the FULL `reviews` array and this handler
// replaces the file. The join key is `(lane_id, start)`, never a block id
// (an array position that shifts on every re-run).
function blockReviewsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "block_reviews.json");
}

const BLOCK_REVIEW_VERDICTS = new Set(["correct", "wrong", "misplaced"]);
const BLOCK_REVIEW_REASONS = new Set(["boundary", "label", "value"]);

function normalizeBlockReviewsPayload(payload: unknown): {
  schema_version: string;
  song_name: string;
  reviews: Array<{
    lane_id: string;
    start: number;
    verdict: string;
    reason: string | null;
    note: string;
    reviewed_at: string;
  }>;
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Block reviews payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const reviewsIn = Array.isArray(record.reviews) ? record.reviews : null;
  if (!reviewsIn) {
    throw new Error("Block reviews payload must include a reviews array.");
  }
  const reviews = reviewsIn.map((entry: unknown) => {
    const r = (entry && typeof entry === "object" ? entry : {}) as Record<
      string,
      unknown
    >;
    const laneId = String(r.lane_id ?? "").trim();
    if (!laneId) {
      throw new Error("Each block review must include a lane_id.");
    }
    const start = Number(r.start);
    if (!Number.isFinite(start)) {
      throw new Error(`Block review for lane "${laneId}" must include a numeric start.`);
    }
    const verdict = String(r.verdict ?? "");
    if (!BLOCK_REVIEW_VERDICTS.has(verdict)) {
      throw new Error(
        `Block review for lane "${laneId}" verdict must be one of correct, wrong, misplaced.`,
      );
    }
    const reasonRaw = r.reason == null ? null : String(r.reason);
    if (verdict === "correct") {
      if (reasonRaw !== null) {
        throw new Error(`Block review for lane "${laneId}" reason must be null on "correct".`);
      }
    } else if (!reasonRaw || !BLOCK_REVIEW_REASONS.has(reasonRaw)) {
      throw new Error(
        `Block review for lane "${laneId}" reason must be one of boundary, label, value on "${verdict}".`,
      );
    }
    return {
      lane_id: laneId,
      start: Number(start.toFixed(3)),
      verdict,
      reason: verdict === "correct" ? null : reasonRaw,
      note: typeof r.note === "string" ? r.note : "",
      reviewed_at:
        typeof r.reviewed_at === "string" && r.reviewed_at
          ? r.reviewed_at
          : new Date().toISOString(),
    };
  });
  return {
    schema_version: "1.0",
    song_name: String(record.song_name || ""),
    reviews,
  };
}

// v3.7 item 11 — reference/proposals/pending.json is written by TWO
// producers: mcp/proposals.py appends new entries (v3.7 item 10, over stdio,
// never through this dev server), and the two handlers below flip one
// existing entry's `status` by `id`. Nothing here ever appends a NEW
// proposal — only mcp/server.py's tools do that.
// Mirrors `referenceHumanFilePath`'s escape guard exactly, but against
// `reference/proposals/` instead of `reference/human/` — the two producers
// above never write into the operator's own directory.
function pendingProposalsFilePath(song: unknown): string {
  const safeSong = path.basename(String(song || "").trim());
  if (!safeSong) {
    throw new Error("Song name is required.");
  }
  const songDir = path.join(analysisRoot, safeSong);
  const filePath = path.join(songDir, "reference", "proposals", "pending.json");
  const relativePath = path.relative(songDir, filePath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    throw new Error("Song path is outside the reference data root.");
  }
  return filePath;
}

interface PendingProposalRecord {
  id: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
  rejection_reason: string | null;
  evidence: string;
  [key: string]: unknown;
}

interface PendingProposalsFile {
  schema_version: string;
  song_name: string;
  proposals: PendingProposalRecord[];
}

async function readPendingProposals(song: string): Promise<PendingProposalsFile> {
  const filePath = pendingProposalsFilePath(song);
  try {
    const raw = await fsp.readFile(filePath, "utf-8");
    return JSON.parse(raw) as PendingProposalsFile;
  } catch (error) {
    if ((error as NodeJS.ErrnoException)?.code === "ENOENT") {
      throw new Error(`No proposals queued for "${song}" yet.`);
    }
    throw error;
  }
}

async function writePendingProposals(
  song: string,
  file: PendingProposalsFile,
): Promise<void> {
  const filePath = pendingProposalsFilePath(song);
  await fsp.mkdir(path.dirname(filePath), { recursive: true });
  await fsp.writeFile(filePath, JSON.stringify(file, null, 2) + "\n", "utf-8");
}

// `PUT /api/proposal-decision/<song>` body: `{id, status, rejection_reason?}`.
// Approve is issued by PendingProposalsPanel.tsx only AFTER the write to the
// operator's own reference/human/*.json file and the stage re-run that
// republishes it have both already succeeded — this handler only ever flips
// the queue entry's own status, never touches reference/human/. A reject
// requires a non-empty reason; only a currently "pending" entry may be
// decided, so a decided entry can never be silently re-queued or overwritten.
function normalizeProposalDecisionPayload(payload: unknown): {
  id: string;
  status: "approved" | "rejected";
  rejection_reason: string | null;
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Proposal decision payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  if (!id) {
    throw new Error("Proposal decision payload must include an id.");
  }
  const status = record.status;
  if (status !== "approved" && status !== "rejected") {
    throw new Error('Proposal decision "status" must be "approved" or "rejected".');
  }
  const rejection_reason =
    typeof record.rejection_reason === "string" ? record.rejection_reason.trim() : "";
  if (status === "rejected" && !rejection_reason) {
    throw new Error('Rejecting a proposal requires a non-empty "rejection_reason".');
  }
  return {
    id,
    status,
    rejection_reason: status === "rejected" ? rejection_reason : null,
  };
}

// Whole-song review-queue fields that disposition into song_facts.json.
const SONG_FACT_KEYS = new Set(["form_family", "form_family_vs_genre"]);

async function normalizeSongFactsPayload(
  payload: unknown,
  song: string,
): Promise<{
  schema_version: string;
  song_name: string;
  facts: Record<string, Record<string, unknown>>;
}> {
  if (!payload || typeof payload !== "object") {
    throw new Error("Song facts payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const factsIn =
    record.facts && typeof record.facts === "object"
      ? (record.facts as Record<string, unknown>)
      : {};

  // Merge onto whatever a prior human Save already wrote, so answering one
  // question does not drop the others.
  let existingFacts: Record<string, Record<string, unknown>> = {};
  try {
    const current = JSON.parse(
      await fsp.readFile(songFactsFilePath(song), "utf-8"),
    ) as Record<string, unknown>;
    if (current.facts && typeof current.facts === "object") {
      existingFacts = current.facts as Record<string, Record<string, unknown>>;
    }
  } catch {
    // no prior file — start clean
  }

  const normalizedFacts: Record<string, Record<string, unknown>> = {
    ...existingFacts,
  };
  const confirmedOn = new Date().toISOString().slice(0, 10);
  for (const [key, entry] of Object.entries(factsIn)) {
    if (!SONG_FACT_KEYS.has(key)) {
      continue;
    }
    const value =
      entry && typeof entry === "object"
        ? (entry as Record<string, unknown>).value
        : entry;
    if (value === undefined || value === null || value === "") {
      continue;
    }
    normalizedFacts[key] = {
      value,
      provenance: "human-confirmed",
      confirmed_on: confirmedOn,
    };
  }

  return {
    schema_version: "1.1",
    song_name: String(record.song_name || song || ""),
    facts: normalizedFacts,
  };
}

function parseByteRange(
  rangeHeader: string | undefined,
  fileSize: number,
): { start: number; end: number } | null {
  if (!rangeHeader || !rangeHeader.startsWith("bytes=")) {
    return null;
  }

  const [rangeSpec] = rangeHeader.replace("bytes=", "").split(",");
  const [startText, endText] = (rangeSpec ?? "").split("-");
  const hasStart = startText !== undefined && startText !== "";
  const hasEnd = endText !== undefined && endText !== "";

  if (!hasStart && !hasEnd) {
    return null;
  }

  let start = hasStart ? Number.parseInt(startText as string, 10) : NaN;
  let end = hasEnd ? Number.parseInt(endText as string, 10) : NaN;

  if (!hasStart) {
    const suffixLength = Number.isNaN(end) ? 0 : end;
    if (suffixLength <= 0) {
      return null;
    }
    start = Math.max(fileSize - suffixLength, 0);
    end = fileSize - 1;
  } else {
    if (Number.isNaN(start) || start < 0 || start >= fileSize) {
      return null;
    }
    if (Number.isNaN(end) || end >= fileSize) {
      end = fileSize - 1;
    }
  }

  if (Number.isNaN(start) || Number.isNaN(end) || start > end) {
    return null;
  }

  return { start, end };
}

function pipeFile(
  response: ServerResponse,
  filePath: string,
  start: number,
  end: number,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const stream = fs.createReadStream(filePath, { start, end });
    stream.on("error", reject);
    stream.on("end", () => resolve());
    stream.pipe(response);
  });
}

function dataMountPlugin(): Plugin {
  return {
    name: "data-mount-plugin",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const requestUrl = request.url
          ? new URL(request.url, "http://localhost")
          : null;

        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/human-hints/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/human-hints/", ""),
            );
            const payload = normalizeHumanHintPayload(
              await readJsonBody(request),
            );
            const filePath = humanHintsFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(
              filePath,
              JSON.stringify(payload, null, 2) + "\n",
              "utf-8",
            );
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(payload));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(
              error instanceof Error ? error.message : "Unable to save human hints.",
            );
          }
          return;
        }

        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/human-sections/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/human-sections/", ""),
            );
            const payload = normalizeHumanSegmentsPayload(
              await readJsonBody(request),
            );
            const filePath = humanSectionsFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(
              filePath,
              JSON.stringify(payload, null, 2) + "\n",
              "utf-8",
            );
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(payload));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(
              error instanceof Error
                ? error.message
                : "Unable to save human sections.",
            );
          }
          return;
        }

        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/song-facts/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/song-facts/", ""),
            );
            const payload = await normalizeSongFactsPayload(
              await readJsonBody(request),
              song,
            );
            const filePath = songFactsFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(
              filePath,
              JSON.stringify(payload, null, 2) + "\n",
              "utf-8",
            );
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(payload));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(
              error instanceof Error ? error.message : "Unable to save song facts.",
            );
          }
          return;
        }

        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/block-energy/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/block-energy/", ""),
            );
            const payload = normalizeBlockEnergyPayload(
              await readJsonBody(request),
            );
            const filePath = blockEnergyFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(
              filePath,
              JSON.stringify(payload, null, 2) + "\n",
              "utf-8",
            );
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(payload));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(
              error instanceof Error
                ? error.message
                : "Unable to save block energy.",
            );
          }
          return;
        }

        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/lyric-validations/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/lyric-validations/", ""),
            );
            const payload = normalizeLyricValidationsPayload(
              await readJsonBody(request),
            );
            const filePath = lyricValidationsFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(
              filePath,
              JSON.stringify(payload, null, 2) + "\n",
              "utf-8",
            );
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(payload));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(
              error instanceof Error
                ? error.message
                : "Unable to save lyric validations.",
            );
          }
          return;
        }

        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/block-reviews/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/block-reviews/", ""),
            );
            const payload = normalizeBlockReviewsPayload(
              await readJsonBody(request),
            );
            const filePath = blockReviewsFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(
              filePath,
              JSON.stringify(payload, null, 2) + "\n",
              "utf-8",
            );
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(payload));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(
              error instanceof Error
                ? error.message
                : "Unable to save block reviews.",
            );
          }
          return;
        }

        // v3.7 item 11 — approve/reject one reference/proposals/pending.json
        // entry by id. Never appends a new entry (only mcp/proposals.py does
        // that) and never itself touches reference/human/ — see
        // normalizeProposalDecisionPayload's docstring.
        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/proposal-decision/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/proposal-decision/", ""),
            );
            const decision = normalizeProposalDecisionPayload(
              await readJsonBody(request),
            );
            const file = await readPendingProposals(song);
            const index = file.proposals.findIndex((p) => p.id === decision.id);
            if (index === -1) {
              throw new Error(`No pending proposal with id "${decision.id}".`);
            }
            const current = file.proposals[index]!;
            if (current.status !== "pending") {
              throw new Error(
                `Proposal "${decision.id}" is already ${current.status} — it cannot be re-decided.`,
              );
            }
            file.proposals[index] = {
              ...current,
              status: decision.status,
              rejection_reason: decision.rejection_reason,
            };
            await writePendingProposals(song, file);
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(file));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(
              error instanceof Error
                ? error.message
                : "Unable to save the proposal decision.",
            );
          }
          return;
        }

        if (!requestUrl || !requestUrl.pathname.startsWith("/data")) {
          next();
          return;
        }

        try {
          const filePath = normalizeDataPath(requestUrl.pathname);
          const stats = await fsp.stat(filePath);
          if (stats.isDirectory()) {
            const entries = await fsp.readdir(filePath, { withFileTypes: true });
            response.statusCode = 200;
            response.setHeader("Content-Type", "text/html; charset=utf-8");
            if (request.method === "HEAD") {
              response.end();
              return;
            }
            response.end(renderDirectoryListing(requestUrl.pathname, entries));
            return;
          }

          const contentType = contentTypeFor(filePath);
          const range = parseByteRange(request.headers.range, stats.size);
          response.setHeader("Accept-Ranges", "bytes");
          response.setHeader("Content-Type", contentType);

          if (range) {
            const { start, end } = range;
            response.statusCode = 206;
            response.setHeader(
              "Content-Range",
              `bytes ${start}-${end}/${stats.size}`,
            );
            response.setHeader("Content-Length", String(end - start + 1));
            if (request.method === "HEAD") {
              response.end();
              return;
            }
            await pipeFile(response, filePath, start, end);
            return;
          }

          response.statusCode = 200;
          response.setHeader("Content-Length", String(stats.size));
          if (request.method === "HEAD") {
            response.end();
            return;
          }
          await pipeFile(response, filePath, 0, stats.size - 1);
        } catch {
          response.statusCode = 404;
          response.setHeader("Content-Type", "text/plain; charset=utf-8");
          response.end(`Not found: ${requestUrl.pathname}`);
        }
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
