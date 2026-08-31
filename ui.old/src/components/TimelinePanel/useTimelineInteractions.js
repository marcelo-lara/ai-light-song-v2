import { useTimelineDragPan } from "./interactions/useTimelineDragPan.js";
import { useTimelineKeyboardShortcuts } from "./interactions/useTimelineKeyboardShortcuts.js";
import { useTimelinePointerHandlers } from "./interactions/useTimelinePointerHandlers.js";
import { useTimelineSongMenu } from "./interactions/useTimelineSongMenu.js";

export function useTimelineInteractions({
  timeline,
  zoom,
  onSeek,
  onAddHumanHint,
  onOpenSelectionOverlay,
  onCloseSelectionOverlay,
  onToggleLaneCollapsed,
  laneVisibility,
  laneCollapsed,
  waveformPeaks,
  onVisibleWindowChange,
  onPlayPause,
  onPreviousBar,
  onPreviousBeat,
  onNextBeat,
  onNextBar,
  onHeaderSongSelect,
  scrollerRef,
  rowsRef,
  viewportFrameRef,
  dragStateRef,
  suppressClickRef,
}) {
  useTimelineDragPan({ dragStateRef, scrollerRef, suppressClickRef });
  useTimelineKeyboardShortcuts({ onPlayPause, onPreviousBar, onPreviousBeat, onNextBeat, onNextBar });
  const menu = useTimelineSongMenu(onHeaderSongSelect);
  const pointerHandlers = useTimelinePointerHandlers({ timeline, zoom, onSeek, onAddHumanHint, onOpenSelectionOverlay, onCloseSelectionOverlay, onToggleLaneCollapsed, laneVisibility, laneCollapsed, waveformPeaks, onVisibleWindowChange, scrollerRef, rowsRef, viewportFrameRef, dragStateRef, suppressClickRef });

  return {
    ...menu,
    ...pointerHandlers,
  };
}