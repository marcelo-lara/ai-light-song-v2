import { describe, expect, it } from "vitest";

import { normalizeBlockReviewsPayload } from "./blockReviews";

describe("normalizeBlockReviewsPayload", () => {
  it("passes a valid payload through", () => {
    const result = normalizeBlockReviewsPayload({
      song_name: "Song A",
      reviews: [
        {
          lane_id: "sections",
          start: 1.23456,
          verdict: "wrong",
          reason: "boundary",
          note: "off by a beat",
          reviewed_at: "2026-01-01T00:00:00.000Z",
        },
      ],
    });
    expect(result).toEqual({
      schema_version: "1.0",
      song_name: "Song A",
      reviews: [
        {
          lane_id: "sections",
          start: 1.235,
          verdict: "wrong",
          reason: "boundary",
          note: "off by a beat",
          reviewed_at: "2026-01-01T00:00:00.000Z",
        },
      ],
    });
  });

  it("throws the existing message when reviews is missing", () => {
    expect(() => normalizeBlockReviewsPayload({ song_name: "Song A" })).toThrow(
      "Block reviews payload must include a reviews array.",
    );
  });
});
