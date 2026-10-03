import { describe, expect, it } from "vitest";

import type { HumanHint, PendingHintProposal, PendingProposalsFile } from "../data/types";

import * as queue from "./proposalsQueue";
import { hintDraftFromProposal, partitionProposals, proposalWindow } from "./proposalsQueue";

const hintProposal = (over: Partial<PendingHintProposal> = {}): PendingHintProposal => ({
  id: "prop-1",
  type: "hint",
  status: "pending",
  created_at: "2026-09-22T00:00:00Z",
  rejection_reason: null,
  evidence: "loudness spike",
  hint: { start: 10, end: 12, title: "Drop payoff", summary: "loudness spike" },
  ...over,
} as PendingHintProposal);

describe("partitionProposals", () => {
  it("splits pending from decided, newest-decided first", () => {
    const file: PendingProposalsFile = {
      schema_version: "1.0",
      song_name: "ayuni",
      proposals: [
        hintProposal({ id: "a", status: "approved", created_at: "2026-09-20T00:00:00Z" }),
        hintProposal({ id: "b", status: "pending" }),
        hintProposal({ id: "c", status: "rejected", created_at: "2026-09-21T00:00:00Z" }),
      ],
    };
    const { pending, decided } = partitionProposals(file);
    expect(pending.map((p) => p.id)).toEqual(["b"]);
    expect(decided.map((p) => p.id)).toEqual(["c", "a"]);
  });
});

describe("proposalWindow", () => {
  it("uses the proposal's own start/end with no operator edit", () => {
    expect(proposalWindow(hintProposal())).toEqual({ start: 10, end: 12 });
  });

  it("prefers the operator's dragged correction", () => {
    expect(proposalWindow(hintProposal(), { start: 9, end: 13 })).toEqual({ start: 9, end: 13 });
  });
});

describe("section-field helpers are gone", () => {
  it("exports no section-field merge or section span lookup", () => {
    expect(queue).not.toHaveProperty("applySectionFieldToSegments");
    expect(queue).not.toHaveProperty("bestOverlapIndex");
    expect(queue).not.toHaveProperty("sectionSpan");
  });
});

describe("hintDraftFromProposal", () => {
  const existing: HumanHint[] = [
    {
      id: "human-hint-1",
      title: "existing",
      start_time: 1,
      end_time: 2,
      summary: "",
      lighting_hint: "",
    },
  ];

  it("builds a HintDraft carrying the proposal id as an informative note", () => {
    const proposal = hintProposal();
    const draft = hintDraftFromProposal(proposal, existing);
    expect(draft).toEqual({
      id: "human-hint-2",
      title: "Drop payoff",
      start_time: 10,
      end_time: 12,
      summary: "loudness spike",
      lighting_hint: "",
      captured_from: "MCP proposal prop-1",
      type: "review",
    });
  });

  it("falls back to the proposal's own hint.start/end when no times are given", () => {
    const proposal = hintProposal();
    const draft = hintDraftFromProposal(proposal, existing);
    expect(draft.start_time).toBe(proposal.hint.start);
    expect(draft.end_time).toBe(proposal.hint.end);
  });

  it("uses the operator's corrected times over the proposal's own, when given", () => {
    const proposal = hintProposal();
    const draft = hintDraftFromProposal(proposal, existing, { start: 9.5, end: 13.25 });
    expect(draft.start_time).toBe(9.5);
    expect(draft.end_time).toBe(13.25);
    // every other field is unaffected by the override
    expect(draft.title).toBe("Drop payoff");
    expect(proposal.hint.start).toBe(10);
    expect(proposal.hint.end).toBe(12);
  });
});
