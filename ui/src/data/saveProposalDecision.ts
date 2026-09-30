// Client for `PUT /api/proposal-decision/<song>` (v3.7 item 11).
//
// Marks one `reference/proposals/pending.json` entry (found by `id`)
// "approved" or "rejected" and stores `rejection_reason` on a reject. On an
// approve, the dev-server handler ITSELF writes the corresponding
// `reference/human/*.json` file (v3.9 item 6 — moved server-side, and
// serialized per song, after a client-side read-modify-write race there lost
// six of nineteen approved hints on one song) before flipping the status, so
// a proposal is never marked approved without the value actually landing.
// The dev-server handler is the only thing that mutates pending.json besides
// mcp/proposals.py's append — an approved/rejected entry is never re-queued.

import type { PendingProposalsFile } from "./types";

export interface ProposalDecision {
  id: string;
  status: "approved" | "rejected";
  /** required on a reject, absent on an approve */
  rejection_reason?: string;
  /** Only sent when approving a hint proposal AND the operator corrected its
   *  start/end — an unedited approve omits this (absence = approved as
   *  proposed). Rejected server-side (400) on a reject. */
  approved_times?: { start: number; end: number };
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
