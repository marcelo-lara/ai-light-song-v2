import { LABEL_WIDTH } from "../config.js";
import { clamp } from "../utils.js";

import { timeToPx } from "./shared.js";

export function getVisibleRange(scroller, zoom, duration) {
  const scrollLeft = scroller?.scrollLeft || 0;
  const viewportWidth = Math.max((scroller?.clientWidth || 0) - LABEL_WIDTH, 0);
  const start = clamp(scrollLeft / zoom, 0, duration || 0);
  const end = clamp(start + (viewportWidth / zoom), start, duration || 0);
  return { start, end };
}

export function updateNowMarkers(rowsElement, timeline, zoom, currentTime) {
  if (!rowsElement || !timeline) {
    return;
  }
  const x = timeToPx(currentTime, timeline, zoom);
  for (const marker of rowsElement.querySelectorAll("[data-now-marker]")) {
    marker.style.transform = `translate3d(${x}px, 0, 0)`;
  }
}

export function centerTimeInView(scroller, timeline, zoom, time) {
  if (!scroller || !timeline) {
    return;
  }
  const viewportWidth = Math.max(scroller.clientWidth - LABEL_WIDTH, 0);
  scroller.scrollLeft = Math.max(0, timeToPx(time, timeline, zoom) - (viewportWidth / 2));
}