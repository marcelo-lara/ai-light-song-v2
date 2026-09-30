// AppRightPanels.tsx — every RightPanel-shell surface: the block inspector,
// the lane-events panel, the hint/segment editors, the review queue and the
// pending-proposals queue. Split out of App.tsx (v3.9 item 7) with no
// behaviour change. Takes the hook-result objects (`panel`, `overrides`,
// `proposals`, `viewport`) directly rather than flattening every field into
// its own prop — they are already the cohesive unit App.tsx assembled them
// as, and re-destructuring here would only re-scatter that grouping.

import {
  BlockInspector,
  HintEditorPanel,
  SegmentEditorPanel,
  LaneEventsPanel,
  PendingProposalsPanel,
  ReviewQueuePanel,
  RightPanel,
} from "../panel";
import { REVIEWABLE_LANE_IDS, reviewKey } from "../data/blockReviewMatch";
import type { BlockReviewMatched, HumanHintsFile, HumanSegmentsFile, BlockEnergyFile } from "../data/types";
import type { SparseBlock } from "../timeline/laneContent";
import type { DrawerView } from "./useDrawer";
import type { HumanOverridesResult } from "./useHumanOverrides";
import type { PanelStateResult } from "./usePanelState";
import type { ProposalsState } from "./useProposals";
import type { TimelineViewport } from "./useTimelineViewport";

export interface EventsPanelProps {
  laneId: string;
  laneLabel: string;
  experiment: string | undefined;
  blocks: SparseBlock[];
  status: "idle" | "loading" | "ready" | "error";
  error: string | null;
}

export function AppRightPanels({
  activeView,
  song,
  panel,
  overrides,
  proposals,
  viewport,
  currentTime,
  isPlaying,
  humanHintsFile,
  humanSectionsFile,
  blockEnergyFile,
  validatedLyricIds,
  eventsPanel,
  blockReviewIndexFor,
  onSelectBlock,
  openPendingProposal,
  setActiveView,
}: {
  activeView: DrawerView;
  song: string | null;
  panel: PanelStateResult;
  overrides: HumanOverridesResult;
  proposals: ProposalsState;
  viewport: Pick<TimelineViewport, "scrollTimelineToTime" | "seekToTimeAlways">;
  currentTime: number;
  isPlaying: boolean;
  humanHintsFile: HumanHintsFile | null;
  humanSectionsFile: HumanSegmentsFile | null;
  blockEnergyFile: BlockEnergyFile | null;
  validatedLyricIds: ReadonlySet<number>;
  eventsPanel: EventsPanelProps | null;
  blockReviewIndexFor: (laneId: string) => Map<string, BlockReviewMatched> | null;
  onSelectBlock: (block: SparseBlock) => void;
  openPendingProposal: (reference: string) => void;
  setActiveView: (view: DrawerView) => void;
}): React.JSX.Element {
  return (
    <>
      {activeView === "timeline" && song && panel.panelMode === "inspector" && panel.selection && (
        <RightPanel
          open
          onClose={panel.closePanel}
          aria-label="Block inspector"
          header={<span className="app-rightpanel__kicker">{panel.selection.laneLabel}</span>}
        >
          <BlockInspector
            selection={panel.selection}
            onCreateHint={panel.handleCreateHintFromSelection}
            onCreateSection={panel.handleCreateSectionFromSelection}
            blockReview={
              REVIEWABLE_LANE_IDS.has(panel.selection.laneId)
                ? {
                    review: blockReviewIndexFor(panel.selection.laneId)?.get(
                      reviewKey(panel.selection.laneId, Number(panel.selection.start_s.toFixed(3))),
                    ),
                    onSave: overrides.handleSaveBlockReview,
                  }
                : undefined
            }
          />
        </RightPanel>
      )}

      {activeView === "timeline" && song && eventsPanel && (
        <LaneEventsPanel
          laneId={eventsPanel.laneId}
          laneLabel={eventsPanel.laneLabel}
          experiment={eventsPanel.experiment}
          blocks={eventsPanel.blocks}
          status={eventsPanel.status}
          error={eventsPanel.error}
          currentTime={currentTime}
          playing={isPlaying}
          onClose={panel.closePanel}
          onSelectBlock={(block) => {
            onSelectBlock(block);
            if (eventsPanel.laneId === "llmPendingProposals") {
              openPendingProposal(block.reference);
            }
          }}
          onSelectMarker={panel.handleSelectMarker}
          blockEnergy={
            eventsPanel.laneId === "humanHints"
              ? { file: blockEnergyFile, onSave: overrides.handleSaveBlockEnergy }
              : undefined
          }
          sectionRating={
            eventsPanel.laneId === "humanSections"
              ? { onSave: overrides.handleSaveSectionRatings }
              : undefined
          }
          lyricValidation={
            eventsPanel.laneId === "moisesLyrics"
              ? {
                  validatedIds: validatedLyricIds,
                  onToggle: overrides.handleToggleLyricValidation,
                }
              : undefined
          }
          blockReview={
            REVIEWABLE_LANE_IDS.has(eventsPanel.laneId)
              ? {
                  reviewsByKey: blockReviewIndexFor(eventsPanel.laneId) ?? new Map(),
                  onSave: overrides.handleSaveBlockReview,
                }
              : undefined
          }
        />
      )}

      {activeView === "timeline" && song && panel.panelMode === "hint" && (
        <HintEditorPanel
          song={song}
          file={humanHintsFile}
          currentTime={currentTime}
          activeReference={panel.activeHintRef}
          seed={panel.hintSeed}
          onClose={panel.closePanel}
          onSaved={overrides.handleSaveHints}
          onScrollToTime={viewport.scrollTimelineToTime}
        />
      )}

      {activeView === "timeline" && song && panel.panelMode === "segment" && (
        <SegmentEditorPanel
          song={song}
          file={humanSectionsFile}
          currentTime={currentTime}
          activeReference={panel.activeSectionRef}
          seed={panel.sectionSeed}
          onClose={panel.closePanel}
          onSaved={overrides.handleSaveSegments}
          onScrollToTime={viewport.scrollTimelineToTime}
        />
      )}

      {/* item 7: the review queue is the RightPanel shell's third mode,
          opened from the "Review queue" drawer entry (no lane). */}
      {activeView === "review" &&
        (song ? (
          <ReviewQueuePanel song={song} onClose={() => setActiveView("timeline")} />
        ) : (
          <aside className="app-rightpanel" aria-label="Review queue">
            <div className="card-kicker">Review queue</div>
            <p className="card-body">Select a song to review its open questions.</p>
          </aside>
        ))}

      {/* v3.7 item 11: MCP correction proposals — same RightPanel-shell
          convention as the review queue above, its own drawer entry. */}
      {activeView === "proposals" &&
        (song ? (
          <PendingProposalsPanel
            song={song}
            onClose={() => setActiveView("timeline")}
            focusId={proposals.proposalsFocusId}
            onQueueChange={proposals.setProposalsOverride}
            currentTime={currentTime}
            onSeek={viewport.seekToTimeAlways}
            timeEdits={proposals.proposalTimeEdits}
            onResetTimes={proposals.handleResetProposalTimes}
          />
        ) : (
          <aside className="app-rightpanel" aria-label="Pending proposals">
            <div className="card-kicker">Pending proposals</div>
            <p className="card-body">Select a song to review its queued proposals.</p>
          </aside>
        ))}
    </>
  );
}
