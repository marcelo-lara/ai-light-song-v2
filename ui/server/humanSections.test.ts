import { describe, expect, it } from "vitest";

import { normalizeHumanSegmentsPayload } from "./humanSections";

describe("normalizeHumanSegmentsPayload", () => {
  it("writes start/end/label/description and adds nothing else", () => {
    const result = normalizeHumanSegmentsPayload([
      { start: 0, end: 10, label: "Intro", description: " warm " },
    ]);
    expect(result).toEqual([{ start: 0, end: 10, label: "Intro", description: "warm" }]);
  });

  it("leaves keys it does not own (legacy energy/tension/rhythm) exactly as they were", () => {
    const legacy = { energy: 2, tension: 1, rhythm: { drums: "quarter" } };
    const result = normalizeHumanSegmentsPayload([{ start: 0, end: 10, label: "Intro", ...legacy }]);
    expect(result).toEqual([{ start: 0, end: 10, label: "Intro", ...legacy }]);
  });

  it("accepts and keeps a Drop Break label", () => {
    const result = normalizeHumanSegmentsPayload([{ start: 0, end: 10, label: "Drop Break" }]);
    expect(result[0]!.label).toBe("Drop Break");
  });

  it("throws the existing message when the payload is not an array", () => {
    expect(() => normalizeHumanSegmentsPayload({ start: 0, end: 10 })).toThrow(
      "Human sections payload must be a JSON array.",
    );
  });
});
