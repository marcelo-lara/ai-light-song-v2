import { describe, expect, it } from "vitest";

import { buildHumanHintsPayload } from "../data/saveHumanHints";

import {
  draftIdForReference,
  draftToHint,
  hintToDraft,
  newHintDraft,
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
  it("seeds start/end at the playhead", () => {
    const d = newHintDraft(12.3456, []);
    expect(d.start).toBe("12.346");
    expect(d.end).toBe("12.346");
    expect(d.id).toBe("hint-001");
  });
  it("item 8: a span spreads end to start + span; default span unchanged", () => {
    const d = newHintDraft(10, [], 1.0);
    expect(d.start).toBe("10");
    expect(d.end).toBe("11");
    // default (zero span) still collapses end onto start
    expect(newHintDraft(10, []).end).toBe("10");
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
