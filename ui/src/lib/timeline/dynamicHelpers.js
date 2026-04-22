import { TRACK_HEIGHT } from "./constants.js";
import { timeToPx } from "./shared.js";
import { clamp } from "../utils.js";

export function bucketRows(rows, secondsPerBucket, start, end) {
  const buckets = new Map();
  for (const row of rows) {
    if (Number(row.end_s) < start || Number(row.start_s) > end) { continue; }
    const index = Math.floor(Number(row.start_s) / secondsPerBucket);
    const bucket = buckets.get(index) || { start_s: index * secondsPerBucket, end_s: (index + 1) * secondsPerBucket, value: 0, count: 0, byType: { kick: 0, snare: 0, hat: 0 } };
    bucket.value = Math.max(bucket.value, Number(row.value ?? 0));
    bucket.count += 1;
    if (row.event_type && bucket.byType[row.event_type] !== undefined) { bucket.byType[row.event_type] += 1; }
    buckets.set(index, bucket);
  }
  return [...buckets.values()].sort((left, right) => left.start_s - right.start_s);
}

export function buildAreaPath(rows, timeline, zoom) {
  if (!rows.length) { return ""; }
  const baseline = TRACK_HEIGHT - 8;
  const topPoints = rows.map((row) => `${timeToPx((Number(row.start_s) + Number(row.end_s)) / 2, timeline, zoom)},${baseline - (clamp(Number(row.value), 0, 1) * (TRACK_HEIGHT - 18))}`);
  return `M ${timeToPx(rows[0].start_s, timeline, zoom)},${baseline} L ${topPoints.join(" L ")} L ${timeToPx(rows.at(-1).end_s, timeline, zoom)},${baseline} Z`;
}

export function normalizeWaveformEnvelope(waveformPeaks, timeline) {
  if (Array.isArray(waveformPeaks) && waveformPeaks.length > 0) {
    if (typeof waveformPeaks[0] === "number") {
      return waveformPeaks.map((peak) => ({ min: -Math.abs(Number(peak) || 0), max: Math.abs(Number(peak) || 0) }));
    }
    return waveformPeaks.map((peak) => ({ min: clamp(Number(peak.min ?? 0), -1, 1), max: clamp(Number(peak.max ?? 0), -1, 1) }));
  }
  return timeline.beats.map((beat) => ({ min: -(beat.beat_in_bar === 1 ? 0.9 : 0.45), max: beat.beat_in_bar === 1 ? 0.9 : 0.45 }));
}