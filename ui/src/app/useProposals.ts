// useProposals.ts — LLM Pending Proposals lane state: the server-normalised
// override, the operator's drag-time edits and the focus-a-card handshake
// with the Pending Proposals drawer panel. Split out of App.tsx (v3.9 item 7)
// with no behaviour change.

import { useCallback, useMemo, useState } from "react";

import type { PendingProposalsFile } from "../data/types";

export interface ProposalsState {
  pendingProposalsFile: PendingProposalsFile | null;
  /** The LLM Pending Proposals lane's own copy: every PENDING hint
   *  proposal's hint.start/end replaced by the operator's drag edit, so the
   *  dragged block stays where it was dropped. The panel itself always
   *  loads/saves the real file — this is a read-time overlay for the lane
   *  only. */
  pendingProposalsFileForLane: PendingProposalsFile | null;
  proposalsFocusId: string | null;
  setProposalsFocusId: React.Dispatch<React.SetStateAction<string | null>>;
  proposalTimeEdits: Record<string, { start: number; end: number }>;
  setProposalsOverride: React.Dispatch<React.SetStateAction<PendingProposalsFile | null>>;
  resetProposalsState: () => void;
  handleCommitProposalTimes: (blockId: string, start: number, end: number) => void;
  handleResetProposalTimes: (id: string) => void;
}

export function useProposals(
  pendingProposalsData: PendingProposalsFile | null | undefined,
): ProposalsState {
  // The server-normalised pending.json returned after every approve/reject
  // on the Pending Proposals panel, applied in place so the LLM Pending
  // Proposals lane drops a decided block without a full reload (same
  // reasoning as App's `hintsOverride`).
  const [proposalsOverride, setProposalsOverride] =
    useState<PendingProposalsFile | null>(null);
  // A click on an LLM Pending Proposals block (lane or events panel) opens
  // the Pending Proposals drawer scrolled to that proposal's card.
  const [proposalsFocusId, setProposalsFocusId] = useState<string | null>(null);
  // The operator's Start/End correction for a pending hint proposal, keyed
  // by proposal id — set by dragging the block's edges/interior on the LLM
  // Pending Proposals lane (SparseLane's drag-to-edit, same mechanism as
  // Human Hints; see `handleCommitProposalTimes`). This state is the sole
  // owner: it moves the lane's block live AND is what PendingProposalsPanel
  // reads/displays and sends on approve. It writes no file itself —
  // approving is what turns an edit into a real value.
  const [proposalTimeEdits, setProposalTimeEdits] = useState<
    Record<string, { start: number; end: number }>
  >({});

  const pendingProposalsFile = proposalsOverride ?? pendingProposalsData ?? null;

  const pendingProposalsFileForLane = useMemo<PendingProposalsFile | null>(() => {
    if (!pendingProposalsFile || Object.keys(proposalTimeEdits).length === 0) {
      return pendingProposalsFile;
    }
    return {
      ...pendingProposalsFile,
      proposals: pendingProposalsFile.proposals.map((p) => {
        if (p.type !== "hint" || p.status !== "pending") return p;
        const edit = proposalTimeEdits[p.id];
        if (!edit) return p;
        return { ...p, hint: { ...p.hint, start: edit.start, end: edit.end } };
      }),
    };
  }, [pendingProposalsFile, proposalTimeEdits]);

  // The LLM Pending Proposals lane's drag commit (SparseLane's
  // onCommitHintTimes, same mechanism as Human Hints/Human Sections) — but
  // this lane writes NO file. It only updates `proposalTimeEdits`, so the
  // block stays where it was dropped and the Pending Proposals panel picks
  // up the correction on approve. An invalid drop (not 0 <= start < end,
  // e.g. dragged past the other edge) is silently ignored — no revert
  // needed since we never reject, and the lane simply keeps its last valid
  // position. `blockId` is this lane's adapter-assigned block id
  // (`llmPendingProposals-<proposal.id>`, laneContent.ts's
  // `llmPendingProposalsContent`) — stripping that fixed prefix recovers the
  // same proposal id `handleSelectMarker`'s `marker.raw.reference` resolves
  // to for a click on the same block.
  const handleCommitProposalTimes = useCallback(
    (blockId: string, start: number, end: number) => {
      if (!(Number.isFinite(start) && Number.isFinite(end) && start >= 0 && start < end)) {
        return;
      }
      const prefix = "llmPendingProposals-";
      const proposalId = blockId.startsWith(prefix) ? blockId.slice(prefix.length) : blockId;
      setProposalTimeEdits((cur) => ({ ...cur, [proposalId]: { start, end } }));
    },
    [],
  );

  // The ↺ reset button, and PendingProposalsPanel's own cleanup once a
  // proposal is approved or rejected (same prop, per the operator's "keep it
  // simple" — a decided proposal's edit is just as stale as a reset one).
  const handleResetProposalTimes = useCallback((id: string) => {
    setProposalTimeEdits((cur) => {
      if (!(id in cur)) return cur;
      const next = { ...cur };
      delete next[id];
      return next;
    });
  }, []);

  const resetProposalsState = useCallback(() => {
    setProposalsOverride(null);
    setProposalsFocusId(null);
    setProposalTimeEdits({});
  }, []);

  return {
    pendingProposalsFile,
    pendingProposalsFileForLane,
    proposalsFocusId,
    setProposalsFocusId,
    proposalTimeEdits,
    setProposalsOverride,
    resetProposalsState,
    handleCommitProposalTimes,
    handleResetProposalTimes,
  };
}
