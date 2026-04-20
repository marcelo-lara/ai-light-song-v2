import { useEffect } from "preact/hooks";

import {
  centerTimeInView,
  getVisibleRange,
  renderTrackLane,
  renderTimelineMarkup,
  updateNowMarkers,
} from "../../lib/timeline.js";
import { formatRange } from "../../lib/utils.js";

export function useTimelineEffects({
  timeline,
  laneVisibility,
  laneCollapsed,
  zoom,
  waveformPeaks,
  onVisibleWindowChange,
  currentTime,
  followPlayhead,
  scrollerRef,
  rowsRef,
  viewportFrameRef,
}) {
  useEffect(() => {
    const rowsElement = rowsRef.current;
    const scrollerElement = scrollerRef.current;
    if (!rowsElement) {
      return undefined;
    }
    if (!timeline) {
      rowsElement.className = "timeline-rows empty";
      rowsElement.textContent = "Load a song to inspect the synchronized timeline lanes.";
      onVisibleWindowChange("Visible 0:00.0-0:00.0", "-");
      return undefined;
    }

    rowsElement.className = "timeline-rows";
    rowsElement.innerHTML = renderTimelineMarkup(timeline, laneVisibility, laneCollapsed, zoom);
    const visibleRange = getVisibleRange(scrollerElement, zoom, timeline.duration);
    for (const laneId of Object.keys(laneVisibility)) {
      if (laneVisibility[laneId] && !laneCollapsed[laneId]) {
        const track = rowsElement.querySelector(`[data-track-lane="${laneId}"]`);
        renderTrackLane(track, laneId, timeline, zoom, visibleRange, waveformPeaks);
      }
    }
    updateNowMarkers(rowsElement, timeline, zoom, currentTime);
    onVisibleWindowChange(`Visible ${formatRange(visibleRange.start, visibleRange.end)}`, formatRange(visibleRange.start, visibleRange.end));
    return undefined;
  }, [timeline, laneVisibility, laneCollapsed, zoom, waveformPeaks, onVisibleWindowChange, currentTime, rowsRef, scrollerRef]);

  useEffect(() => {
    if (!rowsRef.current || !timeline) {
      return;
    }
    updateNowMarkers(rowsRef.current, timeline, zoom, currentTime);
  }, [timeline, zoom, currentTime, rowsRef]);

  useEffect(() => {
    if (!timeline || !followPlayhead) {
      return;
    }
    centerTimeInView(scrollerRef.current, timeline, zoom, currentTime);
  }, [timeline, followPlayhead, zoom, currentTime, scrollerRef]);

  useEffect(() => () => {
    if (viewportFrameRef.current) {
      cancelAnimationFrame(viewportFrameRef.current);
    }
  }, [viewportFrameRef]);
}