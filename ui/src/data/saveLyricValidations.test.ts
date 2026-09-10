import { describe, expect, it, vi } from "vitest";

import {
  buildLyricValidationsPayload,
  saveLyricValidations,
} from "./saveLyricValidations";

describe("buildLyricValidationsPayload", () => {
  it("sorts, dedupes and stamps schema_version 1.0", () => {
    expect(buildLyricValidationsPayload("s", [3, 2, 3, 7])).toEqual({
      schema_version: "1.0",
      song_name: "s",
      validated_ids: [2, 3, 7],
    });
  });

  it("drops non-integer ids rather than defaulting", () => {
    expect(
      buildLyricValidationsPayload("s", [2, 3.5, Number.NaN, 4]).validated_ids,
    ).toEqual([2, 4]);
  });

  it("accepts an empty list (last token un-validated)", () => {
    expect(buildLyricValidationsPayload("s", []).validated_ids).toEqual([]);
  });
});

describe("saveLyricValidations", () => {
  it("PUTs the full array to /api/lyric-validations/<song>", async () => {
    const server = { schema_version: "1.0", song_name: "s", validated_ids: [2] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => server,
    } as Response);

    const result = await saveLyricValidations(
      "A - B",
      { schema_version: "1.0", song_name: "s", validated_ids: [2] },
      fetchImpl as unknown as typeof fetch,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/lyric-validations/A%20-%20B",
      expect.objectContaining({ method: "PUT" }),
    );
    const body = JSON.parse(
      (fetchImpl.mock.calls[0]![1] as RequestInit).body as string,
    );
    expect(body.validated_ids).toEqual([2]);
    expect(result).toEqual(server);
  });

  it("throws the server error text on failure", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: async () => "Each validated_id must be an integer.",
    } as Response);

    await expect(
      saveLyricValidations(
        "x",
        { schema_version: "1.0", song_name: "", validated_ids: [] },
        fetchImpl as unknown as typeof fetch,
      ),
    ).rejects.toThrow("Each validated_id must be an integer.");
  });
});
