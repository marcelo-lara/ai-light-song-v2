import { describe, expect, it } from "vitest";

import { buildHumanHintsPayload } from "../data/saveHumanHints";

import {
  draftIdForReference,
  draftToHint,
  hintDraftFromSeed,
  hintToDraft,
  nextHintId,
  parseTimeInput,
  type HintDraftFields,
} from "./hintDraft";

describe("parseTimeInput", () => {
  it("passes raw seconds through", () => {
    expect(parseTimeInput("83.4")).toBe("83.4");
    expect(parseTimeInput("  12 ")).toBe("12");
  });
  it("converts m:ss(.s) to canonical seconds", () => {
    expect(parseTimeInput("1:23.4")).toBe("83.4");
    expect(parseTimeInput("0:05")).toBe("5");
    expect(parseTimeInput("2:00")).toBe("120");
  });
  it("leaves empty / unparseable input for validation to catch", () => {
    expect(parseTimeInput("")).toBe("");
    expect(parseTimeInput("soon")).toBe("soon");
  });
});

describe("draft <-> hint mapping (design notes §4)", () => {
  const hint = {
    id: "hint-002",
    title: "Drop",
    start_time: 61.5,
    end_time: 78,
    summary: "big build then release",
    lighting_hint: "strobe on the downbeat",
  };

  it("round-trips through the on-disk payload", () => {
    const draft = hintToDraft(hint);
    expect(draft).toEqual({
      id: "hint-002",
      title: "Drop",
      start: "61.5",
      end: "78",
      musical: "big build then release",
      lighting: "strobe on the downbeat",
    });
    const payload = buildHumanHintsPayload("song", [draftToHint(draft)]);
    expect(payload.human_hints[0]).toEqual(hint);
  });

  it("carries captured_from through hintToDraft / draftToHint untouched", () => {
    const captured = {
      ...hint,
      id: "hint-003",
      captured_from: "allin1 Sections · experiments/allin1",
    };
    const draft = hintToDraft(captured);
    expect(draft.capturedFrom).toBe("allin1 Sections · experiments/allin1");
    const out = buildHumanHintsPayload("song", [draftToHint(draft)])
      .human_hints[0]!;
    expect(out.captured_from).toBe("allin1 Sections · experiments/allin1");
  });

  it("omits capturedFrom on a hand-authored hint", () => {
    expect(hintToDraft(hint)).not.toHaveProperty("capturedFrom");
    expect(
      buildHumanHintsPayload("song", [draftToHint(hintToDraft(hint))])
        .human_hints[0]!,
    ).not.toHaveProperty("captured_from");
  });

  it("maps musical->summary and lighting->lighting_hint", () => {
    const draft: HintDraftFields = {
      id: "hint-001",
      title: "T",
      start: "1:00",
      end: "1:10",
      musical: "M",
      lighting: "L",
    };
    const out = buildHumanHintsPayload("s", [draftToHint(draft)]).human_hints[0]!;
    expect(out.start_time).toBe(60);
    expect(out.end_time).toBe(70);
    expect(out.summary).toBe("M");
    expect(out.lighting_hint).toBe("L");
  });
});

describe("validation surfaced from buildHumanHintsPayload", () => {
  const base: HintDraftFields = {
    id: "hint-001",
    title: "T",
    start: "10",
    end: "20",
    musical: "",
    lighting: "",
  };
  const build = (d: HintDraftFields) =>
    buildHumanHintsPayload("s", [draftToHint(d)]);

  it("requires an id", () => {
    expect(() => build({ ...base, id: "  " })).toThrow(/id/);
  });
  it("requires a title", () => {
    expect(() => build({ ...base, title: "" })).toThrow(/title/);
  });
  it("rejects non-numeric times", () => {
    expect(() => build({ ...base, start: "soon" })).toThrow(/valid numbers/);
  });
  it("rejects end < start", () => {
    expect(() => build({ ...base, start: "20", end: "10" })).toThrow(
      /greater than or equal/,
    );
  });
  it("accepts end == start", () => {
    expect(() => build({ ...base, start: "10", end: "10" })).not.toThrow();
  });
});

describe("new hint ids", () => {
  it("increments hint-NNN", () => {
    const drafts = [
      { id: "hint-001" } as HintDraftFields,
      { id: "hint-004" } as HintDraftFields,
    ];
    expect(nextHintId(drafts)).toBe("hint-005");
    expect(nextHintId([])).toBe("hint-001");
  });
});

describe("hintDraftFromSeed (plan v1.5 item 9)", () => {
  it("seeds start/end from the seed, rounding through formatSeconds", () => {
    const d = hintDraftFromSeed({ start: 12.3456, end: 12.3456, nonce: 1 }, []);
    expect(d.start).toBe("12.346");
    expect(d.end).toBe("12.346");
    expect(d.id).toBe("hint-001");
  });
  it("carries a widened span through (double-click path: end = start + 1.0)", () => {
    const d = hintDraftFromSeed({ start: 10, end: 11, nonce: 2 }, []);
    expect(d.start).toBe("10");
    expect(d.end).toBe("11");
  });
  it("continues the existing hint-NNN sequence", () => {
    const existing = [
      { id: "hint-001" } as HintDraftFields,
      { id: "hint-002" } as HintDraftFields,
    ];
    expect(hintDraftFromSeed({ start: 0, end: 0, nonce: 3 }, existing).id).toBe(
      "hint-003",
    );
  });
  it("falls back to `Hint <n>` when the seed carries no title", () => {
    const existing = [{ id: "hint-001" } as HintDraftFields];
    expect(hintDraftFromSeed({ start: 0, end: 0, nonce: 4 }, existing).title).toBe(
      "Hint 2",
    );
    expect(
      hintDraftFromSeed({ start: 0, end: 0, title: "  ", nonce: 5 }, []).title,
    ).toBe("Hint 1");
  });
  it("maps title, summary and capturedFrom from the seed", () => {
    const d = hintDraftFromSeed(
      {
        start: 40,
        end: 48,
        title: "intro",
        summary: "the opening bars",
        capturedFrom: "allin1 Sections · experiments/allin1",
        nonce: 6,
      },
      [],
    );
    expect(d.title).toBe("intro");
    expect(d.musical).toBe("the opening bars");
    expect(d.capturedFrom).toBe("allin1 Sections · experiments/allin1");
    expect(d.lighting).toBe("");
  });
  it("omits capturedFrom when the seed carries none or an empty string", () => {
    expect(
      hintDraftFromSeed({ start: 0, end: 0, nonce: 7 }, []),
    ).not.toHaveProperty("capturedFrom");
    expect(
      hintDraftFromSeed({ start: 0, end: 0, capturedFrom: "  ", nonce: 8 }, []),
    ).not.toHaveProperty("capturedFrom");
  });
});

describe("draftIdForReference", () => {
  it("matches a hint block selection back to a draft", () => {
    const drafts = [{ id: "hint-002" } as HintDraftFields];
    expect(draftIdForReference("hint-002", drafts)).toBe("hint-002");
    expect(draftIdForReference("hint-009", drafts)).toBe("");
    expect(draftIdForReference(null, drafts)).toBe("");
  });
});
