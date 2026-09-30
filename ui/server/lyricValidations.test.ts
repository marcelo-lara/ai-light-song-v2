import { describe, expect, it } from "vitest";

import { normalizeLyricValidationsPayload } from "./lyricValidations";

describe("normalizeLyricValidationsPayload", () => {
  it("passes a valid payload through, sorted and de-duplicated", () => {
    const result = normalizeLyricValidationsPayload({
      song_name: "Song A",
      validated_ids: [3, 1, 1, 2],
    });
    expect(result).toEqual({
      schema_version: "1.0",
      song_name: "Song A",
      validated_ids: [1, 2, 3],
    });
  });

  it("throws the existing message when validated_ids is missing", () => {
    expect(() => normalizeLyricValidationsPayload({ song_name: "Song A" })).toThrow(
      "Lyric validations payload must include a validated_ids array.",
    );
  });
});
