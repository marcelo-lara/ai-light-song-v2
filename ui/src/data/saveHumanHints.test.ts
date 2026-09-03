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
