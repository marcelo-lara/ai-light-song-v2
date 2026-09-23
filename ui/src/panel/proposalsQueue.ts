// proposalsQueue.ts — pure helpers for the Pending proposals panel (v3.7
// item 11). No fetch here: the panel component owns loading/saving, this
// module only shapes data.
//
// Approving a `section_field` proposal writes into reference/human/segments.json
// (the operator's own file), matched to the proposal's `section_id` by
// overlap with the current top-level `sections.json` span — the same
// best-overlap rule `section_clues.py` (src/analyzer/stages/section_clues.py)
// uses to resolve a human/seed row against a published section. A section
// with no overlapping human row gets a brand-new one at the section's own
// span, since approving a proposal is the act of giving that row a value.

import type {
  HumanHint,
  HumanSegment,
  HumanSegmentsFile,
  PendingProposal,
  PendingProposalsFile,
  SectionsTopLevel,
} from "../data/types";
import type { HintDraft } from "../data/saveHumanHints";

export function partitionProposals(file: PendingProposalsFile): {
  pending: PendingProposal[];
  decided: PendingProposal[];
} {
  const pending = file.proposals.filter((p) => p.status === "pending");
  const decided = file.proposals
    .filter((p) => p.status !== "pending")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  return { pending, decided };
}

/** The published span for a section_id, or `null` if the section no longer
 * exists (the song was re-analysed and boundaries shifted). */
export function sectionSpan(
  sections: SectionsTopLevel,
  sectionId: string,
): { start: number; end: number } | null {
  const row = sections.find((s) => s.section_id === sectionId);
  return row ? { start: row.start, end: row.end } : null;
}

/** Index of the segments.json row with the largest positive overlap against
 * [start, end], or -1 when no row overlaps at all. */
export function bestOverlapIndex(
  segments: HumanSegmentsFile,
  start: number,
  end: number,
): number {
  let bestIndex = -1;
  let bestOverlap = 0;
  segments.forEach((row, index) => {
    const overlap = Math.min(end, row.end) - Math.max(start, row.start);
    if (overlap > bestOverlap) {
      bestOverlap = overlap;
      bestIndex = index;
    }
  });
  return bestIndex;
}

function applyFieldToRow(
  row: HumanSegment,
  field: string,
  value: number | string,
): HumanSegment {
  if (field === "energy" || field === "tension") {
    if (typeof value !== "number" || !Number.isInteger(value) || value < 1 || value > 5) {
      throw new Error(`Proposal field "${field}" must be an integer 1-5.`);
    }
    return { ...row, [field]: value };
  }
  if (field.startsWith("rhythm.")) {
    const stem = field.slice("rhythm.".length);
    if (typeof value !== "string") {
      throw new Error(`Proposal field "${field}" must be a string.`);
    }
    return { ...row, rhythm: { ...(row.rhythm ?? {}), [stem]: value } };
  }
  throw new Error(`Unknown proposal field: "${field}".`);
}

/** Apply one section_field proposal onto the current human segments array,
 * returning a NEW array (the input is never mutated). Matches (or creates) a
 * row by span overlap against `span`, never by index. */
export function applySectionFieldToSegments(
  segments: HumanSegmentsFile,
  span: { start: number; end: number },
  field: string,
  value: number | string,
): HumanSegmentsFile {
  const index = bestOverlapIndex(segments, span.start, span.end);
  if (index === -1) {
    return [...segments, applyFieldToRow({ start: span.start, end: span.end }, field, value)];
  }
  return segments.map((row, i) => (i === index ? applyFieldToRow(row, field, value) : row));
}

/** Build the draft `buildHumanHintsPayload` expects for a new hint proposal.
 * `captured_from` names the proposal id — informative only (never read by
 * anything), matching the existing convention for every other captured hint. */
export function hintDraftFromProposal(
  proposal: Extract<PendingProposal, { type: "hint" }>,
  existingHints: HumanHint[],
): HintDraft {
  return {
    id: `human-hint-${existingHints.length + 1}`,
    title: proposal.hint.title,
    start_time: proposal.hint.start,
    end_time: proposal.hint.end,
    summary: proposal.hint.summary,
    lighting_hint: "",
    captured_from: `MCP proposal ${proposal.id}`,
    type: "review",
  };
}
