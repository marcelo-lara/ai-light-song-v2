// blockReviewMatch.ts — v3.7 item 1: the lane set block reviews apply to, and
// the staleness match against the CURRENT run's emitted blocks.
//
// A review whose `start` matches no block of its `lane_id` in the current run
// within ±0.25 s (the repo's own beat-alignment tolerance) is stale: shown as
// stale in the lane and skipped by the experiments/truth_common scorer, never
// silently dropped and never silently re-attached to a neighbouring block
// (docs/product-refinement-v3.7.md item 1).

import type { BlockReview, BlockReviewMatched } from "./types";

/**
 * Every lane carrying an `experiment` field in
 * ../timeline/laneState.ts (segmentSeeds, vocalPhrases, allin1Posterior,
 * rhythmDrumIoi, rhythmStemAutocorr, rhythmVocalOnsets, energyLevel,
 * tensionShape, character, vocalTranscription), plus `gestures` — shipped,
 * and the lane the gestures-precision issue names. NOT moisesSections /
 * moisesLyrics (reference lanes, truth or authored input) and not a
 * human-authored lane — those are truth, not claims to be judged.
 */
export const REVIEWABLE_LANE_IDS: ReadonlySet<string> = new Set([
  "segmentSeeds",
  "vocalPhrases",
  "allin1Posterior",
  "rhythmDrumIoi",
  "rhythmStemAutocorr",
  "rhythmVocalOnsets",
  "energyLevel",
  "tensionShape",
  "character",
  "vocalTranscription",
  "gestures",
]);

/** The repo's own beat-alignment tolerance (docs/product-refinement-v3.7.md item 1). */
export const BLOCK_REVIEW_STALE_TOLERANCE_S = 0.25;

/**
 * Annotate every review with whether it matches a block the current run
 * emitted for its `lane_id`. `currentStartsByLane` carries only the
 * `start_s` values of blocks currently on the timeline for each lane (not the
 * blocks themselves) — the match is on `(lane_id, start)`, never on a block
 * id (an array position that shifts on every re-run).
 */
export function matchBlockReviews(
  reviews: readonly BlockReview[],
  currentStartsByLane: ReadonlyMap<string, readonly number[]>,
  toleranceS: number = BLOCK_REVIEW_STALE_TOLERANCE_S,
): BlockReviewMatched[] {
  return reviews.map((review) => {
    const starts = currentStartsByLane.get(review.lane_id) ?? [];
    const stale = !starts.some((s) => Math.abs(s - review.start) <= toleranceS);
    return { ...review, stale };
  });
}

/** Build `currentStartsByLane` from the lane blocks actually on the timeline. */
export function startsByLane(
  blocksByLane: ReadonlyMap<string, readonly { start_s: number }[]>,
): Map<string, number[]> {
  const out = new Map<string, number[]>();
  for (const [laneId, blocks] of blocksByLane) {
    out.set(laneId, blocks.map((b) => b.start_s));
  }
  return out;
}

/**
 * Index matched reviews by `(lane_id, start)` for O(1) per-block lookup —
 * `start` rounded to 3 decimals, the same convention the file itself uses.
 */
export function indexBlockReviews(
  reviews: readonly BlockReviewMatched[],
): Map<string, BlockReviewMatched> {
  const out = new Map<string, BlockReviewMatched>();
  for (const review of reviews) {
    out.set(reviewKey(review.lane_id, review.start), review);
  }
  return out;
}

export function reviewKey(laneId: string, start: number): string {
  return `${laneId}::${start.toFixed(3)}`;
}
