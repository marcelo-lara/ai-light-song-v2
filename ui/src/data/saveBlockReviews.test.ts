import { describe, expect, it, vi } from "vitest";

import { buildBlockReviewsPayload, saveBlockReviews } from "./saveBlockReviews";
import type { BlockReview } from "./types";

const CORRECT: BlockReview = {
  lane_id: "gestures",
  start: 7.86,
  verdict: "correct",
  reason: null,
  note: "",
  reviewed_at: "",
};

describe("buildBlockReviewsPayload", () => {
  it("rounds start to 3 decimals and stamps schema_version 1.0", () => {
    const payload = buildBlockReviewsPayload("s", [
      { ...CORRECT, start: 7.8600001 },
    ]);
    expect(payload.schema_version).toBe("1.0");
    expect(payload.reviews[0]!.start).toBe(7.86);
  });

  it("requires a lane_id", () => {
    expect(() =>
      buildBlockReviewsPayload("s", [{ ...CORRECT, lane_id: "" }]),
    ).toThrow(/lane_id/);
  });

  it("rejects an out-of-vocabulary verdict", () => {
    expect(() =>
      buildBlockReviewsPayload("s", [
        { ...CORRECT, verdict: "maybe" as never },
      ]),
    ).toThrow(/verdict must be one of/);
  });

  it("rejects reason set on correct", () => {
    expect(() =>
      buildBlockReviewsPayload("s", [{ ...CORRECT, reason: "boundary" }]),
    ).toThrow(/reason must be null/);
  });

  it("requires a reason on wrong", () => {
    expect(() =>
      buildBlockReviewsPayload("s", [
        { ...CORRECT, verdict: "wrong", reason: null },
      ]),
    ).toThrow(/reason is required/);
  });

  it("requires a reason on misplaced", () => {
    expect(() =>
      buildBlockReviewsPayload("s", [
        { ...CORRECT, verdict: "misplaced", reason: null },
      ]),
    ).toThrow(/reason is required/);
  });

  it("accepts a well-formed wrong/misplaced row", () => {
    const payload = buildBlockReviewsPayload("s", [
      { ...CORRECT, verdict: "wrong", reason: "boundary" },
    ]);
    expect(payload.reviews[0]!.reason).toBe("boundary");
  });
});

describe("saveBlockReviews", () => {
  it("PUTs the full reviews array to /api/block-reviews/<song>", async () => {
    const server = { schema_version: "1.0", song_name: "s", reviews: [CORRECT] };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => server,
    } as Response);

    const result = await saveBlockReviews(
      "A - B",
      { schema_version: "1.0", song_name: "s", reviews: [CORRECT] },
      fetchImpl as unknown as typeof fetch,
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/block-reviews/A%20-%20B",
      expect.objectContaining({ method: "PUT" }),
    );
    const body = JSON.parse(
      (fetchImpl.mock.calls[0]![1] as RequestInit).body as string,
    );
    expect(body.reviews).toEqual([CORRECT]);
    expect(result).toEqual(server);
  });

  it("throws the server error text on failure", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: async () => "Each block review must include a lane_id.",
    } as Response);

    await expect(
      saveBlockReviews(
        "x",
        { schema_version: "1.0", song_name: "", reviews: [] },
        fetchImpl as unknown as typeof fetch,
      ),
    ).rejects.toThrow("Each block review must include a lane_id.");
  });
});
