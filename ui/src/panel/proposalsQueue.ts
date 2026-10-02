// proposalsQueue.ts — pure helpers for the Pending proposals panel (v3.7
// item 11). No fetch here: the panel component owns loading/saving, this
// module only shapes data.
//

import type {
  HumanHint,
  PendingProposal,
  PendingProposalsFile,
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

/** A proposal card's playhead window: the operator's dragged correction
 * (`timeEdit`) when given, else the proposal's own proposed start/end. */
export function proposalWindow(
  proposal: PendingProposal,
  timeEdit?: { start: number; end: number },
): { start: number; end: number } {
  return timeEdit ?? { start: proposal.hint.start, end: proposal.hint.end };
}

/** Build the draft `buildHumanHintsPayload` expects for a new hint proposal.
 * `captured_from` names the proposal id — informative only (never read by
 * anything), matching the existing convention for every other captured hint.
 * `times`, when given (the operator's corrected start/end), wins over the
 * proposal's own `hint.start`/`hint.end` — `proposal.hint` itself is never
 * mutated by this. */
export function hintDraftFromProposal(
  proposal: PendingProposal,
  existingHints: HumanHint[],
  times?: { start: number; end: number },
): HintDraft {
  return {
    id: `human-hint-${existingHints.length + 1}`,
    title: proposal.hint.title,
    start_time: times?.start ?? proposal.hint.start,
    end_time: times?.end ?? proposal.hint.end,
    summary: proposal.hint.summary,
    lighting_hint: "",
    captured_from: `MCP proposal ${proposal.id}`,
    type: "review",
  };
}
