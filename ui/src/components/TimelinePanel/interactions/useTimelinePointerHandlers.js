import { buildScrubSelection, findSelectionAtTrackPosition, getVisibleRange, renderTrackLane } from "../../../lib/timeline.js";
import { formatRange } from "../../../lib/utils.js";

const scrollRenderedLaneIds = ["waveform", "drums", "energy", "validation"];

export function useTimelinePointerHandlers(context) {
  const { timeline, zoom, onSeek, onOpenSelectionOverlay, onCloseSelectionOverlay, onToggleLaneCollapsed, laneVisibility, laneCollapsed, waveformPeaks, onVisibleWindowChange, scrollerRef, rowsRef, viewportFrameRef, dragStateRef, suppressClickRef } = context;

  return {
    handleTimelineMouseDown(event) {
      if (event.button !== 0 || !timeline || !scrollerRef.current || event.target.closest("[data-lane-toggle]")) {
        return;
      }
      Object.assign(dragStateRef.current, { active: true, startClientX: event.clientX, startScrollLeft: scrollerRef.current.scrollLeft, moved: false });
      scrollerRef.current.classList.add("is-dragging");
    },
    handleTimelineClick(event) {
      if (suppressClickRef.current) {
        suppressClickRef.current = false;
        return;
      }
      if (!timeline) {
        return;
      }
      const laneToggle = event.target.closest("[data-lane-toggle]");
      if (laneToggle) {
        onToggleLaneCollapsed?.(laneToggle.dataset.laneToggle);
        return;
      }
      const track = event.target.closest("[data-track-lane], .ruler-track");
      if (!track) {
        return;
      }
      const rectangle = track.getBoundingClientRect();
      const absoluteX = event.clientX - rectangle.left;
      const offsetY = event.clientY - rectangle.top;
      const regionSelection = findSelectionAtTrackPosition(track, absoluteX, offsetY);
      if (regionSelection) {
        onSeek(regionSelection.start_s, regionSelection);
        if (regionSelection.laneLabel === "Human Hints") {
          onCloseSelectionOverlay?.();
          return;
        }
        onOpenSelectionOverlay?.(regionSelection, { x: event.clientX, y: event.clientY });
        return;
      }
      onSeek(absoluteX / zoom, buildScrubSelection(track.dataset.trackLane, absoluteX / zoom));
      onCloseSelectionOverlay?.();
    },
    handleScroll() {
      if (!timeline || !rowsRef.current) {
        return;
      }
      if (viewportFrameRef.current) {
        cancelAnimationFrame(viewportFrameRef.current);
      }
      viewportFrameRef.current = requestAnimationFrame(() => {
        const visibleRange = getVisibleRange(scrollerRef.current, zoom, timeline.duration);
        for (const laneId of scrollRenderedLaneIds) {
          if (laneVisibility[laneId] && !laneCollapsed[laneId]) {
            renderTrackLane(rowsRef.current.querySelector(`[data-track-lane="${laneId}"]`), laneId, timeline, zoom, visibleRange, waveformPeaks);
          }
        }
        onVisibleWindowChange(`Visible ${formatRange(visibleRange.start, visibleRange.end)}`, formatRange(visibleRange.start, visibleRange.end));
      });
    },
  };
}