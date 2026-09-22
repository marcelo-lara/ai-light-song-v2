// Client for `PUT /api/block-reviews/<song>` — mirrors saveLyricValidations.ts:
// per-click, not explicit-Save (v3.7 item 1, following D5.1's "a rapid pass
// should not need a Save button"). Each verdict click sends the FULL `reviews`
// array (the client already holds the merged state) and the dev-server handler
// replaces the file.
//
// `reference/human/block_reviews.json` records the operator's three-state
// verdict on a claim-bearing lane's emitted block, joined by `(lane_id, start)`
// — never a block id, which is an array position and shifts on every re-run.
// The operator is the only producer; nothing in `src/` or `mcp/` reads the
// file, and there is no `field_sources` / `source` attribution machinery
// (the human-hints-file-stays-simple rule).

import { artifactPaths } from "./paths";
import type {
  BlockReview,
  BlockReviewReason,
  BlockReviewsFile,
  BlockReviewVerdict,
} from "./types";

const VERDICTS: readonly BlockReviewVerdict[] = ["correct", "wrong", "misplaced"];
const REASONS: readonly BlockReviewReason[] = ["boundary", "label", "value"];

/**
 * Validate + normalise reviews into the on-disk payload shape.
 *
 * - `lane_id` and `start` are required; `start` is rounded to 3 decimals (the
 *   join-key convention).
 * - `verdict` must be one of the fixed vocabulary, or this throws.
 * - `reason` must be `null` on `correct`, and non-null (one of the fixed
 *   vocabulary) on `wrong` / `misplaced` — never a silently-defaulted reason.
 * - `note` is free text, never validated.
 */
export function buildBlockReviewsPayload(
  songName: string,
  reviews: readonly BlockReview[],
): BlockReviewsFile {
  const normalized: BlockReview[] = reviews.map((review) => {
    const laneId = String(review.lane_id || "").trim();
    if (!laneId) {
      throw new Error("Each block review must reference a lane_id.");
    }
    if (!Number.isFinite(review.start)) {
      throw new Error(`Block review for lane "${laneId}" must carry a numeric start.`);
    }
    if (!VERDICTS.includes(review.verdict)) {
      throw new Error(
        `Block review for lane "${laneId}" verdict must be one of ${VERDICTS.join(", ")}.`,
      );
    }
    if (review.verdict === "correct") {
      if (review.reason != null) {
        throw new Error(`Block review for lane "${laneId}" reason must be null on "correct".`);
      }
    } else if (!review.reason || !REASONS.includes(review.reason)) {
      throw new Error(
        `Block review for lane "${laneId}" reason is required (one of ${REASONS.join(", ")}) on "${review.verdict}".`,
      );
    }
    return {
      lane_id: laneId,
      start: Number(review.start.toFixed(3)),
      verdict: review.verdict,
      reason: review.verdict === "correct" ? null : review.reason,
      note: typeof review.note === "string" ? review.note : "",
      reviewed_at: review.reviewed_at || new Date().toISOString(),
    };
  });
  return {
    schema_version: "1.0",
    song_name: String(songName || ""),
    reviews: normalized,
  };
}

/**
 * PUT the full reviews array. Resolves with the server-normalised file (the
 * new source of truth); rejects with the server's error text on a non-2xx
 * response.
 */
export async function saveBlockReviews(
  song: string,
  payload: BlockReviewsFile,
  fetchImpl: typeof fetch = fetch,
): Promise<BlockReviewsFile> {
  const response = await fetchImpl(
    `/api/block-reviews/${encodeURIComponent(song)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      message.trim() ||
        `Failed to save ${artifactPaths.blockReviews(song)} (${response.status}).`,
    );
  }

  return (await response.json()) as BlockReviewsFile;
}
