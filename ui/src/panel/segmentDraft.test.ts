import { describe, expect, it } from "vitest";

import { segmentDraftFromSeed } from "./segmentDraft";

describe("segmentDraftFromSeed", () => {
  it("leaves every field unset for a bare time-span seed", () => {
    const d = segmentDraftFromSeed({ start: 1, end: 5, nonce: 1 }, []);
    expect(d).toMatchObject({ start: "1", end: "5", label: "", energy: "", tension: "", rhythmDrums: "" });
  });

  it("pre-fills a label only when it names a vocabulary value, case-insensitively", () => {
    expect(segmentDraftFromSeed({ start: 0, end: 1, nonce: 1, label: "chorus" }, []).label).toBe("Chorus");
    expect(segmentDraftFromSeed({ start: 0, end: 1, nonce: 1, label: "not-a-section" }, []).label).toBe("");
  });

  it("carries seed energy, tension and rhythm across", () => {
    const d = segmentDraftFromSeed(
      { start: 0, end: 8, nonce: 1, energy: 4, tension: 2, rhythm: { drums: "quarter", bass: "eighth" } },
      [],
    );
    expect(d).toMatchObject({ energy: "4", tension: "2", rhythmDrums: "quarter", rhythmBass: "eighth", rhythmVocals: "" });
  });
});
