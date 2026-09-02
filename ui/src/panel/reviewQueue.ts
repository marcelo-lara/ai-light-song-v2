// Pure helpers for the review-queue editor (item 7 / Story 8.10).
//
// `review_queue.json` is a flat list of low-confidence questions the analyzer
// wants a human to settle. Two kinds matter to this panel:
//   - whole-song questions (`form_family`, `form_family_vs_genre`) — answerable
//     here; the answer is dispositioned into `song_facts.json`.
//   - per-section `form_role` and `drops.*` questions — shown read-only for
//     context; they are answered by editing `human_hints.json` (Story 8.8).

import { WHOLE_SONG_FACT_FIELDS } from "../data/saveSongFacts";
import type { ReviewQuestion, ReviewQueue } from "../data/types";

export type ReviewQuestionKind = "whole_song" | "context";

/** Classify a question by its dotted `field` path. */
export function reviewQuestionKind(question: ReviewQuestion): ReviewQuestionKind {
  return (WHOLE_SONG_FACT_FIELDS as readonly string[]).includes(question.field)
    ? "whole_song"
    : "context";
}

export interface AnswerOption {
  value: string;
  score: number;
}

/**
 * Candidate answers for a question, highest score first, blanks removed.
 * `value` is stringified so it can back a `<select>`.
 */
export function questionOptions(question: ReviewQuestion): AnswerOption[] {
  return question.candidates
    .map((candidate) => ({
      value:
        candidate.value === null || candidate.value === undefined
          ? ""
          : String(candidate.value),
      score: candidate.score,
    }))
    .filter((option) => option.value !== "")
    .sort((left, right) => right.score - left.score);
}

export interface PartitionedReviewQueue {
  /** answerable here; ranked by leverage (highest first) */
  wholeSong: ReviewQuestion[];
  /** read-only context; ranked by leverage (highest first) */
  context: ReviewQuestion[];
}

/** Split + rank the queue's questions. Missing `leverage` sorts last. */
export function partitionReviewQueue(queue: ReviewQueue): PartitionedReviewQueue {
  const ranked = [...queue.questions].sort(
    (left, right) => (right.leverage ?? -Infinity) - (left.leverage ?? -Infinity),
  );
  return {
    wholeSong: ranked.filter((q) => reviewQuestionKind(q) === "whole_song"),
    context: ranked.filter((q) => reviewQuestionKind(q) === "context"),
  };
}
