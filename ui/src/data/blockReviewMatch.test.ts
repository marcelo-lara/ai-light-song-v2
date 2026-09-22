import { describe, expect, it } from "vitest";

import {
  REVIEWABLE_LANE_IDS,
  indexBlockReviews,
  matchBlockReviews,
  reviewKey,
  startsByLane,
} from "./blockReviewMatch";
import type { BlockReview } from "./types";

const review = (lane_id: string, start: number, verdict: BlockReview["verdict"] = "correct"): BlockReview => ({
  lane_id,
  start,
  verdict,
  reason: verdict === "correct" ? null : "boundary",
  note: "",
  reviewed_at: "",
});

describe("REVIEWABLE_LANE_IDS", () => {
  it("includes every experiment lane plus gestures, and excludes reference/human lanes", () => {
    expect(REVIEWABLE_LANE_IDS.has("gestures")).toBe(true);
    expect(REVIEWABLE_LANE_IDS.has("segmentSeeds")).toBe(true);
    expect(REVIEWABLE_LANE_IDS.has("tensionShape")).toBe(true);
    expect(REVIEWABLE_LANE_IDS.has("moisesSections")).toBe(false);
    expect(REVIEWABLE_LANE_IDS.has("moisesLyrics")).toBe(false);
    expect(REVIEWABLE_LANE_IDS.has("humanHints")).toBe(false);
    expect(REVIEWABLE_LANE_IDS.has("humanSections")).toBe(false);
  });
});

describe("matchBlockReviews", () => {
  it("marks a review within tolerance as not stale", () => {
    const [matched] = matchBlockReviews(
      [review("gestures", 7.86)],
      new Map([["gestures", [7.86, 15.232]]]),
    );
    expect(matched!.stale).toBe(false);
  });

  it("marks a review with no matching current block as stale — never dropped", () => {
    const reviews = [review("gestures", 999.999)];
    const matched = matchBlockReviews(reviews, new Map([["gestures", [7.86]]]));
    expect(matched).toHaveLength(1);
    expect(matched[0]!.stale).toBe(true);
  });

  it("honours the +-0.25s tolerance boundary", () => {
    const matched = matchBlockReviews(
      [review("gestures", 7.86 + 0.25), review("gestures", 7.86 + 0.26)],
      new Map([["gestures", [7.86]]]),
    );
    expect(matched[0]!.stale).toBe(false);
    expect(matched[1]!.stale).toBe(true);
  });

  it("never reattaches a stale review to a different lane's block", () => {
    const matched = matchBlockReviews(
      [review("gestures", 7.86)],
      new Map([["tensionShape", [7.86]]]), // wrong lane — no starts for "gestures"
    );
    expect(matched[0]!.stale).toBe(true);
  });
});

describe("startsByLane / indexBlockReviews / reviewKey", () => {
  it("builds a lane -> starts map from block lists", () => {
    const map = startsByLane(
      new Map([["gestures", [{ start_s: 1 }, { start_s: 2 }]]]),
    );
    expect(map.get("gestures")).toEqual([1, 2]);
  });

  it("indexes matched reviews by reviewKey(lane_id, start)", () => {
    const matched = matchBlockReviews(
      [review("gestures", 7.86)],
      new Map([["gestures", [7.86]]]),
    );
    const index = indexBlockReviews(matched);
    expect(index.get(reviewKey("gestures", 7.86))).toBe(matched[0]);
  });
});
