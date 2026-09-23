// Client for `PUT /api/proposal-decision/<song>` (v3.7 item 11).
//
// Marks one `reference/proposals/pending.json` entry (found by `id`)
// "approved" or "rejected" and stores `rejection_reason` on a reject.
// Approve is issued by PendingProposalsPanel only AFTER the corresponding
// `reference/human/*.json` write and stage re-run have already succeeded, so
// a proposal is never marked approved without the value actually landing.
// The dev-server handler is the only thing that mutates pending.json besides
// mcp/proposals.py's append — an approved/rejected entry is never re-queued.

import type { PendingProposalsFile } from "./types";

export interface ProposalDecision {
  id: string;
  status: "approved" | "rejected";
  /** required on a reject, absent on an approve */
  rejection_reason?: string;
}

export async function saveProposalDecision(
  song: string,
  decision: ProposalDecision,
  fetchImpl: typeof fetch = fetch,
): Promise<PendingProposalsFile> {
  const response = await fetchImpl(
    `/api/proposal-decision/${encodeURIComponent(song)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(decision),
    },
  );

  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      message.trim() || `Failed to save the proposal decision (${response.status}).`,
    );
  }

  return (await response.json()) as PendingProposalsFile;
}
