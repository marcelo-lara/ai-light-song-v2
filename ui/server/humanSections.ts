// humanSections.ts — `PUT /api/human-sections/<song>`, writing
// reference/human/segments.json (a bare array, not `{song_name, ...}`).
// Split out of vite.config.ts (v3.9 item 7) with no behaviour change.

import type { IncomingMessage, ServerResponse } from "node:http";

import { readJsonBody, referenceHumanFilePath, writeJsonFile } from "./shared";

// Kept in sync by hand with ui/src/data/segmentFunctions.ts (itself copied from
// docs/segments-vocabulary.md) — this file is Node-side config, not part of
// the src/ bundle, so it cannot import that module.
export const SEGMENT_FUNCTION_NAMES = [
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
  "Drop Break",
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
// never validated against the vocabulary.
//
// The editor writes `start`/`end`/`label`/`description` only. Any other key an
// existing row carries (older files hold fields the analyzer now ignores) is
// passed through verbatim, never validated, never dropped, never added to.
export type NormalizedSegment = {
  start: number;
  end: number;
  label?: string;
  description?: string;
  [extra: string]: unknown;
};

const SEGMENT_OWN_KEYS = new Set(["start", "end", "label", "description", "id", "function"]);

function normalizeSegmentLabel(value: unknown): string | undefined {
  const name = String(value ?? "").trim();
  if (!name) return undefined;
  if (!SEGMENT_FUNCTION_NAMES.includes(name)) {
    throw new Error(`Segment label "${name}" is not in segments-vocabulary.md, and free text is not allowed.`);
  }
  return name;
}

export function normalizeHumanSegmentsPayload(payload: unknown): NormalizedSegment[] {
  if (!Array.isArray(payload)) {
    throw new Error("Human sections payload must be a JSON array.");
  }
  return payload.map((segment: unknown) => {
    const s = (segment && typeof segment === "object" ? segment : {}) as Record<
      string,
      unknown
    >;
    const description = String(s.description ?? "").trim();
    const label = normalizeSegmentLabel(s.label);
    const extras = Object.fromEntries(
      Object.entries(s).filter(([key]) => !SEGMENT_OWN_KEYS.has(key)),
    );
    return {
      start: Number(s.start ?? 0),
      end: Number(s.end ?? 0),
      ...(label ? { label } : {}),
      ...(description ? { description } : {}),
      ...extras,
    };
  });
}

export function humanSectionsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "segments.json");
}

export async function handleHumanSections(
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const payload = normalizeHumanSegmentsPayload(await readJsonBody(request));
    await writeJsonFile(humanSectionsFilePath(song), payload);
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(payload));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to save human sections.",
    );
  }
}
