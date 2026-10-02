import { describe, expect, it } from "vitest";

import { segmentDraftFromSeed } from "./segmentDraft";

describe("segmentDraftFromSeed", () => {
  it("leaves every field unset for a bare time-span seed", () => {
    const d = segmentDraftFromSeed({ start: 1, end: 5, nonce: 1 }, []);
    expect(d).toEqual({ id: "segment-001", start: "1", end: "5", label: "", description: "", preserved: {} });
  });

  it("pre-fills a label only when it names a vocabulary value, case-insensitively", () => {
    expect(segmentDraftFromSeed({ start: 0, end: 1, nonce: 1, label: "chorus" }, []).label).toBe("Chorus");
    expect(segmentDraftFromSeed({ start: 0, end: 1, nonce: 1, label: "not-a-section" }, []).label).toBe("");
  });
});
