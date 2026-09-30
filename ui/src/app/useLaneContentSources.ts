// useLaneContentSources.ts — assembles the `LaneContentSources` every sparse
// lane's `buildLaneBlocks` call reads from. Split out of App.tsx (v3.9 item
// 7) with no behaviour change: same fields, same memo dependency list.

import { useMemo } from "react";

import type { SongArtifacts } from "../data/useSong";
import type {
  BlockReviewsFile,
  HumanHintsFile,
  HumanSegmentsFile,
  PendingProposalsFile,
  SectionRow,
  SegmentationSection,
} from "../data/types";
import type { LaneContentSources } from "../timeline/laneContent";

export interface LaneContentSourcesInputs {
  humanHintsFile: HumanHintsFile | null;
  pendingProposalsFileForLane: PendingProposalsFile | null;
  humanSectionsFile: HumanSegmentsFile | null;
  artifacts: SongArtifacts;
  validatedLyricIds: ReadonlySet<number>;
  sections: readonly SectionRow[];
  sectionSegmentation: readonly SegmentationSection[];
  blockReviewsFile: BlockReviewsFile | null;
}

export function useLaneContentSources({
  humanHintsFile,
  pendingProposalsFileForLane,
  humanSectionsFile,
  artifacts,
  validatedLyricIds,
  sections,
  sectionSegmentation,
  blockReviewsFile,
}: LaneContentSourcesInputs): LaneContentSources {
  return useMemo<LaneContentSources>(
    () => ({
      humanHints: humanHintsFile,
      llmPendingProposals: pendingProposalsFileForLane,
      humanSections: humanSectionsFile,
      moisesSections: artifacts.moisesSections.data,
      moisesLyrics: artifacts.moisesLyrics.data,
      lyricValidations: validatedLyricIds,
      arrangementState: artifacts.arrangementState.data,
      vocalPhrases: artifacts.vocalPhrases.data,
      allin1Posterior: artifacts.allin1Posterior.data,
      stemPresenceSections: artifacts.stemPresenceSections.data,
      vocalCadence: artifacts.vocalCadence.data,
      rhythmDrumIoi: artifacts.rhythmDrumIoi.data,
      rhythmStemAutocorr: artifacts.rhythmStemAutocorr.data,
      rhythmVocalOnsets: artifacts.rhythmVocalOnsets.data,
      energyLevel: artifacts.energyLevel.data,
      tensionShape: artifacts.tensionShape.data,
      segmentSeeds: artifacts.humanSectionsSeed.data,
      whisperxVad: artifacts.whisperxVad.data,
      gestures: artifacts.eventTimeline.data,
      character: artifacts.character.data,
      vocalTranscription: artifacts.vocalTranscription.data,
      clapEvents: artifacts.clapEvents.data,
      kickCheck: artifacts.kickCheck.data,
      crashCheck: artifacts.crashCheck.data,
      sections,
      sectionSegmentation,
      blockReviews: blockReviewsFile,
    }),
    [
      humanHintsFile,
      pendingProposalsFileForLane,
      humanSectionsFile,
      artifacts.moisesSections.data,
      artifacts.moisesLyrics.data,
      validatedLyricIds,
      artifacts.arrangementState.data,
      artifacts.vocalPhrases.data,
      artifacts.allin1Posterior.data,
      artifacts.stemPresenceSections.data,
      artifacts.vocalCadence.data,
      artifacts.rhythmDrumIoi.data,
      artifacts.rhythmStemAutocorr.data,
      artifacts.rhythmVocalOnsets.data,
      artifacts.energyLevel.data,
      artifacts.tensionShape.data,
      artifacts.whisperxVad.data,
      artifacts.eventTimeline.data,
      artifacts.character.data,
      artifacts.vocalTranscription.data,
      artifacts.clapEvents.data,
      artifacts.kickCheck.data,
      artifacts.crashCheck.data,
      sections,
      sectionSegmentation,
      blockReviewsFile,
    ],
  );
}
