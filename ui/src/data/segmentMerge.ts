// segmentMerge.ts — v3.6 item 4 ("Seeds first"). Per-field fusion of the
// operator's reference/human/segments.json against the unreviewed rule-based
// reference/human/segments.seed.json (experiments/segment_seeds), for display
// only. Never written back as-is: a save always goes through
// `saveHumanSections.ts` into segments.json.
//
// Per field (docs/product-refinement-v3.6.md section 6, "Unreviewed seeds
// reach MCP with a warning" / the UI half of that rule): the operator's own
// value wins when present; otherwise the seed's value is shown as an
// `isDraft: true` fallback. Spans come from segments.json when it holds any
// rows; with no segments.json at all (or an empty one), the seed's own spans
// are shown instead, every field a draft. Seeds are matched to an operator
// span by `start` — the two files share spans by construction
// (experiments/segment_seeds/features.py never invents boundaries).

import type {
  HumanSegment,
  HumanSegmentsFile,
  HumanSegmentsSeedFile,
  SegmentRhythm,
} from "./types";

export interface MergedSegmentField<T> {
  value: T;
  isDraft: boolean;
}

export type MergedRhythm = Record<
  "drums" | "bass" | "harmonic" | "vocals",
  MergedSegmentField<string | null>
>;

export interface MergedSegment {
  start: number;
  end: number;
  label: string | null;
  description: string | null;
  energy: MergedSegmentField<number | null>;
  tension: MergedSegmentField<number | null>;
  rhythm: MergedRhythm;
}

const RHYTHM_KEYS = ["drums", "bass", "harmonic", "vocals"] as const;

/** Key spans by `start`, tolerant of float noise past 3 decimals. */
function startKey(start: number): string {
  return start.toFixed(3);
}

function rhythmValue(rhythm: SegmentRhythm | null | undefined, key: (typeof RHYTHM_KEYS)[number]): string | null {
  return rhythm?.[key] ?? null;
}

export function mergeHumanSegments(
  operator: HumanSegmentsFile | null,
  seed: HumanSegmentsSeedFile | null,
): MergedSegment[] {
  const opRows = operator ?? [];
  const seedRows = seed ?? [];
  const seedByStart = new Map(seedRows.map((s) => [startKey(s.start), s]));

  interface BaseRow {
    start: number;
    end: number;
    label: string | null;
    description: string | null;
    energy: number | null;
    tension: number | null;
    rhythm: SegmentRhythm | null;
  }

  // With no operator spans at all, fall back to the seed's own spans — every
  // field on them is necessarily a draft, since there is nothing to fuse
  // against.
  const base: BaseRow[] =
    opRows.length > 0
      ? opRows.map((s: HumanSegment) => ({
          start: s.start,
          end: s.end,
          label: s.label ?? null,
          description: s.description ?? null,
          energy: s.energy ?? null,
          tension: s.tension ?? null,
          rhythm: s.rhythm ?? null,
        }))
      : seedRows.map((s) => ({
          start: s.start,
          end: s.end,
          label: s.label ?? null,
          description: null,
          energy: null,
          tension: null,
          rhythm: null,
        }));

  return base.map((row) => {
    const seedRow = seedByStart.get(startKey(row.start));

    const energy: MergedSegmentField<number | null> =
      row.energy != null
        ? { value: row.energy, isDraft: false }
        : { value: seedRow?.energy ?? null, isDraft: (seedRow?.energy ?? null) != null };

    const tension: MergedSegmentField<number | null> =
      row.tension != null
        ? { value: row.tension, isDraft: false }
        : { value: seedRow?.tension ?? null, isDraft: (seedRow?.tension ?? null) != null };

    const rhythm = RHYTHM_KEYS.reduce((acc, key) => {
      const opVal = rhythmValue(row.rhythm, key);
      if (opVal != null) {
        acc[key] = { value: opVal, isDraft: false };
      } else {
        const seedVal = rhythmValue(seedRow?.rhythm, key);
        acc[key] = { value: seedVal, isDraft: seedVal != null };
      }
      return acc;
    }, {} as MergedRhythm);

    return {
      start: row.start,
      end: row.end,
      label: row.label,
      description: row.description,
      energy,
      tension,
      rhythm,
    };
  });
}
