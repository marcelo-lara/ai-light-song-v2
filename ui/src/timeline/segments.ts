// segments.ts — the Segments header blocks, ported from the canvas
// `buildSegments`: HTML blocks positioned by start/end seconds -> x, tinted by
// the allin1 functional label (chorus = accent ramp, else neutral ramp),
// labelled with the cleaned functional name + "N bars" with the label hidden
// when the block is narrow (width < SEGMENT_LABEL_MIN_WIDTH).

import type { SectionRow } from "../data/types";

import type { Coords } from "./coords";
import { SEGMENT_LABEL_MIN_WIDTH } from "./zoom";

// allin1's Harmonix vocabulary has no "drop"/"hook" label — only "chorus"
// reads as the natural accent among `intro verse chorus bridge inst break
// outro solo start end` (plan v3.0 item 7).
const ACCENT_ROLES = new Set(["chorus"]);

export interface SegmentBlock {
  key: string;
  sectionId: string | null;
  /** the cleaned functional name parsed off the projected `label`, e.g. "Chorus" */
  functionName: string | null;
  /** display name: the cleaned-up projection label */
  name: string;
  /** "N bars" or "" when the block is too narrow */
  barsText: string;
  /** x within the body column (label column NOT included) */
  left: number;
  width: number;
  /** true => accent ramp tint, false => neutral ramp tint */
  accent: boolean;
  /** whether the text label should render at all */
  showLabel: boolean;
  section: SectionRow;
}

/** "003 Momentum Lift (0.80)" -> "Momentum Lift" */
export function cleanLabel(label: string): string {
  const stripped = label
    .replace(/^\s*\d+\s+/, "")
    .replace(/\s*\([0-9]*\.?[0-9]+\)\s*$/, "")
    .trim();
  return stripped || label.trim();
}

export function displayRole(section: SectionRow): string {
  return cleanLabel(section.label);
}

/** real bar count inside [start, end), from the coords bar lines */
export function countBars(coords: Coords, start: number, end: number): number {
  let count = 0;
  for (const line of coords.barLines) {
    if (line.time >= start - 1e-6 && line.time < end - 1e-6) count += 1;
  }
  return count;
}

export function buildSegments(
  sections: readonly SectionRow[],
  coords: Coords,
): SegmentBlock[] {
  return sections.map((section, index) => {
    const left = coords.timeToX(section.start);
    const width = Math.max(coords.timeToX(section.end) - left - 2, 2);
    const functionName = cleanLabel(section.label);
    const accent = ACCENT_ROLES.has(functionName.toLowerCase());
    const bars = countBars(coords, section.start, section.end);
    const showLabel = width >= 34;
    const barsText =
      width >= SEGMENT_LABEL_MIN_WIDTH && bars > 0 ? `${bars} bars` : "";
    return {
      key: section.section_id ?? `seg-${index}`,
      sectionId: section.section_id,
      functionName,
      name: displayRole(section),
      barsText,
      left,
      width,
      accent,
      showLabel,
      section,
    };
  });
}
