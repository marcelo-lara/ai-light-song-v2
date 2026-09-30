import { describe, expect, it } from "vitest";

import { normalizeProposalDecisionPayload } from "./proposalDecision";

describe("normalizeProposalDecisionPayload", () => {
  it("passes a valid approve payload through", () => {
    const result = normalizeProposalDecisionPayload({
      id: "prop-1",
      status: "approved",
    });
    expect(result).toEqual({
      id: "prop-1",
      status: "approved",
      rejection_reason: null,
      approved_times: null,
    });
  });

  it("throws the existing message when id is missing", () => {
    expect(() => normalizeProposalDecisionPayload({ status: "approved" })).toThrow(
      "Proposal decision payload must include an id.",
    );
  });
});
