import { describe, expect, it } from "vitest";

import { normalizeHumanHintPayload } from "./humanHints";

describe("normalizeHumanHintPayload", () => {
  it("passes a valid payload through, filling defaults for a bare hint", () => {
    const result = normalizeHumanHintPayload({
      song_name: "Song A",
      human_hints: [
        { id: "hint-001", title: "Intro", start_time: 1, end_time: 2 },
      ],
    });
    expect(result.song_name).toBe("Song A");
    expect(result.human_hints).toEqual([
      {
        id: "hint-001",
        title: "Intro",
        start_time: 1,
        end_time: 2,
        summary: "",
        lighting_hint: "",
      },
    ]);
  });

  it("throws the existing message when human_hints is missing", () => {
    expect(() => normalizeHumanHintPayload({ song_name: "Song A" })).toThrow(
      "Human hints payload must include a human_hints array.",
    );
  });
});
