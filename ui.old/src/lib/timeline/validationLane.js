import { TRACK_HEIGHT } from "./constants.js";
import { drawRoundedRect, getTrackContext, getTrackWidth, timeToPx } from "./shared.js";

export function renderValidationLane(track, timeline, zoom, visibleRange) {
  const context = getTrackContext(track, getTrackWidth(timeline, zoom), TRACK_HEIGHT);
  if (!context) { return; }
  const colorByStatus = { exact: "rgba(15, 118, 110, 0.7)", shifted: "rgba(202, 138, 4, 0.76)", not_exported: "rgba(185, 28, 28, 0.76)", output_only: "rgba(30, 64, 175, 0.7)" };
  context.save();
  for (const row of timeline.eventComparisons.filter((row) => Number(row.end_s) >= visibleRange.start - 2 && Number(row.start_s) <= visibleRange.end + 2)) {
    const left = timeToPx(row.start_s, timeline, zoom);
    drawRoundedRect(context, left, 10, Math.max(2, timeToPx(row.end_s, timeline, zoom) - left), 16, 8);
    context.fillStyle = colorByStatus[row.status] || colorByStatus.shifted;
    context.fill();
  }
  context.lineWidth = 2.4;
  for (const row of timeline.validationDrift.filter((row) => Number(row.reference_time) >= visibleRange.start - 2 && Number(row.reference_time) <= visibleRange.end + 2)) {
    const x = timeToPx(row.reference_time ?? row.inferred_time ?? 0, timeline, zoom);
    const lineHeight = Math.min(24, Math.abs(Number(row.delta_seconds ?? 0)) * 140);
    context.strokeStyle = row.within_tolerance ? "rgba(15, 118, 110, 0.82)" : "rgba(185, 28, 28, 0.88)";
    context.beginPath(); context.moveTo(x, 64 - lineHeight); context.lineTo(x, 64); context.stroke();
  }
  context.strokeStyle = "rgba(77, 53, 29, 0.18)"; context.lineWidth = 1; context.beginPath(); context.moveTo(0, 64); context.lineTo(getTrackWidth(timeline, zoom), 64); context.stroke();
  context.restore();
  track.__laneRegions = [];
}