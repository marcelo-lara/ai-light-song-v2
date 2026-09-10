import { describe, expect, it, vi } from "vitest";

import { buildBlockEnergyPayload, saveBlockEnergy } from "./saveBlockEnergy";
import type { BlockEnergyDraft } from "./saveBlockEnergy";

const draft = (over: Partial<BlockEnergyDraft> = {}): BlockEnergyDraft => ({
  hint_id: "hint-001",
  energy: 5,
  tension: 4,
  ...over,
});

describe("buildBlockEnergyPayload", () => {
  it("keeps a fully-rated block and stamps schema_version 1.0", () => {
    expect(buildBlockEnergyPayload("_test_song", [draft()])).toEqual({
      schema_version: "1.0",
      song_name: "_test_song",
      ratings: [{ hint_id: "hint-001", energy: 5, tension: 4 }],
    });
  });

  it("drops a block that is unrated on both axes", () => {
    expect(
      buildBlockEnergyPayload("s", [draft({ energy: null, tension: null })])
        .ratings,
    ).toEqual([]);
  });

  it("keeps a partially-rated block, carrying only the set axis", () => {
    expect(
      buildBlockEnergyPayload("s", [draft({ energy: 3, tension: null })]).ratings,
    ).toEqual([{ hint_id: "hint-001", energy: 3 }]);
  });

  it("requires a hint_id", () => {
    expect(() =>
      buildBlockEnergyPayload("s", [draft({ hint_id: "  " })]),
    ).toThrow(/hint_id/);
  });

  it("rejects an out-of-range axis", () => {
    expect(() =>
      buildBlockEnergyPayload("s", [draft({ energy: 6 })]),
    ).toThrow(/energy must be an integer 1-5/);
    expect(() =>
      buildBlockEnergyPayload("s", [draft({ tension: 0 })]),
    ).toThrow(/tension must be an integer 1-5/);
  });

  it("rejects a non-integer axis", () => {
    expect(() =>
      buildBlockEnergyPayload("s", [draft({ energy: 3.5 })]),
    ).toThrow(/integer 1-5/);
  });
});

describe("saveBlockEnergy", () => {
  it("PUTs to /api/block-energy/<song> and returns the server file", async () => {
    const server = { schema_version: "1.0", song_name: "s", ratings: [] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => server,
    } as Response);

    const result = await saveBlockEnergy(
      "A - B",
      { schema_version: "1.0", song_name: "s", ratings: [] },
      fetchImpl as unknown as typeof fetch,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/block-energy/A%20-%20B",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(result).toEqual(server);
  });

  it("throws the server error text on failure", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: async () => "Block energy payload must be a JSON object.",
    } as Response);

    await expect(
      saveBlockEnergy(
        "x",
        { schema_version: "1.0", song_name: "", ratings: [] },
        fetchImpl as unknown as typeof fetch,
      ),
    ).rejects.toThrow("Block energy payload must be a JSON object.");
  });
});
