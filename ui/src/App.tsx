import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useSong } from "./data";
import type { SectionRow } from "./data/types";
import { resolveKeyAction, shouldPreventDefault } from "./app/keymap";
import { selectSongLoadState, type ArtifactLoadStatus } from "./app/loadStates";
import { AppDrawer } from "./app/AppDrawer";
import { AppFooter } from "./app/AppFooter";
import { AppHeader } from "./app/AppHeader";
import { AppRightPanels } from "./app/AppRightPanels";
import { AppTimelineArea } from "./app/AppTimelineArea";
import { useDrawer } from "./app/useDrawer";
import { useHumanOverrides } from "./app/useHumanOverrides";
import { useLaneContentSources } from "./app/useLaneContentSources";
import { useLaneVisibility } from "./app/useLaneVisibility";
import { usePanelState } from "./app/usePanelState";
import { useProposals } from "./app/useProposals";
import { useRenderLaneBody } from "./app/useRenderLaneBody";
import { useSongDiscovery } from "./app/useSongDiscovery";
import { useSongSelection } from "./app/useSongSelection";
import { useTimelineViewport } from "./app/useTimelineViewport";
import { type SparseBlock } from "./timeline/laneContent";
import { CANVAS_LANES, SPARSE_LANE_ARTIFACT, TIMELINE_KEYS } from "./timeline/laneConfig";
import { useLaneState } from "./timeline/laneState";

export function App(): React.JSX.Element {
  const { drawerOpen, setDrawerOpen, activeView, setActiveView, drawerRef } = useDrawer();
  const [song, setSong] = useSongSelection(setActiveView);
  const { songListState } = useSongDiscovery();
  const [laneListOpen, setLaneListOpen] = useState(false);

  const { artifacts } = useSong(song, TIMELINE_KEYS);
  const info = artifacts.info.data;
  const beats = useMemo(() => artifacts.beats.data ?? [], [artifacts.beats.data]);
  const sections: SectionRow[] = useMemo(
    () => artifacts.sectionsTopLevel.data ?? [],
    [artifacts.sectionsTopLevel.data],
  );
  const sectionSegmentation = useMemo(
    () => artifacts.sectionSegmentation.data?.sections ?? [],
    [artifacts.sectionSegmentation.data],
  );
  const estimatedDuration = info?.duration ?? beats.at(-1)?.time ?? 0;

  const viewport = useTimelineViewport({ song, activeView, beats, estimatedDuration });
  const { coords, transport } = viewport;

  const overrides = useHumanOverrides({
    song,
    humanHintsData: artifacts.humanHints.data,
    humanSectionsData: artifacts.humanSections.data,
    blockEnergyData: artifacts.blockEnergy.data,
    lyricValidationsData: artifacts.lyricValidations.data,
    blockReviewsData: artifacts.blockReviews.data,
  });
  const {
    humanHintsFile,
    humanSectionsFile,
    blockEnergyFile,
    validatedLyricIds,
    blockReviewsFile,
  } = overrides;

  const proposals = useProposals(artifacts.pendingProposals.data);
  const { pendingProposalsFileForLane } = proposals;

  const laneContentSources = useLaneContentSources({
    humanHintsFile,
    pendingProposalsFileForLane,
    humanSectionsFile,
    artifacts,
    validatedLyricIds,
    sections,
    sectionSegmentation,
    blockReviewsFile,
  });

  const laneState = useLaneState();

  // A click on an LLM Pending Proposals block opens the Pending Proposals
  // drawer scrolled to that proposal's card.
  const { setProposalsFocusId } = proposals;
  const openPendingProposal = useCallback(
    (reference: string) => {
      setProposalsFocusId(reference);
      setActiveView("proposals");
    },
    [setProposalsFocusId, setActiveView],
  );

  const panel = usePanelState({
    isPlaying: transport.isPlaying,
    seekTo: transport.seekTo,
    isTimeVisible: viewport.isTimeVisible,
    scrollTimelineToTime: viewport.scrollTimelineToTime,
    openPendingProposal,
  });

  // `emptyLaneInitSongRef` is owned here (not inside useLaneVisibility) so
  // the reset below — which must run BEFORE useLaneVisibility's own
  // empty-lane-init effect in the same commit, exactly as in the pre-split
  // App.tsx — is simply "registered first": this effect is called before
  // the `useLaneVisibility(...)` hook call textually below it.
  const emptyLaneInitSongRef = useRef<string | null>(null);

  // Reset panel + hint override when the song changes.
  useEffect(() => {
    panel.resetPanelState();
    overrides.resetOverrides();
    proposals.resetProposalsState();
    emptyLaneInitSongRef.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [song]);

  const { toggleExpandedGuarded, eventsPanel, blockReviewIndexFor } = useLaneVisibility({
    song,
    laneState,
    artifacts,
    laneContentSources,
    panelMode: panel.panelMode,
    eventsLaneId: panel.eventsLaneId,
    blockReviewsFile,
    emptyLaneInitSongRef,
  });

  const { seekToTime } = viewport;
  const handleSelectBlock = useCallback(
    (block: SparseBlock) => seekToTime(block.start_s),
    [seekToTime],
  );

  const renderLaneBody = useRenderLaneBody({
    transport,
    coords,
    artifacts,
    scrollLeft: viewport.scrollLeft,
    viewportWidth: viewport.viewportWidth,
    panel,
    laneContentSources,
    overrides,
    proposals,
  });

  const { stepBeat, stepBar } = transport;
  const { zoomIn, zoomOut, fitToWidth } = viewport;

  // esc target: panel → review view → lane list → left panel (drawer).
  // (refinement §10, extended by plan item 4 — the left panel is the drawer.)
  const { panelMode, closePanel } = panel;
  const closeOverlay = useCallback(() => {
    if (panelMode) {
      closePanel();
      return;
    }
    if (activeView === "review" || activeView === "proposals") {
      setActiveView("timeline");
      return;
    }
    if (laneListOpen) {
      setLaneListOpen(false);
      return;
    }
    if (drawerOpen) setDrawerOpen(false);
  }, [panelMode, activeView, laneListOpen, drawerOpen, closePanel, setActiveView, setLaneListOpen, setDrawerOpen]);

  // Single global keyboard listener (plan item 10). Resolution + the
  // input-focus guard live in the pure `keymap` module.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent): void => {
      const action = resolveKeyAction(event);
      if (!action) return;
      if (action === "closeOverlay") {
        closeOverlay();
        return;
      }
      if (activeView !== "timeline" || !song) return;
      if (shouldPreventDefault(action)) event.preventDefault();
      switch (action) {
        case "playPause":
          transport.togglePlay();
          break;
        case "stepBeatBack":
          stepBeat(-1);
          break;
        case "stepBeatForward":
          stepBeat(1);
          break;
        case "stepBarBack":
          stepBar(-1);
          break;
        case "stepBarForward":
          stepBar(1);
          break;
        case "zoomIn":
          zoomIn();
          break;
        case "zoomOut":
          zoomOut();
          break;
        case "fitToWidth":
          fitToWidth();
          break;
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeView, song, transport, stepBeat, stepBar, closeOverlay, zoomIn, zoomOut, fitToWidth]);

  const barBeat = coords.timeToBarBeat(transport.currentTime);
  const keyLabel = artifacts.harmonicLayer.data?.global_key?.label ?? "— key";

  const laneArtifactStatus = useMemo<Record<string, ArtifactLoadStatus>>(() => {
    const entries: Record<string, ArtifactLoadStatus> = {};
    for (const lane of laneState.visibleLanes) {
      const key = CANVAS_LANES[lane.id]?.key ?? SPARSE_LANE_ARTIFACT[lane.id];
      if (key) entries[lane.label] = artifacts[key].status;
    }
    return entries;
  }, [laneState.visibleLanes, artifacts]);

  const songLoadState = selectSongLoadState({
    infoStatus: artifacts.info.status,
    infoError: artifacts.info.error?.message ?? null,
    hasBeats: beats.length > 0,
    laneArtifactStatus,
  });

  // --- Test readiness marker (regression guide §5.2) ----------------------
  // `data-ui-ready` is "0" during any song load / full re-layout and flips to
  // "1" one paint after a fully-settled song's visible lanes have had a chance
  // to draw. `data-ui-loading` carries the in-flight artifact count.
  const inFlightCount = useMemo(
    () =>
      TIMELINE_KEYS.reduce(
        (n, key) => n + (artifacts[key].status === "loading" ? 1 : 0),
        0,
      ),
    [artifacts],
  );

  const canRenderTimeline =
    !!song && songLoadState.kind !== "loading" && songLoadState.kind !== "fatal";

  useEffect(() => {
    document.documentElement.dataset.uiLoading = String(inFlightCount);
  }, [inFlightCount]);

  // Clear the marker at the start of every song load / full re-layout.
  useEffect(() => {
    document.documentElement.dataset.uiReady = "0";
  }, [song, viewport.pxPerBar, viewport.viewportWidth]);

  useEffect(() => {
    if (!canRenderTimeline || inFlightCount > 0) {
      document.documentElement.dataset.uiReady = "0";
      return;
    }
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        document.documentElement.dataset.uiReady = "1";
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
  }, [canRenderTimeline, inFlightCount, viewport.pxPerBar, viewport.viewportWidth, activeView]);

  return (
    <div className="app-shell">
      <AppHeader
        drawerOpen={drawerOpen}
        onToggleDrawer={() => setDrawerOpen((open) => !open)}
        onSeekToStart={() => transport.seekTo(0)}
        onStepBar={stepBar}
        onStepBeat={stepBeat}
        isPlaying={transport.isPlaying}
        onTogglePlay={transport.togglePlay}
        currentTime={transport.currentTime}
        barBeat={barBeat}
        song={song}
        info={info}
        keyLabel={keyLabel}
      />

      <main className="app-main">
        {drawerOpen && (
          <AppDrawer
            drawerOpen={drawerOpen}
            activeView={activeView}
            onSelectView={setActiveView}
            drawerRef={drawerRef}
          />
        )}

        <AppTimelineArea
          activeView={activeView}
          song={song}
          songListState={songListState}
          songLoadState={songLoadState}
          coords={coords}
          transport={transport}
          sections={sections}
          laneState={laneState}
          toggleExpandedGuarded={toggleExpandedGuarded}
          onSelectSegment={panel.handleSelectSegment}
          renderLaneBody={renderLaneBody}
          onOpenLaneEvents={panel.toggleLaneEvents}
          eventsLaneId={panel.panelMode === "lane" ? panel.eventsLaneId : null}
          scrollerRef={viewport.scrollerRef}
          laneListOpen={laneListOpen}
          onCloseLaneList={() => setLaneListOpen(false)}
          onPickSong={(name) => {
            setSong(name);
            setActiveView("timeline");
            // R4/D4: picking a song hides the left panel. Deliberately not
            // done on the `?song=` deep-link effect or the song-change
            // reset effect — only a user pick counts.
            setDrawerOpen(false);
          }}
          onPickAnotherSong={() => setActiveView("song")}
        />

        <AppRightPanels
          activeView={activeView}
          song={song}
          panel={panel}
          overrides={overrides}
          proposals={proposals}
          viewport={viewport}
          currentTime={transport.currentTime}
          isPlaying={transport.isPlaying}
          humanHintsFile={humanHintsFile}
          humanSectionsFile={humanSectionsFile}
          blockEnergyFile={blockEnergyFile}
          validatedLyricIds={validatedLyricIds}
          eventsPanel={eventsPanel}
          blockReviewIndexFor={blockReviewIndexFor}
          onSelectBlock={handleSelectBlock}
          openPendingProposal={openPendingProposal}
          setActiveView={setActiveView}
        />
      </main>

      <AppFooter
        pxPerBar={viewport.pxPerBar}
        minZoomPxPerBar={viewport.minZoomPxPerBar}
        onZoomOut={viewport.zoomOut}
        onZoomIn={viewport.zoomIn}
        onZoomChange={(value) => {
          viewport.captureZoomAnchor();
          viewport.setPxPerBar(viewport.clampZoomForViewport(value));
        }}
        onFitToWidth={viewport.fitToWidth}
        followPlayhead={viewport.followPlayhead}
        onToggleFollow={() => viewport.setFollowPlayhead((on) => !on)}
        laneListOpen={laneListOpen}
        onToggleLaneList={() => setLaneListOpen((open) => !open)}
      />
    </div>
  );
}
