import { CAPTION_FONT } from "./constants.js";
import { getTrackContext, getTrackWidth, timeToPx, trimCanvasText } from "./shared.js";
import { clamp } from "../utils.js";


const LANE_HEIGHT = 112;
const RMS_HEATMAP_VISIBILITY_THRESHOLD = 0.02;
const SOURCE_COLORS = [
  { fill: "rgba(250, 204, 21, 0.9)", stroke: "rgba(250, 204, 21, 0.95)", tint: "rgba(250, 204, 21, VALUE)" },
  { fill: "rgba(248, 113, 113, 0.88)", stroke: "rgba(248, 113, 113, 0.94)", tint: "rgba(248, 113, 113, VALUE)" },
  { fill: "rgba(34, 211, 238, 0.88)", stroke: "rgba(34, 211, 238, 0.94)", tint: "rgba(34, 211, 238, VALUE)" },
  { fill: "rgba(74, 222, 128, 0.88)", stroke: "rgba(74, 222, 128, 0.94)", tint: "rgba(74, 222, 128, VALUE)" },
  { fill: "rgba(192, 132, 252, 0.88)", stroke: "rgba(192, 132, 252, 0.94)", tint: "rgba(192, 132, 252, VALUE)" },
];

function bucketFrames(frames, sourceCount, secondsPerBucket, start, end) {
  const buckets = new Map();
  for (const frame of frames) {
    if (Number(frame.end_s) < start || Number(frame.start_s) > end) { continue; }
    const index = Math.floor(Number(frame.start_s) / secondsPerBucket);
    const bucket = buckets.get(index) || {
      start_s: index * secondsPerBucket,
      end_s: (index + 1) * secondsPerBucket,
      sums: new Array(sourceCount).fill(0),
      counts: new Array(sourceCount).fill(0),
      maxes: new Array(sourceCount).fill(0),
    };
    frame.normalized_values.forEach((value, sourceIndex) => {
      const resolved = clamp(Number(value) || 0, 0, 1);
      bucket.sums[sourceIndex] += resolved;
      bucket.counts[sourceIndex] += 1;
      bucket.maxes[sourceIndex] = Math.max(bucket.maxes[sourceIndex], resolved);
    });
    buckets.set(index, bucket);
  }
  return [...buckets.values()].sort((left, right) => left.start_s - right.start_s).map((bucket) => ({
    start_s: bucket.start_s,
    end_s: bucket.end_s,
    averages: bucket.sums.map((sum, index) => bucket.counts[index] > 0 ? sum / bucket.counts[index] : 0),
    maxes: bucket.maxes,
  }));
}

function colorAt(sourceIndex, alpha) {
  const palette = SOURCE_COLORS[sourceIndex] || SOURCE_COLORS.at(-1);
  return palette.tint.replace("VALUE", String(roundAlpha(alpha)));
}

function roundAlpha(value) {
  return Math.round(clamp(value, 0, 1) * 1000) / 1000;
}

function drawSourceGrid(context, rowTop, rowHeight, width) {
  context.fillStyle = "rgba(148, 163, 184, 0.06)";
  context.fillRect(0, rowTop, width, rowHeight);
  context.strokeStyle = "rgba(148, 163, 184, 0.16)";
  context.beginPath();
  context.moveTo(0, rowTop + rowHeight + 0.5);
  context.lineTo(width, rowTop + rowHeight + 0.5);
  context.stroke();
}

function drawSourceLabel(context, sources, rowTop, sourceIndex, scrollOffset) {
  const label = sources[sourceIndex]?.label || `Source ${sourceIndex + 1}`;
  context.font = CAPTION_FONT;
  const trimmed = trimCanvasText(context, label, 56);
  const textWidth = context.measureText(trimmed).width;
  const labelX = (scrollOffset || 0) + 6;
  context.fillStyle = "rgba(10, 18, 28, 0.68)";
  context.fillRect(labelX - 2, rowTop + 2, textWidth + 6, 13);
  context.fillStyle = SOURCE_COLORS[sourceIndex]?.fill || "rgba(226, 232, 240, 0.92)";
  context.fillText(trimmed, labelX, rowTop + 11);
}

function drawRmsHeatmap(context, buckets, sourceIndex, rowTop, rowHeight, timeline, zoom) {
  for (const bucket of buckets) {
    const intensity = clamp(Number(bucket.maxes[sourceIndex]) || 0, 0, 1);
    if (intensity <= RMS_HEATMAP_VISIBILITY_THRESHOLD) { continue; }
    const left = timeToPx(bucket.start_s, timeline, zoom);
    const widthPx = Math.max(1, timeToPx(bucket.end_s, timeline, zoom) - left);
    const visibleIntensity = (intensity - RMS_HEATMAP_VISIBILITY_THRESHOLD) / (1 - RMS_HEATMAP_VISIBILITY_THRESHOLD);
    context.fillStyle = colorAt(sourceIndex, 0.16 + (visibleIntensity * 0.72));
    context.fillRect(left, rowTop + 1, widthPx, Math.max(1, rowHeight - 2));
  }
}

function drawEnvelopeTrace(context, buckets, sourceIndex, rowTop, rowHeight, timeline, zoom) {
  const rows = buckets.filter((bucket) => (Number(bucket.averages[sourceIndex]) || 0) > 0);
  if (!rows.length) { return; }
  const baseline = rowTop + rowHeight - 4;
  const amplitudeHeight = Math.max(6, rowHeight - 14);
  context.beginPath();
  context.moveTo(timeToPx(rows[0].start_s, timeline, zoom), baseline);
  for (const row of rows) {
    const centerX = timeToPx((Number(row.start_s) + Number(row.end_s)) / 2, timeline, zoom);
    const y = baseline - (clamp(Number(row.averages[sourceIndex]) || 0, 0, 1) * amplitudeHeight);
    context.lineTo(centerX, y);
  }
  context.lineTo(timeToPx(rows.at(-1).end_s, timeline, zoom), baseline);
  context.closePath();
  context.fillStyle = colorAt(sourceIndex, 0.18);
  context.fill();

  context.beginPath();
  for (const [index, row] of rows.entries()) {
    const centerX = timeToPx((Number(row.start_s) + Number(row.end_s)) / 2, timeline, zoom);
    const y = baseline - (clamp(Number(row.averages[sourceIndex]) || 0, 0, 1) * amplitudeHeight);
    if (index === 0) {
      context.moveTo(centerX, y);
    } else {
      context.lineTo(centerX, y);
    }
  }
  context.strokeStyle = SOURCE_COLORS[sourceIndex]?.stroke || "rgba(226, 232, 240, 0.9)";
  context.lineWidth = 1.5;
  context.stroke();
}

export function renderLoudnessLane(track, laneId, timeline, zoom, visibleRange) {
  const context = getTrackContext(track, getTrackWidth(timeline, zoom), LANE_HEIGHT);
  if (!context) { return; }
  const payload = laneId === "rmsLoudness" ? timeline.rmsLoudness : timeline.loudnessEnvelope;
  const frames = Array.isArray(payload?.frames) ? payload.frames : [];
  const sources = Array.isArray(payload?.sources) ? payload.sources : [];
  if (!frames.length || !sources.length) {
    track.__laneRegions = [];
    return;
  }

  const bucketSeconds = Math.max(Number(payload.windowSeconds) || 0.01, 1 / Math.max(zoom, 1));
  const buckets = bucketFrames(frames, sources.length, bucketSeconds, visibleRange.start - 1, visibleRange.end + 1);
  const topPadding = 5;
  const bottomPadding = 5;
  const rowGap = 2;
  const rowHeight = (LANE_HEIGHT - topPadding - bottomPadding - ((sources.length - 1) * rowGap)) / sources.length;
  const width = getTrackWidth(timeline, zoom);
  const scrollOffset = Math.round(visibleRange.start * zoom);

  context.save();
  for (let sourceIndex = 0; sourceIndex < sources.length; sourceIndex += 1) {
    const rowTop = topPadding + (sourceIndex * (rowHeight + rowGap));
    drawSourceGrid(context, rowTop, rowHeight, width);
    if (laneId === "rmsLoudness") {
      drawRmsHeatmap(context, buckets, sourceIndex, rowTop, rowHeight, timeline, zoom);
    } else {
      drawEnvelopeTrace(context, buckets, sourceIndex, rowTop, rowHeight, timeline, zoom);
    }
    drawSourceLabel(context, sources, rowTop, sourceIndex, scrollOffset);
  }
  context.restore();
  track.__laneRegions = [];
}
