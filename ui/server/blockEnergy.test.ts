import { describe, expect, it } from "vitest";

import { normalizeBlockEnergyPayload } from "./blockEnergy";

describe("normalizeBlockEnergyPayload", () => {
  it("passes a valid payload through", () => {
    const result = normalizeBlockEnergyPayload({
      song_name: "Song A",
      ratings: [{ hint_id: "hint-001", energy: 3, tension: 2 }],
    });
    expect(result).toEqual({
      schema_version: "1.0",
      song_name: "Song A",
      ratings: [{ hint_id: "hint-001", energy: 3, tension: 2 }],
    });
  });

  it("throws the existing message when ratings is missing", () => {
    expect(() => normalizeBlockEnergyPayload({ song_name: "Song A" })).toThrow(
      "Block energy payload must include a ratings array.",
    );
  });
});
