import { describe, expect, it } from "vitest";

import { normalizeHumanSegmentsPayload } from "./humanSections";

describe("normalizeHumanSegmentsPayload", () => {
  it("passes a valid payload through", () => {
    const result = normalizeHumanSegmentsPayload([
      { start: 0, end: 10, label: "Intro", energy: 2, tension: 1, rhythm: { drums: "quarter" } },
    ]);
    expect(result).toEqual([
      { start: 0, end: 10, label: "Intro", energy: 2, tension: 1, rhythm: { drums: "quarter" } },
    ]);
  });

  it("throws the existing message when the payload is not an array", () => {
    expect(() => normalizeHumanSegmentsPayload({ start: 0, end: 10 })).toThrow(
      "Human sections payload must be a JSON array.",
    );
  });
});
