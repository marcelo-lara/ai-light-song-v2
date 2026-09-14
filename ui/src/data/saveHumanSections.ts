// Client for `PUT /api/human-sections/<song>`.
//
// Same writable-lane conventions as `saveHumanHints.ts` (validate, coerce
// numeric text-input strings, PUT, treat the server-normalised response as
// the new source of truth) but against segments.json's simpler on-disk
// shape: a bare array of `{start, end, label}` — no id, no wrapper object.
// `label` is a fixed value from SEGMENT_FUNCTION_NAMES, or unset — never
// free text; `description` is optional free text, never validated against
// the vocabulary.

import { SEGMENT_FUNCTION_NAMES } from "./segmentFunctions";
import { artifactPaths } from "./paths";
import type { HumanSegment, HumanSegmentsFile } from "./types";

export interface SegmentDraft {
  id: string;
  /** one of SEGMENT_FUNCTION_NAMES, or "" when unset — never free text */
  label: string;
  /** optional free text */
  description?: string;
  start: string | number;
  end: string | number;
  /** "1".."5", or "" when unset */
  energy?: string;
  tension?: string;
}

/** Parse a "1".."5" draft field to an integer, or `null` for "" (unset). */
function ratingOrNull(value: string | undefined, field: string): number | null {
  const trimmed = (value ?? "").trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  if (!Number.isInteger(n) || n < 1 || n > 5) {
    throw new Error(`Segment ${field} must be a whole number from 1 to 5.`);
  }
  return n;
}

/**
 * Validate + normalise draft segments into the on-disk payload shape.
 *
 * On save the segments are sorted ascending by `start` (ties keep their
 * editor order); the draft-only `id` is dropped since segments.json carries
 * no id field.
 */
export function buildHumanSectionsPayload(
  drafts: SegmentDraft[],
): HumanSegmentsFile {
  const segments: HumanSegment[] = drafts.map((segment) => {
    const start = Number(segment.start);
    const end = Number(segment.end);
    const label = segment.label.trim();
    if (label && !SEGMENT_FUNCTION_NAMES.includes(label)) {
      throw new Error(`Segment label must be one of the segments-vocabulary.md names, or unset.`);
    }
    if (!Number.isFinite(start) || !Number.isFinite(end)) {
      throw new Error("Segment start and end times must be valid numbers.");
    }
    if (end < start) {
      throw new Error(
        "Segment end time must be greater than or equal to start time.",
      );
    }
    const energy = ratingOrNull(segment.energy, "energy");
    const tension = ratingOrNull(segment.tension, "tension");
    const description = (segment.description ?? "").trim();
    return {
      start,
      end,
      // Omitted (not `null`) when unset, matching human_hints.json's optional-key
      // convention — an untouched old segment stays byte-identical on re-save.
      ...(label ? { label } : {}),
      ...(description ? { description } : {}),
      ...(energy !== null ? { energy } : {}),
      ...(tension !== null ? { tension } : {}),
    };
  });

  segments.sort((a, b) => a.start - b.start);
  return segments;
}

/**
 * PUT the payload. Resolves with the server-normalised file (which the UI
 * should treat as the new source of truth). Rejects with the server's error
 * text on a non-2xx response.
 */
export async function saveHumanSections(
  song: string,
  payload: HumanSegmentsFile,
  fetchImpl: typeof fetch = fetch,
): Promise<HumanSegmentsFile> {
  const response = await fetchImpl(
    `/api/human-sections/${encodeURIComponent(song)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      message.trim() ||
        `Failed to save ${artifactPaths.humanSections(song)} (${response.status}).`,
    );
  }

  return (await response.json()) as HumanSegmentsFile;
}
