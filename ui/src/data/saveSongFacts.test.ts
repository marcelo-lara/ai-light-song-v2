import { describe, expect, it, vi } from "vitest";

import { buildSongFactsPayload, saveSongFacts } from "./saveSongFacts";

describe("buildSongFactsPayload", () => {
  it("keeps only whole-song keys and stamps human-confirmed provenance", () => {
    const payload = buildSongFactsPayload("_test_song", {
      form_family: "aaba",
      "sections.section-002.form_role": "chorus",
      "drops.timed_location": "28.7",
    });
    expect(payload).toEqual({
      song_name: "_test_song",
      facts: {
        form_family: { value: "aaba", provenance: "human-confirmed" },
      },
    });
  });

  it("trims values and drops blank answers", () => {
    const payload = buildSongFactsPayload("s", {
      form_family: "  verse_chorus  ",
      "drops.timed_location": "   ",
    });
    expect(payload.facts).toEqual({
      form_family: { value: "verse_chorus", provenance: "human-confirmed" },
    });
    expect(buildSongFactsPayload("s", { form_family: "   " }).facts).toEqual({});
  });

  it("emits an empty facts object when nothing is answered", () => {
    expect(buildSongFactsPayload("s", {}).facts).toEqual({});
  });
});

describe("saveSongFacts", () => {
  it("PUTs to /api/song-facts/<song> and returns the server file", async () => {
    const server = { schema_version: "1.1", song_name: "s", facts: {} };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => server,
    } as Response);

    const result = await saveSongFacts(
      "A - B",
      { song_name: "s", facts: {} },
      fetchImpl as unknown as typeof fetch,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/song-facts/A%20-%20B",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(result).toEqual(server);
  });

  it("throws the server error text on failure", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: async () => "Song facts payload must be a JSON object.",
    } as Response);

    await expect(
      saveSongFacts(
        "x",
        { song_name: "", facts: {} },
        fetchImpl as unknown as typeof fetch,
      ),
    ).rejects.toThrow("Song facts payload must be a JSON object.");
  });
});
