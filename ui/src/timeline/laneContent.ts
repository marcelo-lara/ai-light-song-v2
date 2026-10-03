// laneContent.ts — the SparseBlock type, the lane registry and dispatch
// (buildLaneBlocks). The per-lane `*Content` adapters live in
// laneContent/<family>.ts (v3.9 item 7 split) and are re-exported below, so
// every existing importer of this module is unaffected.
//
// Ported from the previous app's src/lib/timeline/sparseContent.js. Each adapter is a pure
// function from a loaded artifact payload to an ordered `SparseBlock[]`; the
// blocks carry everything the item-6 block inspector needs (`label`,
// `laneLabel`, `caption`, `reference`, `detail`, `summary`) plus the raw source
// row so the inspector's "show raw" disclosure works.
//
// `buildLaneBlocks(laneId, sources)` dispatches to the right adapter; the
// individual adapters are exported for unit tests against artifact fixtures.

import type {
  BlockReviewsFile,
  EventTimeline,
  HumanHintsFile,
  HumanSegmentsFile,
  MoisesSegmentsFile,
  PendingProposalsFile,
  SectionRow,
  SegmentationSection,
  VerdictFile,
} from "../data/types";
import { REVIEWABLE_LANE_IDS, matchBlockReviews } from "../data/blockReviewMatch";
import type {
  CharacterFile,
  MoisesLyricsFile,
  VocalTranscriptionFile,
  VocalPhrasesFile,
  Allin1PosteriorFile,
  StemPresenceSectionsFile,
  VocalCadenceFile,
  ArrangementStateFile,
  WhisperxVadFile,
  ClapEventsFile,
  KickCheckFile,
  CrashCheckFile,
  FilterSweepFile,
  PhrasesFile,
  SectionNamesFile,
} from "../data/sparseArtifacts";

import {
  humanHintsContent,
  llmPendingProposalsContent,
  moisesLyricsContent,
} from "./laneContent/referenceHints";
import {
  humanSectionsContent,
  moisesSectionsContent,
  allin1SectionsContent,
  sectionsContent,
  allin1PosteriorContent,
  stemPresenceSectionsContent,
  arrangementStateContent,
  sectionNamesContent,
} from "./laneContent/sections";
import {
  vocalTranscriptionContent,
  vocalCadenceContent,
  vocalPhrasesContent,
  whisperxVadContent,
} from "./laneContent/vocal";
import {
  characterContent,
  gesturesContent,
  filterSweepContent,
  phrasesContent,
} from "./laneContent/characterGestures";
import {
  clapEventsContent,
  kickCheckContent,
  crashCheckContent,
} from "./laneContent/drumHitChecks";
import { verdictChecksContent } from "./laneContent/verdicts";
import { formatRange } from "./laneContent/shared";

export {
  humanHintsContent,
  llmPendingProposalsContent,
  moisesLyricsContent,
  humanSectionsContent,
  moisesSectionsContent,
  allin1SectionsContent,
  sectionsContent,
  allin1PosteriorContent,
  stemPresenceSectionsContent,
  arrangementStateContent,
  sectionNamesContent,
  vocalTranscriptionContent,
  vocalCadenceContent,
  vocalPhrasesContent,
  whisperxVadContent,
  characterContent,
  gesturesContent,
  filterSweepContent,
  phrasesContent,
  clapEventsContent,
  kickCheckContent,
  crashCheckContent,
  verdictChecksContent,
  formatRange,
};

export interface SparseBlock {
  id: string;
  start_s: number;
  end_s: number;
  /** default block label */
  label: string;
  /** label variant drawn when the block is wide (e.g. chord + roman numeral) */
  wideLabel?: string;
  /**
   * Optional per-block tint id, overriding the lane's own tint. Used by the
   * Drop Proposals lane to colour a candidate that already matches a human
   * label differently from one still needing a decision.
   */
  tintId?: string;
  /**
   * v3.4 item 5 — the Moises lyric-token id this block represents, when the
   * block is a validatable **word** token (not a `<SOL>`/`<EOL>` marker). The
   * Moises Lyrics events panel renders a ✔ validation button only for a block
   * carrying both this and `lyricValidatable: true`.
   */
  lyricTokenId?: number;
  lyricValidatable?: boolean;
  laneLabel: string;
  /** Optional hover text for the lane (`SparseLane` sets it as the native tooltip on a lane that opts in). */
  tooltip?: string;
  caption: string;
  reference: string;
  detail: string;
  summary: string;
  /** original artifact row — surfaced by the inspector's raw disclosure */
  raw: unknown;
  /**
   * v3.7 item 1 — set only when a `reference/human/block_reviews.json` row
   * matches this block's `(lane_id, start)` within tolerance (never a stale
   * one — a stale review matches no current block, so it never tints one).
   * `tintId` is overridden to the matching `blockReview*` id at the same
   * time, by `applyBlockReviewTint` below.
   */
  reviewVerdict?: "correct" | "wrong" | "misplaced";
}

// -- dispatch -------------------------------------------------------------

export interface LaneContentSources {
  humanHints?: HumanHintsFile | null;
  llmPendingProposals?: PendingProposalsFile | null;
  /** v3.11 item 24 — reference/pre-analysis/verdict.json; the Verdict Checks lane. */
  verdictFile?: VerdictFile | null;
  humanSections?: HumanSegmentsFile | null;
  moisesSections?: MoisesSegmentsFile | null;
  moisesLyrics?: MoisesLyricsFile | null;
  /** v3.4 item 5 — read-time overlay: Moises word-token ids the operator has
   *  hand-verified (from reference/human/lyric_validations.json). */
  lyricValidations?: ReadonlySet<number> | null;
  sections?: readonly SectionRow[];
  sectionSegmentation?: readonly SegmentationSection[];
  character?: CharacterFile | null;
  vocalTranscription?: VocalTranscriptionFile | null;
  vocalPhrases?: VocalPhrasesFile | null;
  allin1Posterior?: Allin1PosteriorFile | null;
  stemPresenceSections?: StemPresenceSectionsFile | null;
  vocalCadence?: VocalCadenceFile | null;
  arrangementState?: ArrangementStateFile | null;
  whisperxVad?: WhisperxVadFile | null;
  gestures?: EventTimeline | null;
  clapEvents?: ClapEventsFile | null;
  kickCheck?: KickCheckFile | null;
  crashCheck?: CrashCheckFile | null;
  filterSweep?: FilterSweepFile | null;
  phrases?: PhrasesFile | null;
  sectionNames?: SectionNamesFile | null;
  /** v3.7 item 1 — reference/human/block_reviews.json, unfiltered; tinting is
   *  applied per lane inside `buildLaneBlocks`. */
  blockReviews?: BlockReviewsFile | null;
}

/** the sparse (block) lane ids handled by this module, in registry order */
export const SPARSE_LANE_IDS = [
  "humanHints",
  "llmPendingProposals",
  "verdictChecks",
  "humanSections",
  "moisesSections",
  "allin1Sections",
  "moisesLyrics",
  "arrangementState",
  "vocalPhrases",
  "allin1Posterior",
  "stemPresenceSections",
  "vocalCadence",
  "whisperxVad",
  "gestures",
  "clapEvents",
  "kickCheck",
  "crashCheck",
  "filterSweep",
  "phrases",
  "sectionNames",
  "sections",
  "character",
  "vocalTranscription",
] as const;

export type SparseLaneId = (typeof SPARSE_LANE_IDS)[number];

/**
 * v3.7 item 1 — overrides a reviewed block's `tintId` to a fixed
 * green/red/amber verdict colour, so coverage reads on the timeline canvas
 * without opening the inspector. A review whose `start` matches no block in
 * `blocks` (a stale review — see `../data/blockReviewMatch.ts`) tints
 * nothing: there is no block for it to attach to, and it is never
 * re-attached to the nearest one.
 */
function applyBlockReviewTint(
  blocks: SparseBlock[],
  laneId: string,
  file: BlockReviewsFile | null | undefined,
): SparseBlock[] {
  if (!file?.reviews.length || !REVIEWABLE_LANE_IDS.has(laneId)) return blocks;
  const laneReviews = file.reviews.filter((r) => r.lane_id === laneId);
  if (!laneReviews.length) return blocks;
  const matched = matchBlockReviews(
    laneReviews,
    new Map([[laneId, blocks.map((b) => b.start_s)]]),
  );
  const byStart = new Map(
    matched.filter((r) => !r.stale).map((r) => [Number(r.start.toFixed(3)), r]),
  );
  if (!byStart.size) return blocks;
  return blocks.map((b) => {
    const review = byStart.get(Number(b.start_s.toFixed(3)));
    if (!review) return b;
    const tintId =
      review.verdict === "correct"
        ? "blockReviewCorrect"
        : review.verdict === "wrong"
          ? "blockReviewWrong"
          : "blockReviewMisplaced";
    return { ...b, tintId, reviewVerdict: review.verdict };
  });
}

export function buildLaneBlocks(
  laneId: string,
  s: LaneContentSources,
): SparseBlock[] {
  return applyBlockReviewTint(buildLaneBlocksRaw(laneId, s), laneId, s.blockReviews);
}

function buildLaneBlocksRaw(
  laneId: string,
  s: LaneContentSources,
): SparseBlock[] {
  switch (laneId) {
    case "humanHints":
      return humanHintsContent(s.humanHints ?? null);
    case "llmPendingProposals":
      return llmPendingProposalsContent(s.llmPendingProposals ?? null);
    case "verdictChecks":
      return verdictChecksContent(
        s.verdictFile ?? null,
        s.sections ?? [],
        s.llmPendingProposals ?? null,
      );
    case "humanSections":
      return humanSectionsContent(s.humanSections ?? null);
    case "moisesSections":
      return moisesSectionsContent(s.moisesSections ?? null);
    case "allin1Sections":
      return allin1SectionsContent(s.sectionSegmentation ?? []);
    case "moisesLyrics":
      return moisesLyricsContent(s.moisesLyrics ?? null, s.lyricValidations ?? null);
    case "arrangementState":
      return arrangementStateContent(s.arrangementState ?? null);
    case "vocalPhrases":
      return vocalPhrasesContent(s.vocalPhrases ?? null);
    case "allin1Posterior":
      return allin1PosteriorContent(s.allin1Posterior ?? null);
    case "stemPresenceSections":
      return stemPresenceSectionsContent(s.stemPresenceSections ?? null);
    case "vocalCadence":
      return vocalCadenceContent(s.vocalCadence ?? null);
    case "whisperxVad":
      return whisperxVadContent(s.whisperxVad ?? null);
    case "gestures":
      return gesturesContent(s.gestures ?? null);
    case "clapEvents":
      return clapEventsContent(s.clapEvents ?? null);
    case "kickCheck":
      return kickCheckContent(s.kickCheck ?? null);
    case "crashCheck":
      return crashCheckContent(s.crashCheck ?? null);
    case "filterSweep":
      return filterSweepContent(s.filterSweep ?? null);
    case "phrases":
      return phrasesContent(s.phrases ?? null);
    case "sectionNames":
      return sectionNamesContent(s.sectionNames ?? null);
    case "sections":
      return sectionsContent(s.sections ?? [], s.sectionSegmentation ?? []);
    case "character":
      return characterContent(s.character ?? null);
    case "vocalTranscription":
      return vocalTranscriptionContent(s.vocalTranscription ?? null);
    default:
      return [];
  }
}
