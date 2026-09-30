// useRenderLaneBody.tsx — TimelineGrid's per-lane body renderer: the
// waveform, the canvas (dense-curve) lanes, the sparse (block) lanes plus
// their "new hint/segment" pills, and the Regression Overlay stub. Split out
// of App.tsx (v3.9 item 7) with no behaviour change.

import { useCallback } from "react";

import type { SongArtifacts } from "../data/useSong";
import { CanvasLane, type CanvasLaneSource } from "../timeline/CanvasLane";
import { buildLaneBlocks, type LaneContentSources } from "../timeline/laneContent";
import { CANVAS_LANES, SPARSE_LANE_ARTIFACT } from "../timeline/laneConfig";
import type { Lane } from "../timeline/laneState";
import { SparseLane } from "../timeline/SparseLane";
import type { Transport } from "../timeline/useTransport";
import type { Coords } from "../timeline/coords";
import { WaveformLane } from "../timeline/WaveformLane";
import type { HumanOverridesResult } from "./useHumanOverrides";
import type { PanelStateResult } from "./usePanelState";
import type { ProposalsState } from "./useProposals";

export function useRenderLaneBody({
  transport,
  coords,
  artifacts,
  scrollLeft,
  viewportWidth,
  panel,
  laneContentSources,
  overrides,
  proposals,
}: {
  transport: Transport;
  coords: Coords;
  artifacts: SongArtifacts;
  scrollLeft: number;
  viewportWidth: number;
  panel: PanelStateResult;
  laneContentSources: LaneContentSources;
  overrides: HumanOverridesResult;
  proposals: ProposalsState;
}): (lane: Lane) => React.ReactNode {
  // Destructured to exactly the fields the original App.tsx `renderLaneBody`
  // depended on — `transport` (and `panel`/`overrides`/`proposals`) change
  // identity far more often than these individual fields (`transport` on
  // every playback tick, via `currentTime`), so depending on the whole
  // object here would recreate this callback every animation frame during
  // playback instead of only when one of these actually changes.
  const { surface, isReady, error: transportError, seekTo } = transport;
  const {
    activeHintRef,
    activeSectionRef,
    handleSelectMarker,
    openHintEditor,
    openSegmentEditor,
    handleCreateHintAt,
    handleCreateSegmentAt,
  } = panel;
  const { handleCommitHintTimes, handleCommitSegmentTimes } = overrides;
  const { handleCommitProposalTimes } = proposals;

  return useCallback(
    (lane: Lane): React.ReactNode => {
      if (lane.id === "waveform") {
        return (
          <WaveformLane
            surface={surface}
            ready={isReady}
            error={transportError}
            width={coords.timelineW}
          />
        );
      }
      const entry = CANVAS_LANES[lane.id];
      if (entry) {
        const art = artifacts[entry.key];
        return (
          <CanvasLane
            lane={lane}
            coords={coords}
            source={{ kind: entry.kind, data: art.data as never } as CanvasLaneSource}
            status={art.status}
            error={art.error?.message ?? null}
            scrollLeft={scrollLeft}
            viewportWidth={viewportWidth}
            onSeek={seekTo}
            onSelectMarker={handleSelectMarker}
          />
        );
      }

      const sparseKey = SPARSE_LANE_ARTIFACT[lane.id];
      if (sparseKey) {
        const art = artifacts[sparseKey];
        const blocks = buildLaneBlocks(lane.id, laneContentSources);
        return (
          <>
            <SparseLane
              lane={lane}
              laneId={lane.id}
              coords={coords}
              blocks={blocks}
              status={art.status}
              error={art.error?.message ?? null}
              activeId={
                lane.id === "humanHints"
                  ? activeHintRef
                  : lane.id === "humanSections"
                    ? activeSectionRef
                    : null
              }
              onSeek={seekTo}
              onSelectMarker={handleSelectMarker}
              onCommitHintTimes={
                lane.id === "humanHints"
                  ? handleCommitHintTimes
                  : lane.id === "humanSections"
                    ? handleCommitSegmentTimes
                    : lane.id === "llmPendingProposals"
                      ? handleCommitProposalTimes
                      : undefined
              }
              onCreateHint={
                lane.id === "humanHints"
                  ? handleCreateHintAt
                  : lane.id === "humanSections"
                    ? handleCreateSegmentAt
                    : undefined
              }
            />
            {lane.id === "humanHints" && (
              <button
                type="button"
                className="tl-hint-pill tl-hint-pill--new"
                title="New hint at the playhead"
                onClick={() => openHintEditor(null)}
              >
                <i className="ph ph-plus" />
              </button>
            )}
            {lane.id === "humanSections" && (
              <button
                type="button"
                className="tl-hint-pill tl-hint-pill--new"
                title="New segment at the playhead"
                onClick={() => openSegmentEditor(null)}
              >
                <i className="ph ph-plus" />
              </button>
            )}
          </>
        );
      }

      if (lane.id === "validation") {
        // Regression Overlay — item 9 ships this as an empty-state stub; the
        // eventComparisons / beat-drift wiring is deferred to item 11's parity
        // pass (validation-artifact id alignment not verified). See D-log.
        return (
          <div className="tl-canvas-lane" style={{ position: "absolute", inset: 0 }}>
            <div className="tl-canvas-lane__state">
              Regression overlay — validation wiring deferred (item 11 parity)
            </div>
          </div>
        );
      }
      return null;
    },
    [
      surface,
      isReady,
      transportError,
      seekTo,
      coords,
      artifacts,
      scrollLeft,
      viewportWidth,
      handleSelectMarker,
      laneContentSources,
      activeHintRef,
      activeSectionRef,
      openHintEditor,
      openSegmentEditor,
      handleCommitHintTimes,
      handleCreateHintAt,
      handleCommitSegmentTimes,
      handleCreateSegmentAt,
      handleCommitProposalTimes,
    ],
  );
}
