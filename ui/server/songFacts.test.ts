import { describe, expect, it } from "vitest";

import { normalizeSongFactsPayload } from "./songFacts";

describe("normalizeSongFactsPayload", () => {
  it("passes a valid payload through, recording human-confirmed provenance", async () => {
    const result = await normalizeSongFactsPayload(
      { song_name: "Song A", facts: { form_family: { value: "verse-chorus" } } },
      "Song A",
    );
    expect(result.song_name).toBe("Song A");
    expect(result.facts.form_family?.value).toBe("verse-chorus");
    expect(result.facts.form_family?.provenance).toBe("human-confirmed");
  });

  it("throws the existing message when the payload is not an object", async () => {
    await expect(normalizeSongFactsPayload(null, "Song A")).rejects.toThrow(
      "Song facts payload must be a JSON object.",
    );
  });
});
