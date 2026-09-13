// segmentDraft.ts — the segment-editor draft model and its mapping to the
// segments.json payload. Mirrors hintDraft.ts's conventions, but for the
// simpler shape:
//
//   draft field         | on-disk key
//   ------------------- | -----------
//   start / end         | start / end (seconds)
//   label                | label ("" = unset; otherwise one of SEGMENT_FUNCTION_NAMES — never free text)
//   description          | description (optional free text, "" = unset)
//   energy / tension    | energy / tension (1-5, "" = unset)
//
// segments.json carries no id, so drafts get a synthetic `segment-NNN` id
// (display/selection only — never written back).

import { parseTimeInput } from "./hintDraft";
import type { SegmentDraft } from "../data/saveHumanSections";
import type { HumanSegment } from "../data/types";

export interface SegmentDraftFields {
  id: string;
  /** one of SEGMENT_FUNCTION_NAMES, or "" when unset — never free text */
  label: string;
  /** optional free text */
  description: string;
  start: string;
  end: string;
  /** "1".."5", or "" when unset (honest-unknown — never a guessed default) */
  energy: string;
  tension: string;
}

export function formatSeconds(seconds: number): string {
  return Number.isFinite(seconds) ? String(Number(seconds.toFixed(3))) : "0";
}

export function segmentToDraft(
  segment: HumanSegment,
  index: number,
): SegmentDraftFields {
  return {
    id: `segment-${String(index + 1).padStart(3, "0")}`,
    label: String(segment.label ?? ""),
    description: segment.description ?? "",
    start: formatSeconds(Number(segment.start ?? 0)),
    end: formatSeconds(Number(segment.end ?? 0)),
    energy: segment.energy != null ? String(segment.energy) : "",
    tension: segment.tension != null ? String(segment.tension) : "",
  };
}

/** Draft -> the loose shape `buildHumanSectionsPayload` validates + normalises. */
export function draftToSegment(draft: SegmentDraftFields): SegmentDraft {
  return {
    id: draft.id,
    label: draft.label,
    description: draft.description,
    start: parseTimeInput(draft.start),
    end: parseTimeInput(draft.end),
    energy: draft.energy,
    tension: draft.tension,
  };
}

/** Next `segment-NNN` id given the existing drafts. */
export function nextSegmentId(existing: readonly SegmentDraftFields[]): string {
  const max = existing.reduce((acc, d) => {
    const m = /^segment-(\d+)$/.exec(d.id.trim());
    const n = m ? Number(m[1]) : NaN;
    return Number.isFinite(n) && n > acc ? n : acc;
  }, 0);
  return `segment-${String(max + 1).padStart(3, "0")}`;
}

/**
 * A pending "open the segment editor on a pre-filled draft" request — raised
 * by a double-click on the Human Sections lane background. `nonce` makes
 * each request distinct so the editor consumes it exactly once.
 */
export interface SegmentSeed {
  start: number;
  end: number;
  nonce: number;
}

export function segmentDraftFromSeed(
  seed: SegmentSeed,
  existing: readonly SegmentDraftFields[],
): SegmentDraftFields {
  const start = Math.max(0, seed.start || 0);
  const end = Math.max(start, seed.end || start);
  return {
    id: nextSegmentId(existing),
    // Left unset — the label is a fixed vocabulary value the operator must
    // pick, not a free-text default like the old "Segment N".
    label: "",
    description: "",
    start: formatSeconds(start),
    end: formatSeconds(end),
    energy: "",
    tension: "",
  };
}

/** Match a Human Sections block selection back to a draft id. */
export function draftIdForSegmentReference(
  reference: string | null | undefined,
  drafts: readonly SegmentDraftFields[],
): string {
  const ref = String(reference ?? "").trim();
  if (!ref) return "";
  return drafts.find((d) => d.id === ref)?.id ?? "";
}
