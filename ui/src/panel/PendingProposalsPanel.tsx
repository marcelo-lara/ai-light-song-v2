// PendingProposalsPanel.tsx — right-panel/drawer mode: MCP correction
// proposals (v3.7 item 11, refinement item 7's approval side).
//
// Lists `reference/proposals/pending.json`, written only by
// `mcp/server.py`'s `propose_hint` (v3.7 item 10) —
// the MCP server stays read-only against every top-level and operator file;
// this panel is the ONLY path from a queued proposal to a real value.
//
// Approve:
//  - hint      -> the dev-server's `PUT /api/proposal-decision/<song>`
//                 handler itself appends to reference/human/human_hints.json
//                 (v3.9 item 6 — moved server-side and serialized per song;
//                 the previous client-side load-then-save race lost hints
//                 under concurrent approvals). This panel just shows a
//                 reminder naming the stage to re-run by hand
//                 (`generate-section-hints`).
// The debugger does not trigger analyzer stages itself (no Docker-socket
// access from this container — see docker-compose.yml's history for why that
// was tried and reverted for v3.7 item 11). The human write and the status
// flip to "approved" happen together, server-side — a failed write leaves
// the proposal "pending", never a silent partial state. The operator runs
// the named `--stage` themselves — same manual step CLAUDE.md's "Running
// things" already documents for any other `reference/human/` edit.
//
// Reject: marks the entry "rejected" with an operator-entered reason. No
// write to reference/human/ happens on a reject.
//
// verdict_check (v3.11 item 24) is the second card type. Confirm / Reject is
// the same endpoint; the dev-server handler writes the answer as `operator`
// on that verdict in reference/pre-analysis/verdict.json (see
// ui/server/proposalDecision.ts) and flips the row, no re-run stage involved.

import { useCallback, useEffect, useMemo, useState } from "react";

import { loadPendingProposals } from "../data/loaders";
import { saveProposalDecision } from "../data/saveProposalDecision";
import type { PendingProposal, PendingProposalsFile } from "../data/types";

import { isTimeInWindow } from "./laneEvents";
import { RightPanel } from "./RightPanel";
import { VerdictCheckCard } from "./VerdictCheckCard";
import { partitionProposals, proposalWindow } from "./proposalsQueue";

interface PendingProposalsPanelProps {
  song: string;
  onClose: () => void;
  /** The LLM Pending Proposals timeline lane's block-click focus: the
   *  proposal id to scroll into view and highlight, once the queue is ready. */
  focusId?: string | null;
  /** Called with the reloaded queue after every successful
   *  approve/reject (and after the initial load), so the caller can update a
   *  read-time lane override without a full artifact reload. */
  onQueueChange?: (file: PendingProposalsFile) => void;
  /** The transport's current playhead position, for the in-window accent
   *  stripe on any card whose window covers it. */
  currentTime: number;
  /** A click on a card (outside its actions/reason field) moves the playhead
   *  to its window's start — `timeEdits[proposal.id]` or `proposal.hint`'s
   *  own start/end. Absent -> the card isn't clickable. */
  onSeek?: (time: number) => void;
  /** App.tsx's operator Start/End correction, keyed by proposal id — set by
   *  dragging the block's edges/interior on the LLM Pending Proposals lane
   *  (SparseLane's existing drag-to-edit mechanism, same as Human Hints).
   *  App owns this map; the panel only reads and displays it. */
  timeEdits?: Record<string, { start: number; end: number }>;
  /** Clears one proposal's entry in `timeEdits` — the ↺ reset button, and
   *  (called by this panel) once a proposal is approved or rejected. */
  onResetTimes?: (id: string) => void;
}

/** 3-decimal display for a proposed/corrected time. */
function formatTime(n: number): string {
  return n.toFixed(3);
}

type QueueState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; file: PendingProposalsFile };

type CardState =
  | { phase: "idle" }
  | { phase: "confirming-reject" }
  | { phase: "working"; action: "approve" | "reject" }
  | { phase: "error"; message: string };

function summarize(p: PendingProposal): string {
  if (p.type === "verdict_check") return `${p.verdict_check.field} · ${p.verdict_check.claim}`;
  return `${p.hint.title || "(untitled)"} · ${p.hint.start.toFixed(2)}s–${p.hint.end.toFixed(2)}s`;
}

/** What a decided row's status means to the operator: a confirmed verdict check is "confirmed", not "approved". */
function decidedWord(p: PendingProposal): string {
  return p.type === "verdict_check" && p.status === "approved" ? "confirmed" : p.status;
}

export function PendingProposalsPanel({
  song,
  onClose,
  focusId = null,
  onQueueChange,
  currentTime,
  onSeek,
  timeEdits = {},
  onResetTimes,
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
    void loadPendingProposals(song).then((queueResult) => {
      if (cancelled) return;
      if (!queueResult.ok) {
        setQueueState({ status: "error", message: queueResult.error.message });
        return;
      }
      setQueueState({ status: "ready", file: queueResult.data });
      onQueueChange?.(queueResult.data);
    });
    return () => {
      cancelled = true;
    };
  }, [song, onQueueChange]);

  useEffect(() => reload(), [reload]);

  const setCard = useCallback((id: string, state: CardState) => {
    setCards((current) => ({ ...current, [id]: state }));
  }, []);

  const approve = useCallback(
    async (proposal: PendingProposal) => {
      if (queueState.status !== "ready") return;
      setCard(proposal.id, { phase: "working", action: "approve" });
      try {
        // Only set when the operator dragged this hint's block on the LLM
        // Pending Proposals lane — App.tsx's `timeEdits` only ever holds a
        // drag commit's already-clamped/validated times (0 <= start < end),
        // so no re-validation is needed here. Absent -> approved as proposed.
        const approvedTimes: { start: number; end: number } | undefined =
          proposal.type === "hint" ? timeEdits[proposal.id] : undefined;
        // The dev-server handler now does the reference/human/*.json write
        // itself, from its own fresh read, serialized per song (v3.9 item
        // 6) — this call is the whole approve, not a follow-up to a write
        // this panel already made.
        await saveProposalDecision(song, {
          id: proposal.id,
          status: "approved",
          ...(approvedTimes ? { approved_times: approvedTimes } : {}),
        });
        // A hint approve republishes only on a stage re-run; a confirmed
        // verdict_check changes no published file, so it has no reminder.
        if (proposal.type === "hint") {
          setRerunReminders((cur) => ({ ...cur, [proposal.id]: "generate-section-hints" }));
        }
        setCard(proposal.id, { phase: "idle" });
        onResetTimes?.(proposal.id);
        reload();
      } catch (error) {
        setCard(proposal.id, {
          phase: "error",
          message: error instanceof Error ? error.message : "Unable to approve this proposal.",
        });
      }
    },
    [song, queueState, setCard, reload, timeEdits, onResetTimes],
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
        onResetTimes?.(proposal.id);
        reload();
      } catch (error) {
        setCard(proposal.id, {
          phase: "error",
          message: error instanceof Error ? error.message : "Unable to reject this proposal.",
        });
      }
    },
    [song, rejectReason, setCard, reload, onResetTimes],
  );

  const partitioned = useMemo(
    () =>
      queueState.status === "ready"
        ? partitionProposals(queueState.file)
        : { pending: [], decided: [] },
    [queueState],
  );

  // Scroll a block-click's focused card into view once the queue is
  // ready. Only the Pending group's cards carry `data-proposal-id` (below),
  // so a focus id for an already-decided proposal simply finds nothing.
  // `RightPanel` doesn't forward a ref, so this scopes the query by its own
  // `data-testid` instead of a local element ref.
  useEffect(() => {
    if (!focusId || queueState.status !== "ready") return;
    const el = document.querySelector(
      `[data-testid="pending-proposals"] [data-proposal-id="${CSS.escape(focusId)}"]`,
    );
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focusId, queueState]);

  // A click anywhere on a card seeks to its window's
  // start, except a click that originated inside the actions row, the
  // reject-reason field, or any button/input/textarea — those already have
  // their own handlers and must not also move the playhead.
  const handleCardClick = useCallback(
    (proposal: PendingProposal) => (event: React.MouseEvent<HTMLDivElement>) => {
      if (!onSeek || queueState.status !== "ready" || proposal.type !== "hint") return;
      const cardWindow = proposalWindow(proposal, timeEdits[proposal.id]);
      const target = event.target as Element;
      if (target.closest(".hint-editor__actions, .hint-editor__row2, button, textarea, input")) {
        return;
      }
      onSeek(cardWindow.start);
    },
    [onSeek, queueState, timeEdits],
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
                No queued proposals — `propose_hint`
                has not been called for this song, or every one has been decided.
              </p>
            ) : (
              partitioned.pending.map((proposal) => {
                const card = cards[proposal.id] ?? { phase: "idle" };
                if (proposal.type === "verdict_check") {
                  return (
                    <VerdictCheckCard
                      key={proposal.id}
                      proposal={proposal}
                      focused={proposal.id === focusId}
                      card={card}
                      reason={rejectReason[proposal.id] ?? ""}
                      onReasonChange={(r) =>
                        setRejectReason((cur) => ({ ...cur, [proposal.id]: r }))
                      }
                      onConfirm={() => void approve(proposal)}
                      onStartReject={() => setCard(proposal.id, { phase: "confirming-reject" })}
                      onCancelReject={() => setCard(proposal.id, { phase: "idle" })}
                      onConfirmReject={() => void confirmReject(proposal)}
                    />
                  );
                }
                const working = card.phase === "working";
                // The operator's dragged-edge correction for this hint card, if
                // any — App.tsx's `timeEdits`, keyed by proposal id.
                const edit = timeEdits[proposal.id];
                // The card's playhead window — the proposed (or edited) span —
                // and whether `currentTime` falls inside it.
                const cardWindow = proposalWindow(proposal, edit);
                const inWindow = isTimeInWindow(cardWindow, currentTime);
                return (
                  <div
                    key={proposal.id}
                    className={`field review-queue__q${
                      proposal.id === focusId ? " review-queue__q--focused" : ""
                    }${onSeek ? " review-queue__q--clickable" : ""}`}
                    data-testid="pending-proposal-card"
                    data-proposal-id={proposal.id}
                    data-in-window={inWindow}
                    onClick={handleCardClick(proposal)}
                  >
                    <label>
                      {proposal.hint.title || "(untitled)"}
                    </label>
                    <p className="review-queue__reason">{summarize(proposal)}</p>
                    {proposal.hint.summary && (
                      <p className="review-queue__reason">{proposal.hint.summary}</p>
                    )}
                    <p className="review-queue__evidence">evidence: {proposal.evidence}</p>
                    {edit && (
                      <div className="hint-editor__row2">
                        <p className="review-queue__reason">
                          proposed {formatTime(proposal.hint.start)}–
                          {formatTime(proposal.hint.end)} s → {formatTime(edit.start)}–
                          {formatTime(edit.end)} s
                        </p>
                        <span className="review-queue__edited-tag">edited</span>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          title="Reset to proposed times"
                          onClick={() => onResetTimes?.(proposal.id)}
                        >
                          ↺
                        </button>
                      </div>
                    )}
                    <p className="review-queue__evidence">
                      Drag the block&rsquo;s edges on the LLM Pending Proposals lane to adjust
                      timing.
                    </p>
                    {card.phase === "error" && (
                      <p className="hint-editor__status is-error">{card.message}</p>
                    )}
                    {card.phase === "confirming-reject" ? (
                      <div className="hint-editor__row2">
                        <textarea
                          className="input"
                          rows={2}
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
                      {decidedWord(proposal)} · {summarize(proposal)}
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
