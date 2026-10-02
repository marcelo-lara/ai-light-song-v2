// useHumanOverrides.ts — the four writable `reference/human/*.json` files
// (human hints, sections, lyric validations, block reviews):
// their server-normalised overrides and every save/commit handler that
// writes them. Split out of App.tsx (v3.9 item 7) with no behaviour change.
//
// Every handler here deliberately does NOT `reloadSong()` — a full reload
// reseeds every artifact to loading/null, collapsing beats -> coords ->
// timelineW to zero and resetting the scroller's zoom/scroll to song start on
// every hint drag-commit and panel Save. Instead each save applies the
// server-normalised result in place via its own override state.

import { useCallback, useMemo, useRef, useState } from "react";

import type {
  BlockReview,
  BlockReviewsFile,
  HumanHintsFile,
  HumanSegmentsFile,
  LyricValidationsFile,
} from "../data/types";
import { buildHumanHintsPayload, saveHumanHints } from "../data/saveHumanHints";
import { buildHumanSectionsPayload, saveHumanSections } from "../data/saveHumanSections";
import {
  buildLyricValidationsPayload,
  saveLyricValidations,
} from "../data/saveLyricValidations";
import { buildBlockReviewsPayload, saveBlockReviews } from "../data/saveBlockReviews";
import { draftToHint, hintToDraft } from "../panel/hintDraft";
import { draftToSegment, segmentToDraft } from "../panel/segmentDraft";

export interface HumanOverridesInputs {
  song: string | null;
  humanHintsData: HumanHintsFile | null | undefined;
  humanSectionsData: HumanSegmentsFile | null | undefined;
  lyricValidationsData: LyricValidationsFile | null | undefined;
  blockReviewsData: BlockReviewsFile | null | undefined;
}

export type HumanOverridesResult = ReturnType<typeof useHumanOverrides>;

export function useHumanOverrides({
  song,
  humanHintsData,
  humanSectionsData,
  lyricValidationsData,
  blockReviewsData,
}: HumanOverridesInputs) {
  const [hintsOverride, setHintsOverride] = useState<HumanHintsFile | null>(null);
  const [sectionsOverride, setSectionsOverride] = useState<HumanSegmentsFile | null>(null);
  // v3.4 item 5: the server-normalised lyric_validations.json returned by a
  // per-click ✔ toggle, applied in place.
  const [lyricValidationsOverride, setLyricValidationsOverride] =
    useState<LyricValidationsFile | null>(null);
  // Guards a double-fire from one ✔ click (D5.1) at the write layer too.
  const savingLyricRef = useRef(false);
  // v3.7 item 1: the server-normalised block_reviews.json returned by a
  // per-click verdict, applied in place.
  const [blockReviewsOverride, setBlockReviewsOverride] = useState<BlockReviewsFile | null>(null);
  // Guards a double-fire from one verdict click at the write layer too.
  const savingReviewRef = useRef(false);

  const humanHintsFile = hintsOverride ?? humanHintsData ?? null;
  const humanSectionsFile = sectionsOverride ?? humanSectionsData ?? null;
  const lyricValidationsFile = lyricValidationsOverride ?? lyricValidationsData ?? null;
  const validatedLyricIds = useMemo(
    () => new Set(lyricValidationsFile?.validated_ids ?? []),
    [lyricValidationsFile],
  );
  const blockReviewsFile = blockReviewsOverride ?? blockReviewsData ?? null;

  // item 7 (ui-issues finding 7): the server-normalised file returned by the
  // save flows into `hintsOverride`, which authoritatively updates the Human
  // Hints lane in place.
  const handleSaveHints = useCallback((file: HumanHintsFile) => {
    setHintsOverride(file);
  }, []);

  // Same reasoning as `handleSaveHints`, for Human Sections.
  const handleSaveSegments = useCallback((file: HumanSegmentsFile) => {
    setSectionsOverride(file);
  }, []);

  // v3.4 item 5 (D5.1): a ✔ toggle in the Moises Lyrics panel persists
  // immediately — no Save button. Sends the FULL validated-id list; the handler
  // replaces the file. Applies the server-normalised result in place.
  // `savingLyricRef` drops a second toggle that lands while a write is still
  // in flight.
  const handleToggleLyricValidation = useCallback(
    async (tokenId: number, nextValidated: boolean) => {
      if (!song || savingLyricRef.current) return;
      savingLyricRef.current = true;
      try {
        const ids = new Set(lyricValidationsFile?.validated_ids ?? []);
        if (nextValidated) ids.add(tokenId);
        else ids.delete(tokenId);
        const payload = buildLyricValidationsPayload(
          lyricValidationsFile?.song_name || song,
          [...ids],
        );
        const written = await saveLyricValidations(song, payload);
        setLyricValidationsOverride(written);
      } finally {
        savingLyricRef.current = false;
      }
    },
    [song, lyricValidationsFile],
  );

  // v3.7 item 1: a verdict click persists immediately — no Save button
  // (mirrors `handleToggleLyricValidation`'s per-click pattern, D5.1). Sends
  // the FULL reviews array (merging the new/changed one into whatever is
  // already on disk); the handler replaces the file. Applies the
  // server-normalised result in place. `savingReviewRef` drops a second
  // verdict click that lands while a write is still in flight.
  const handleSaveBlockReview = useCallback(
    async (review: BlockReview) => {
      if (!song || savingReviewRef.current) return;
      savingReviewRef.current = true;
      try {
        const current = (blockReviewsFile?.reviews ?? []).filter(
          (r) => !(r.lane_id === review.lane_id && r.start === review.start),
        );
        const payload = buildBlockReviewsPayload(
          blockReviewsFile?.song_name || song,
          [...current, review],
        );
        const written = await saveBlockReviews(song, payload);
        setBlockReviewsOverride(written);
      } finally {
        savingReviewRef.current = false;
      }
    },
    [song, blockReviewsFile],
  );

  // item 10: persist a humanHints block's new start/end after a timeline drag.
  // Builds the full file from the current hints (only the dragged one's times
  // change) through the same validator/PUT the hint editor uses, then feeds the
  // server-normalised result through `handleSaveHints`. Rejects on failure so
  // `SparseLane` reverts its optimistic preview.
  const handleCommitHintTimes = useCallback(
    async (id: string, start: number, end: number) => {
      if (!song) throw new Error("No song selected.");
      const current = humanHintsFile?.human_hints ?? [];
      const drafts = current.map((hint) => {
        const draft = hintToDraft(hint);
        return hint.id === id
          ? { ...draft, start: String(start), end: String(end) }
          : draft;
      });
      const payload = buildHumanHintsPayload(
        humanHintsFile?.song_name || song,
        drafts.map(draftToHint),
      );
      const written = await saveHumanHints(song, payload);
      handleSaveHints(written);
    },
    [song, humanHintsFile, handleSaveHints],
  );

  // Same reasoning as `handleCommitHintTimes`, for Human Sections. Segments
  // carry no persisted id — the block's synthesized `segment-NNN` id is
  // matched back to its array position (assigned in the same order by
  // `humanSectionsContent`).
  const handleCommitSegmentTimes = useCallback(
    async (id: string, start: number, end: number) => {
      if (!song) throw new Error("No song selected.");
      const current = humanSectionsFile ?? [];
      const drafts = current.map((segment, i) => {
        const draft = segmentToDraft(segment, i);
        return draft.id === id
          ? { ...draft, start: String(start), end: String(end) }
          : draft;
      });
      const payload = buildHumanSectionsPayload(drafts.map(draftToSegment));
      const written = await saveHumanSections(song, payload);
      handleSaveSegments(written);
    },
    [song, humanSectionsFile, handleSaveSegments],
  );

  const resetOverrides = useCallback(() => {
    setHintsOverride(null);
    setSectionsOverride(null);
    setLyricValidationsOverride(null);
    setBlockReviewsOverride(null);
  }, []);

  return {
    humanHintsFile,
    humanSectionsFile,
    lyricValidationsFile,
    validatedLyricIds,
    blockReviewsFile,
    handleSaveHints,
    handleSaveSegments,
    handleToggleLyricValidation,
    handleSaveBlockReview,
    handleCommitHintTimes,
    handleCommitSegmentTimes,
    resetOverrides,
  };
}
