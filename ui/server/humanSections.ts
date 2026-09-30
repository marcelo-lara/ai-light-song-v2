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
export type NormalizedSegment = {
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

export function normalizeHumanSegmentsPayload(payload: unknown): NormalizedSegment[] {
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
