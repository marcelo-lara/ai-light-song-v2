import { TRACK_HEIGHT } from "./constants.js";
import { bucketRows, buildAreaPath } from "./dynamicHelpers.js";
import { getTrackContext, getTrackWidth, timeToPx } from "./shared.js";
import { clamp } from "../utils.js";

export function renderSeriesLane(track, laneId, timeline, zoom, visibleRange) {
  const context = getTrackContext(track, getTrackWidth(timeline, zoom), TRACK_HEIGHT);
  if (!context) { return; }
  const source = timeline.energyRows;
  const rows = bucketRows(source, Math.max(0.1, 12 / zoom), Math.max(0, visibleRange.start - 4), Math.min(timeline.duration, visibleRange.end + 4));
  context.save();
  const areaPath = new Path2D(buildAreaPath(rows, timeline, zoom));
  context.fillStyle = "rgba(14, 116, 144, 0.16)";
  context.strokeStyle = "rgba(14, 116, 144, 0.72)";
  context.lineWidth = 1.4;
  context.fill(areaPath);
  context.stroke(areaPath);
  context.fillStyle = "rgba(185, 28, 28, 0.8)";
  for (const accent of timeline.accentCandidates.filter((row) => Number(row.time) >= visibleRange.start - 2 && Number(row.time) <= visibleRange.end + 2)) {
    context.beginPath();
    context.arc(timeToPx(accent.time, timeline, zoom), 72 - (clamp(Number(accent.intensity) || 0, 0, 1) * 52), 3.6, 0, Math.PI * 2);
    context.fill();
  }
  context.restore();
  track.__laneRegions = [];
}