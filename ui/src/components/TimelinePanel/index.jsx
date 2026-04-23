import { useRef } from "preact/hooks";

import TimelineHeader from "./TimelineHeader.jsx";
import TimelineSongMenu from "./TimelineSongMenu.jsx";
import TimelineViewport from "./TimelineViewport.jsx";
import { useTimelineEffects } from "./useTimelineEffects.js";
import { useTimelineInteractions } from "./useTimelineInteractions.js";
import { buildTimelineLabels, getPlaybackIndicators } from "./usePlaybackIndicators.js";

export default function TimelinePanel(props) {
  const scrollerRef = useRef(null);
  const rowsRef = useRef(null);
  const viewportFrameRef = useRef(null);
  const dragStateRef = useRef({
    active: false,
    startClientX: 0,
    startScrollLeft: 0,
    moved: false,
  });
  const suppressClickRef = useRef(0);

  useTimelineEffects({
    timeline: props.timeline,
    laneVisibility: props.laneVisibility,
    laneCollapsed: props.laneCollapsed,
    zoom: props.zoom,
    waveformPeaks: props.waveformPeaks,
    onVisibleWindowChange: props.onVisibleWindowChange,
    currentTime: props.currentTime,
    followPlayhead: props.followPlayhead,
    scrollerRef,
    rowsRef,
    viewportFrameRef,
  });

  const {
    songMenuAnchor,
    songMenuOpen,
    handleOpenSongMenu,
    handleCloseSongMenu,
    handleSongMenuSelect,
    handleTimelineMouseDown,
    handleTimelineClick,
    handleTimelineContextMenu,
    handleScroll,
  } = useTimelineInteractions({
    timeline: props.timeline,
    zoom: props.zoom,
    onSeek: props.onSeek,
    onAddHumanHint: props.onAddHumanHint,
    onOpenSelectionOverlay: props.onOpenSelectionOverlay,
    onCloseSelectionOverlay: props.onCloseSelectionOverlay,
    onToggleLaneCollapsed: props.onToggleLaneCollapsed,
    laneVisibility: props.laneVisibility,
    laneCollapsed: props.laneCollapsed,
    waveformPeaks: props.waveformPeaks,
    onVisibleWindowChange: props.onVisibleWindowChange,
    onPlayPause: props.onPlayPause,
    onPreviousBar: props.onPreviousBar,
    onPreviousBeat: props.onPreviousBeat,
    onNextBeat: props.onNextBeat,
    onNextBar: props.onNextBar,
    onHeaderSongSelect: props.onHeaderSongSelect,
    scrollerRef,
    rowsRef,
    viewportFrameRef,
    dragStateRef,
    suppressClickRef,
  });

  const transportDisabled = !props.timeline;
  const { beatIndicator, barIndicator } = getPlaybackIndicators(props.timeline, props.currentTime);
  const { visibleWindowLabel, selectionLabel } = buildTimelineLabels(props.timeline, props.selection);

  return (
    <section className="panel">
      <TimelineHeader
        loadedSong={props.loadedSong}
        isSidebarCollapsed={props.isSidebarCollapsed}
        onToggleSidebar={props.onToggleSidebar}
        onOpenSongMenu={handleOpenSongMenu}
        transportDisabled={transportDisabled}
        onJumpStart={props.onJumpStart}
        onPreviousBar={props.onPreviousBar}
        onPreviousBeat={props.onPreviousBeat}
        onPlayPause={props.onPlayPause}
        isPlaying={props.isPlaying}
        onNextBeat={props.onNextBeat}
        onNextBar={props.onNextBar}
        barIndicator={barIndicator}
        beatIndicator={beatIndicator}
        zoom={props.zoom}
        onZoomChange={props.onZoomChange}
        visibleWindowLabel={visibleWindowLabel}
        selectionLabel={selectionLabel}
      />
      <TimelineSongMenu anchorEl={songMenuAnchor} open={songMenuOpen} onClose={handleCloseSongMenu} songs={props.availableAudioSongs} loadedSong={props.loadedSong} onSelectSong={handleSongMenuSelect} />
      <TimelineViewport scrollerRef={scrollerRef} rowsRef={rowsRef} onMouseDown={handleTimelineMouseDown} onContextMenu={handleTimelineContextMenu} onScroll={handleScroll} onClick={handleTimelineClick} />
    </section>
  );
}