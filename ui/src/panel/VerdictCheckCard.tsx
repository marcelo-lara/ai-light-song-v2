// VerdictCheckCard.tsx — the pending `verdict_check` card of the Pending
// proposals panel (v3.11 item 24). The claim is the heading, then one row per
// evidence kind (what was read, what it showed), why the evidence could not
// settle it, the one-line question, and Confirm / Reject. Reject needs a
// reason (same two-step row as a hint card). Confirm means "the hint's claim
// holds"; Reject means it does not. The decision itself is the panel's.

import type { PendingVerdictCheckProposal, VerdictCheckEvidenceKind } from "../data/types";
import { VERDICT_CHECK_EVIDENCE_KINDS } from "../data/types";

const KIND_LABEL: Record<VerdictCheckEvidenceKind, string> = {
  stems: "Stems",
  drum_density: "Drum density",
  dropouts: "Dropouts",
  loudness: "Loudness",
  web_search: "Web search",
};

export type VerdictCardPhase =
  | { phase: "idle" }
  | { phase: "confirming-reject" }
  | { phase: "working"; action: "approve" | "reject" }
  | { phase: "error"; message: string };

interface VerdictCheckCardProps {
  proposal: PendingVerdictCheckProposal;
  focused: boolean;
  card: VerdictCardPhase;
  reason: string;
  onReasonChange: (reason: string) => void;
  onConfirm: () => void;
  onStartReject: () => void;
  onCancelReject: () => void;
  onConfirmReject: () => void;
}

export function VerdictCheckCard({
  proposal,
  focused,
  card,
  reason,
  onReasonChange,
  onConfirm,
  onStartReject,
  onCancelReject,
  onConfirmReject,
}: VerdictCheckCardProps): React.JSX.Element {
  const check = proposal.verdict_check;
  const working = card.phase === "working";
  return (
    <div
      className={`field review-queue__q${focused ? " review-queue__q--focused" : ""}`}
      data-testid="pending-proposal-card"
      data-proposal-id={proposal.id}
      data-proposal-type="verdict_check"
    >
      <label data-testid="verdict-check-claim">{check.claim}</label>
      <p className="review-queue__reason">verdict check · {check.field}</p>
      <ul className="review-queue__evidence-list" data-testid="verdict-check-evidence">
        {VERDICT_CHECK_EVIDENCE_KINDS.map((kind) => (
          <li key={kind} data-evidence-kind={kind}>
            <strong>{KIND_LABEL[kind]}</strong>
            <span className="review-queue__evidence-read">read: {check.evidence[kind].read}</span>
            <span>showed: {check.evidence[kind].showed}</span>
          </li>
        ))}
      </ul>
      <p className="review-queue__evidence">cannot settle: {check.cannot_settle}</p>
      <p className="review-queue__question" data-testid="verdict-check-question">
        {check.question}
      </p>
      {card.phase === "error" && <p className="hint-editor__status is-error">{card.message}</p>}
      {card.phase === "confirming-reject" ? (
        <div className="hint-editor__row2">
          <textarea
            className="input"
            rows={2}
            placeholder="Reason for rejecting"
            value={reason}
            onChange={(e) => onReasonChange(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={!reason.trim() || working}
            onClick={onConfirmReject}
          >
            Confirm reject
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCancelReject}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="hint-editor__actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={working}
            onClick={onStartReject}
          >
            Reject
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            disabled={working}
            onClick={onConfirm}
          >
            {working && card.action === "approve" ? "Confirming…" : "Confirm"}
          </button>
        </div>
      )}
    </div>
  );
}
