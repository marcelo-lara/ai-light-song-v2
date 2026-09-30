// blockReviews.ts — `PUT /api/block-reviews/<song>`, writing
// reference/human/block_reviews.json. Split out of vite.config.ts (v3.9 item
// 7) with no behaviour change.

import type { IncomingMessage, ServerResponse } from "node:http";

import { readJsonBody, referenceHumanFilePath, writeJsonFile } from "./shared";

// v3.7 item 1 — block_reviews.json is written PER-CLICK by the verdict
// control in the block inspector / lane events panel, mirroring
// lyric_validations.json's pattern (D5.1: a rapid review pass should not need
// a Save button). Each toggle PUTs the FULL `reviews` array and this handler
// replaces the file. The join key is `(lane_id, start)`, never a block id
// (an array position that shifts on every re-run).
export function blockReviewsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "block_reviews.json");
}

const BLOCK_REVIEW_VERDICTS = new Set(["correct", "wrong", "misplaced"]);
const BLOCK_REVIEW_REASONS = new Set(["boundary", "label", "value"]);

export function normalizeBlockReviewsPayload(payload: unknown): {
  schema_version: string;
  song_name: string;
  reviews: Array<{
    lane_id: string;
    start: number;
    verdict: string;
    reason: string | null;
    note: string;
    reviewed_at: string;
  }>;
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Block reviews payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const reviewsIn = Array.isArray(record.reviews) ? record.reviews : null;
  if (!reviewsIn) {
    throw new Error("Block reviews payload must include a reviews array.");
  }
  const reviews = reviewsIn.map((entry: unknown) => {
    const r = (entry && typeof entry === "object" ? entry : {}) as Record<
      string,
      unknown
    >;
    const laneId = String(r.lane_id ?? "").trim();
    if (!laneId) {
      throw new Error("Each block review must include a lane_id.");
    }
    const start = Number(r.start);
    if (!Number.isFinite(start)) {
      throw new Error(`Block review for lane "${laneId}" must include a numeric start.`);
    }
    const verdict = String(r.verdict ?? "");
    if (!BLOCK_REVIEW_VERDICTS.has(verdict)) {
      throw new Error(
        `Block review for lane "${laneId}" verdict must be one of correct, wrong, misplaced.`,
      );
    }
    const reasonRaw = r.reason == null ? null : String(r.reason);
    if (verdict === "correct") {
      if (reasonRaw !== null) {
        throw new Error(`Block review for lane "${laneId}" reason must be null on "correct".`);
      }
    } else if (!reasonRaw || !BLOCK_REVIEW_REASONS.has(reasonRaw)) {
      throw new Error(
        `Block review for lane "${laneId}" reason must be one of boundary, label, value on "${verdict}".`,
      );
    }
    return {
      lane_id: laneId,
      start: Number(start.toFixed(3)),
      verdict,
      reason: verdict === "correct" ? null : reasonRaw,
      note: typeof r.note === "string" ? r.note : "",
      reviewed_at:
        typeof r.reviewed_at === "string" && r.reviewed_at
          ? r.reviewed_at
          : new Date().toISOString(),
    };
  });
  return {
    schema_version: "1.0",
    song_name: String(record.song_name || ""),
    reviews,
  };
}

export async function handleBlockReviews(
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const payload = normalizeBlockReviewsPayload(await readJsonBody(request));
    await writeJsonFile(blockReviewsFilePath(song), payload);
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(payload));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to save block reviews.",
    );
  }
}
