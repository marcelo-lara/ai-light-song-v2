import { TRACK_HEIGHT } from "./constants.js";
import { bucketRows } from "./dynamicHelpers.js";
import { getTrackContext, getTrackWidth, timeToPx } from "./shared.js";

export function renderDrumsLane(track, timeline, zoom, visibleRange) {
  const context = getTrackContext(track, getTrackWidth(timeline, zoom), TRACK_HEIGHT);
  if (!context) { return; }
  context.save();
  if (zoom >= 42) {
    const typeY = { kick: 58, snare: 38, hat: 18, unresolved: 68 };
    const typeColor = { kick: "rgba(15, 118, 110, 0.9)", snare: "rgba(185, 28, 28, 0.9)", hat: "rgba(202, 138, 4, 0.9)", unresolved: "rgba(107, 114, 128, 0.8)" };
    for (const event of timeline.drums.filter((event) => Number(event.time) >= visibleRange.start - 1.5 && Number(event.time) <= visibleRange.end + 1.5)) {
      context.strokeStyle = typeColor[event.event_type] || typeColor.unresolved;
      context.beginPath();
      context.moveTo(timeToPx(event.time, timeline, zoom), (typeY[event.event_type] || 68) - 10);
      context.lineTo(timeToPx(event.time, timeline, zoom), (typeY[event.event_type] || 68) + 10);
      context.stroke();
    }
    context.restore();
    track.__laneRegions = [];
    return;
  }
  const buckets = bucketRows(timeline.drums.map((event) => ({ start_s: Number(event.time), end_s: Number(event.end_s ?? event.time), value: 0, event_type: String(event.event_type) })), Math.max(0.2, 14 / zoom), visibleRange.start, visibleRange.end);
  const maxCount = Math.max(...buckets.map((bucket) => bucket.count), 1);
  for (const bucket of buckets) {
    const left = timeToPx(bucket.start_s, timeline, zoom);
    const widthPx = Math.max(1, timeToPx(bucket.end_s, timeline, zoom) - left);
    context.fillStyle = "rgba(15, 118, 110, 0.85)"; context.fillRect(left, 78 - ((bucket.byType.kick / maxCount) * 24), widthPx, (bucket.byType.kick / maxCount) * 24);
    context.fillStyle = "rgba(185, 28, 28, 0.82)"; context.fillRect(left, 52 - ((bucket.byType.snare / maxCount) * 18), widthPx, (bucket.byType.snare / maxCount) * 18);
    context.fillStyle = "rgba(202, 138, 4, 0.84)"; context.fillRect(left, 28 - ((bucket.byType.hat / maxCount) * 16), widthPx, (bucket.byType.hat / maxCount) * 16);
  }
  context.restore();
  track.__laneRegions = [];
}