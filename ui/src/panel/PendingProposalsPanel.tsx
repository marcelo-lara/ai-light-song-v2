// PendingProposalsPanel.tsx — right-panel/drawer mode: MCP correction
// proposals (v3.7 item 11, refinement item 7's approval side).
//
// Lists `reference/proposals/pending.json`, written only by
// `mcp/server.py`'s `propose_hint`/`propose_section_field` (v3.7 item 10) —
// the MCP server stays read-only against every top-level and operator file;
// this panel is the ONLY path from a queued proposal to a real value.
//
// Approve:
//  - hint      -> appends to reference/human/human_hints.json through the
//                 EXISTING `saveHumanHints` PUT client. The write alone does
//                 not republish hints.json — the panel then shows a reminder
//                 naming the stage to re-run by hand (`generate-section-hints`).
//  - section_field -> merges onto reference/human/segments.json (by span
//                 overlap against the proposal's section_id, never by index)
//                 through the EXISTING `saveHumanSections` PUT client, then
//                 shows a reminder to re-run `section-clues` so sections.json
//                 republishes it with `<field>_source: "human"`.
// The debugger does not trigger analyzer stages itself (no Docker-socket
// access from this container — see docker-compose.yml's history for why that
// was tried and reverted for v3.7 item 11). Once the human write succeeds the
// proposal is marked "approved"; a failed write leaves it "pending", never a
// silent partial state. The operator runs the named `--stage` themselves —
// same manual step CLAUDE.md's "Running things" already documents for any
// other `reference/human/` edit.
//
// Reject: marks the entry "rejected" with an operator-entered reason. No
// write to reference/human/ happens on a reject.

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  loadHumanHints,
  loadHumanSegments,
  loadPendingProposals,
  loadSectionsTopLevel,
} from "../data/loaders";
import { buildHumanHintsPayload, saveHumanHints } from "../data/saveHumanHints";
import { saveHumanSections } from "../data/saveHumanSections";
import { saveProposalDecision } from "../data/saveProposalDecision";
import type { PendingProposal, PendingProposalsFile, SectionsTopLevel } from "../data/types";

import { RightPanel } from "./RightPanel";
import {
  applySectionFieldToSegments,
  hintDraftFromProposal,
  partitionProposals,
  sectionSpan,
} from "./proposalsQueue";

interface PendingProposalsPanelProps {
  song: string;
  onClose: () => void;
}

type QueueState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; file: PendingProposalsFile; sections: SectionsTopLevel };

type CardState =
  | { phase: "idle" }
  | { phase: "confirming-reject" }
  | { phase: "working"; action: "approve" | "reject" }
  | { phase: "error"; message: string };

function summarize(p: PendingProposal): string {
  if (p.type === "hint") {
    return `${p.hint.title || "(untitled)"} · ${p.hint.start.toFixed(2)}s–${p.hint.end.toFixed(2)}s`;
  }
  return `${p.section_field.section_id} · ${p.section_field.field} = ${p.section_field.value}`;
}

export function PendingProposalsPanel({
  song,
  onClose,
}: PendingProposalsPanelProps): React.JSX.Element {
  const [queueState, setQueueState] = useState<QueueState>({ status: "loading" });
  const [cards, setCards] = useState<Record<string, CardState>>({});
  const [rejectReason, setRejectReason] = useState<Record<string, string>>({});
  // Survives `reload()` (unlike `cards`, which is keyed by an id that may no
  // longer be in the "pending" list once approved) — the stage name to
  // remind the operator to re-run for a proposal just approved this session.
  const [rerunReminders, setRerunReminders] = useState<Record<string, string>>({});

  const reload = useCallback(() => {
    let cancelled = false;
    setQueueState({ status: "loading" });
    void Promise.all([loadPendingProposals(song), loadSectionsTopLevel(song)]).then(
      ([queueResult, sectionsResult]) => {
        if (cancelled) return;
        if (!queueResult.ok) {
          setQueueState({ status: "error", message: queueResult.error.message });
          return;
        }
        setQueueState({
          status: "ready",
          file: queueResult.data,
          sections: sectionsResult.ok ? sectionsResult.data : [],
        });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [song]);

  useEffect(() => reload(), [reload]);

  const setCard = useCallback((id: string, state: CardState) => {
    setCards((current) => ({ ...current, [id]: state }));
  }, []);

  const approve = useCallback(
    async (proposal: PendingProposal) => {
      if (queueState.status !== "ready") return;
      setCard(proposal.id, { phase: "working", action: "approve" });
      try {
        let stageToRerun: string;
        if (proposal.type === "hint") {
          const hintsResult = await loadHumanHints(song);
          const currentHints = hintsResult.ok ? hintsResult.data.human_hints : [];
          const songName = hintsResult.ok ? hintsResult.data.song_name : song;
          const draft = hintDraftFromProposal(proposal, currentHints);
          const payload = buildHumanHintsPayload(songName, [...currentHints, draft]);
          await saveHumanHints(song, payload);
          stageToRerun = "generate-section-hints";
        } else {
          const span = sectionSpan(queueState.sections, proposal.section_field.section_id);
          if (!span) {
            throw new Error(
              `Section ${proposal.section_field.section_id} is no longer on sections.json — re-run analysis before approving.`,
            );
          }
          const segmentsResult = await loadHumanSegments(song);
          const currentSegments = segmentsResult.ok ? segmentsResult.data : [];
          const updated = applySectionFieldToSegments(
            currentSegments,
            span,
            proposal.section_field.field,
            proposal.section_field.value,
          );
          await saveHumanSections(song, updated);
          stageToRerun = "section-clues";
        }
        await saveProposalDecision(song, { id: proposal.id, status: "approved" });
        setRerunReminders((cur) => ({ ...cur, [proposal.id]: stageToRerun }));
        setCard(proposal.id, { phase: "idle" });
        reload();
      } catch (error) {
        setCard(proposal.id, {
          phase: "error",
          message: error instanceof Error ? error.message : "Unable to approve this proposal.",
        });
      }
    },
    [song, queueState, setCard, reload],
  );

  const confirmReject = useCallback(
    async (proposal: PendingProposal) => {
      const reason = (rejectReason[proposal.id] ?? "").trim();
      if (!reason) return;
      setCard(proposal.id, { phase: "working", action: "reject" });
      try {
        await saveProposalDecision(song, {
          id: proposal.id,
          status: "rejected",
          rejection_reason: reason,
        });
        setCard(proposal.id, { phase: "idle" });
        reload();
      } catch (error) {
        setCard(proposal.id, {
          phase: "error",
          message: error instanceof Error ? error.message : "Unable to reject this proposal.",
        });
      }
    },
    [song, rejectReason, setCard, reload],
  );

  const partitioned = useMemo(
    () =>
      queueState.status === "ready"
        ? partitionProposals(queueState.file)
        : { pending: [], decided: [] },
    [queueState],
  );

  const header = <span className="app-rightpanel__kicker">Pending proposals</span>;

  return (
    <RightPanel
      open
      onClose={onClose}
      header={header}
      aria-label="Pending proposals"
      data-testid="pending-proposals"
    >
      {queueState.status === "loading" && (
        <p className="hint-editor__empty">Loading pending proposals…</p>
      )}

      {queueState.status === "error" && (
        <p className="hint-editor__empty">
          Could not load pending proposals: {queueState.message}
        </p>
      )}

      {queueState.status === "ready" && (
        <div className="review-queue">
          <section className="review-queue__group">
            <h3 className="review-queue__group-title">
              Pending
              <span className="review-queue__count">{partitioned.pending.length}</span>
            </h3>
            {partitioned.pending.length === 0 ? (
              <p className="hint-editor__empty">
                No queued proposals — none of `propose_hint`/`propose_section_field`
                have been called for this song, or every one has been decided.
              </p>
            ) : (
              partitioned.pending.map((proposal) => {
                const card = cards[proposal.id] ?? { phase: "idle" };
                const working = card.phase === "working";
                return (
                  <div
                    key={proposal.id}
                    className="field review-queue__q"
                    data-testid="pending-proposal-card"
                    data-proposal-id={proposal.id}
                  >
                    <label>
                      {proposal.type === "hint" ? "Hint" : "Section field"}
                    </label>
                    <p className="review-queue__reason">{summarize(proposal)}</p>
                    <p className="review-queue__evidence">evidence: {proposal.evidence}</p>
                    {card.phase === "error" && (
                      <p className="hint-editor__status is-error">{card.message}</p>
                    )}
                    {card.phase === "confirming-reject" ? (
                      <div className="hint-editor__row2">
                        <input
                          className="input"
                          placeholder="Reason for rejecting"
                          value={rejectReason[proposal.id] ?? ""}
                          onChange={(e) =>
                            setRejectReason((cur) => ({ ...cur, [proposal.id]: e.target.value }))
                          }
                        />
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          disabled={!(rejectReason[proposal.id] ?? "").trim() || working}
                          onClick={() => void confirmReject(proposal)}
                        >
                          Confirm reject
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => setCard(proposal.id, { phase: "idle" })}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="hint-editor__actions">
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          disabled={working}
                          onClick={() => setCard(proposal.id, { phase: "confirming-reject" })}
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          disabled={working}
                          onClick={() => void approve(proposal)}
                        >
                          {working && card.action === "approve" ? "Approving…" : "Approve"}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </section>

          <section className="review-queue__group">
            <h3 className="review-queue__group-title">
              Decided
              <span className="review-queue__count">{partitioned.decided.length}</span>
            </h3>
            {partitioned.decided.length === 0 ? (
              <p className="hint-editor__empty">No decided proposals yet.</p>
            ) : (
              <ul className="review-queue__context">
                {partitioned.decided.map((proposal) => (
                  <li key={proposal.id} className="review-queue__context-item">
                    <div className="review-queue__context-field">
                      {proposal.status} · {summarize(proposal)}
                    </div>
                    {proposal.rejection_reason && (
                      <div className="review-queue__reason">{proposal.rejection_reason}</div>
                    )}
                    {rerunReminders[proposal.id] && (
                      <div className="review-queue__reason" data-testid="rerun-reminder">
                        Not republished yet — run{" "}
                        <code>
                          {`./analyze --stage ${rerunReminders[proposal.id]}`}
                        </code>{" "}
                        for this song.
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </RightPanel>
  );
}
