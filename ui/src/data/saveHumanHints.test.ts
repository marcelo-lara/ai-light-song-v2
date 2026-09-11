import { describe, expect, it, vi } from "vitest";

import { buildHumanHintsPayload, saveHumanHints } from "./saveHumanHints";

const draft = (over: Partial<Parameters<typeof buildHumanHintsPayload>[1][number]> = {}) => ({
  id: "hint-001",
  title: "Drop",
  start_time: "10",
  end_time: "12",
  summary: " big ",
  lighting_hint: " strobe ",
  ...over,
});

describe("buildHumanHintsPayload", () => {
  it("coerces string times to numbers and trims text", () => {
    const payload = buildHumanHintsPayload("_test_song", [draft()]);
    expect(payload).toEqual({
      song_name: "_test_song",
      human_hints: [
        {
          id: "hint-001",
          title: "Drop",
          start_time: 10,
          end_time: 12,
          summary: "big",
          lighting_hint: "strobe",
        },
      ],
    });
  });

  it("sorts hints by start_time and renumbers ids to match", () => {
    const payload = buildHumanHintsPayload("s", [
      draft({ id: "hint-042", title: "late", start_time: 90, end_time: 92 }),
      draft({ id: "x", title: "early", start_time: 5, end_time: 6 }),
      draft({ id: "hint-007", title: "mid", start_time: 30, end_time: 31 }),
    ]);
    expect(
      payload.human_hints.map((h) => [h.id, h.title, h.start_time]),
    ).toEqual([
      ["hint-001", "early", 5],
      ["hint-002", "mid", 30],
      ["hint-003", "late", 90],
    ]);
  });

  it("keeps editor order for equal start_times", () => {
    const payload = buildHumanHintsPayload("s", [
      draft({ id: "a", title: "first", start_time: 10, end_time: 11 }),
      draft({ id: "b", title: "second", start_time: 10, end_time: 11 }),
    ]);
    expect(payload.human_hints.map((h) => [h.id, h.title])).toEqual([
      ["hint-001", "first"],
      ["hint-002", "second"],
    ]);
  });

  it("requires an id", () => {
    expect(() => buildHumanHintsPayload("s", [draft({ id: "  " })])).toThrow(
      /must include an id/,
    );
  });

  it("requires a title", () => {
    expect(() => buildHumanHintsPayload("s", [draft({ title: "" })])).toThrow(
      /must include a title/,
    );
  });

  it("rejects non-numeric times", () => {
    expect(() =>
      buildHumanHintsPayload("s", [draft({ start_time: "abc" })]),
    ).toThrow(/valid numbers/);
  });

  it("rejects end < start", () => {
    expect(() =>
      buildHumanHintsPayload("s", [draft({ start_time: 20, end_time: 5 })]),
    ).toThrow(/greater than or equal to start/);
  });

  it("allows end == start", () => {
    expect(
      buildHumanHintsPayload("s", [draft({ start_time: 5, end_time: 5 })])
        .human_hints[0]!.end_time,
    ).toBe(5);
  });

  it("omits captured_from when the draft has no note", () => {
    const hint = buildHumanHintsPayload("s", [draft()]).human_hints[0]!;
    expect(hint).not.toHaveProperty("captured_from");
  });

  it("emits a trimmed captured_from when the draft carries one", () => {
    const hint = buildHumanHintsPayload("s", [
      draft({ captured_from: "  allin1 Sections · experiments/allin1  " }),
    ]).human_hints[0]!;
    expect(hint.captured_from).toBe("allin1 Sections · experiments/allin1");
  });

  it("omits captured_from for an empty or whitespace-only note", () => {
    expect(
      buildHumanHintsPayload("s", [draft({ captured_from: "" })]).human_hints[0]!,
    ).not.toHaveProperty("captured_from");
    expect(
      buildHumanHintsPayload("s", [draft({ captured_from: "   " })])
        .human_hints[0]!,
    ).not.toHaveProperty("captured_from");
  });

  it("omits type for a hand-authored hint with no explicit type", () => {
    const hint = buildHumanHintsPayload("s", [draft()]).human_hints[0]!;
    expect(hint).not.toHaveProperty("type");
  });

  it("defaults type to review when the draft carries a captured_from note", () => {
    const hint = buildHumanHintsPayload("s", [
      draft({ captured_from: "allin1 Sections · experiments/allin1" }),
    ]).human_hints[0]!;
    expect(hint.type).toBe("review");
  });

  it("honours an explicit type over the captured_from-derived default", () => {
    const reviewOverride = buildHumanHintsPayload("s", [
      draft({ type: "hint", captured_from: "allin1 Sections · experiments/allin1" }),
    ]).human_hints[0]!;
    expect(reviewOverride).not.toHaveProperty("type");

    const hintOverride = buildHumanHintsPayload("s", [
      draft({ type: "review" }),
    ]).human_hints[0]!;
    expect(hintOverride.type).toBe("review");
  });
});

describe("saveHumanHints", () => {
  it("PUTs to /api/human-hints/<song> and returns the server file", async () => {
    const server = { song_name: "s", human_hints: [] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => server,
    } as Response);

    const result = await saveHumanHints(
      "A - B",
      { song_name: "s", human_hints: [] },
      fetchImpl as unknown as typeof fetch,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/human-hints/A%20-%20B",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(result).toEqual(server);
  });

  it("throws the server error text on failure", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: async () => "Song name is required.",
    } as Response);

    await expect(
      saveHumanHints(
        "x",
        { song_name: "", human_hints: [] },
        fetchImpl as unknown as typeof fetch,
      ),
    ).rejects.toThrow("Song name is required.");
  });
});
