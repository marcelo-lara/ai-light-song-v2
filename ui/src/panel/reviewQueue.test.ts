import { describe, expect, it } from "vitest";

import type { ReviewQueue, ReviewQuestion } from "../data/types";

import {
  partitionReviewQueue,
  questionOptions,
  reviewQuestionKind,
} from "./reviewQueue";

const q = (over: Partial<ReviewQuestion> = {}): ReviewQuestion => ({
  field: "form_family",
  candidates: [
    { value: "verse_chorus", score: 0.41 },
    { value: "aaba", score: 0.62 },
  ],
  evidence_timestamps: [12.3],
  reason_low_confidence: "margin too small",
  leverage: 0.5,
  ...over,
});

describe("reviewQuestionKind", () => {
  it("treats form_family / form_family_vs_genre as whole-song", () => {
    expect(reviewQuestionKind(q({ field: "form_family" }))).toBe("whole_song");
    expect(reviewQuestionKind(q({ field: "form_family_vs_genre" }))).toBe(
      "whole_song",
    );
  });

  it("treats per-section and drop questions as context", () => {
    expect(
      reviewQuestionKind(q({ field: "sections.section-002.form_role" })),
    ).toBe("context");
    expect(reviewQuestionKind(q({ field: "drops.timed_location" }))).toBe(
      "context",
    );
  });
});

describe("questionOptions", () => {
  it("stringifies, drops blanks, and sorts by score desc", () => {
    expect(
      questionOptions(
        q({
          candidates: [
            { value: "a", score: 0.1 },
            { value: null, score: 0.9 },
            { value: "b", score: 0.5 },
          ],
        }),
      ),
    ).toEqual([
      { value: "b", score: 0.5 },
      { value: "a", score: 0.1 },
    ]);
  });
});

describe("partitionReviewQueue", () => {
  it("splits whole-song from context and ranks each by leverage desc", () => {
    const queue: ReviewQueue = {
      schema_version: "1.1",
      song_name: "_test_song",
      direction_of_flow: null,
      open_question_count: 3,
      questions: [
        q({ field: "sections.section-001.form_role", leverage: 0.2 }),
        q({ field: "form_family", leverage: 0.9 }),
        q({ field: "form_family_vs_genre", leverage: 0.3 }),
        q({ field: "drops.timed_location", leverage: 0.7 }),
      ],
    };
    const { wholeSong, context } = partitionReviewQueue(queue);
    expect(wholeSong.map((x) => x.field)).toEqual([
      "form_family",
      "form_family_vs_genre",
    ]);
    expect(context.map((x) => x.field)).toEqual([
      "drops.timed_location",
      "sections.section-001.form_role",
    ]);
  });

  it("sorts a missing leverage last", () => {
    const queue: ReviewQueue = {
      schema_version: "1.1",
      song_name: "s",
      direction_of_flow: null,
      open_question_count: 2,
      questions: [
        q({ field: "form_family", leverage: null }),
        q({ field: "form_family_vs_genre", leverage: 0.1 }),
      ],
    };
    expect(
      partitionReviewQueue(queue).wholeSong.map((x) => x.field),
    ).toEqual(["form_family_vs_genre", "form_family"]);
  });
});
