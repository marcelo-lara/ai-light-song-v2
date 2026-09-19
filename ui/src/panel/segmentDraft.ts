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
//   rhythm{Drums,Bass,Harmonic,Vocals} | rhythm.{drums,bass,harmonic,vocals} ("" = unset)
//
// segments.json carries no id, so drafts get a synthetic `segment-NNN` id
// (display/selection only — never written back).

import { parseTimeInput } from "./hintDraft";
import type { SegmentDraft } from "../data/saveHumanSections";
import { SEGMENT_FUNCTION_NAMES } from "../data/segmentFunctions";
import type { HumanSegment, SegmentRhythm } from "../data/types";

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
  /** one of SEGMENT_RHYTHM_VALUES, or "" when unset */
  rhythmDrums: string;
  rhythmBass: string;
  rhythmHarmonic: string;
  rhythmVocals: string;
}

export function formatSeconds(seconds: number): string {
  return Number.isFinite(seconds) ? String(Number(seconds.toFixed(3))) : "0";
}

/** Seed a draft straight from an operator segments.json row. */
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
    rhythmDrums: segment.rhythm?.drums ?? "",
    rhythmBass: segment.rhythm?.bass ?? "",
    rhythmHarmonic: segment.rhythm?.harmonic ?? "",
    rhythmVocals: segment.rhythm?.vocals ?? "",
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
    rhythm: {
      drums: draft.rhythmDrums,
      bass: draft.rhythmBass,
      harmonic: draft.rhythmHarmonic,
      vocals: draft.rhythmVocals,
    },
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
  /** from "Create human section" on an allin1 / Moises / Segment Seeds block;
   *  used only when it names a SEGMENT_FUNCTION_NAMES value (case-insensitive) */
  label?: string | null;
  /** Segment Seeds blocks only — the seed's own draft values */
  energy?: number | null;
  tension?: number | null;
  rhythm?: SegmentRhythm | null;
}

/** The vocabulary name matching `label` case-insensitively, else "" (unset —
 *  never a guessed label). */
function vocabularyLabel(label: string | null | undefined): string {
  const wanted = (label ?? "").trim().toLowerCase();
  return SEGMENT_FUNCTION_NAMES.find((n) => n.toLowerCase() === wanted) ?? "";
}

export function segmentDraftFromSeed(
  seed: SegmentSeed,
  existing: readonly SegmentDraftFields[],
): SegmentDraftFields {
  const start = Math.max(0, seed.start || 0);
  const end = Math.max(start, seed.end || start);
  return {
    id: nextSegmentId(existing),
    // Unset unless the source block's label is a vocabulary value — the label
    // is a fixed value the operator must pick, not a free-text default.
    label: vocabularyLabel(seed.label),
    description: "",
    start: formatSeconds(start),
    end: formatSeconds(end),
    energy: seed.energy != null ? String(seed.energy) : "",
    tension: seed.tension != null ? String(seed.tension) : "",
    rhythmDrums: seed.rhythm?.drums ?? "",
    rhythmBass: seed.rhythm?.bass ?? "",
    rhythmHarmonic: seed.rhythm?.harmonic ?? "",
    rhythmVocals: seed.rhythm?.vocals ?? "",
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
