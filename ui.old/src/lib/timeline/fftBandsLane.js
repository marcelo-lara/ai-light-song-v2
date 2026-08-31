import { TRACK_HEIGHT } from "./constants.js";
import { getTrackContext, getTrackWidth, timeToPx } from "./shared.js";
import { clamp } from "../utils.js";

const FFT_BAND_VISIBILITY_THRESHOLD = 0.02;

function bucketFftFrames(frames, bandCount, secondsPerBucket, start, end) {
  const buckets = new Map();
  for (const frame of frames) {
    if (Number(frame.end_s) < start || Number(frame.start_s) > end) { continue; }
    const index = Math.floor(Number(frame.start_s) / secondsPerBucket);
    const bucket = buckets.get(index) || {
      start_s: index * secondsPerBucket,
      end_s: (index + 1) * secondsPerBucket,
      levels: new Array(bandCount).fill(0),
    };
    frame.levels.forEach((level, bandIndex) => {
      bucket.levels[bandIndex] = Math.max(bucket.levels[bandIndex], Number(level) || 0);
    });
    buckets.set(index, bucket);
  }
  return [...buckets.values()].sort((left, right) => left.start_s - right.start_s);
}

function bandColor(index, intensity) {
  const hues = [22, 46, 88, 138, 164, 186, 196];
  const hue = hues[index] ?? 196;
  const alpha = clamp(intensity, 0, 1) * 0.9;
  return `hsla(${hue}, 84%, 58%, ${alpha})`;
}

function resolveBandRows(bandCount, topPadding, bottomPadding) {
  const drawableHeight = TRACK_HEIGHT - topPadding - bottomPadding;
  const edges = Array.from({ length: bandCount + 1 }, (_, index) => Math.round(topPadding + ((drawableHeight * index) / bandCount)));
  return Array.from({ length: bandCount }, (_, bandIndex) => {
    const displayIndex = bandCount - 1 - bandIndex;
    const top = edges[displayIndex];
    const bottom = edges[displayIndex + 1];
    return {
      top,
      height: Math.max(1, bottom - top),
    };
  });
}

export function renderFftBandsLane(track, timeline, zoom, visibleRange) {
  const width = getTrackWidth(timeline, zoom);
  const context = getTrackContext(track, width, TRACK_HEIGHT);
  if (!context) { return; }
  const fftBands = timeline.fftBands || {};
  const frames = Array.isArray(fftBands.frames) ? fftBands.frames : [];
  const bands = Array.isArray(fftBands.bands) ? fftBands.bands : [];
  const bandCount = bands.length;
  if (!bandCount || !frames.length) {
    track.__laneRegions = [];
    return;
  }

  const bucketSeconds = Math.max(Number(fftBands.intervalSeconds) || 0.05, 1 / Math.max(zoom, 1));
  const buckets = bucketFftFrames(frames, bandCount, bucketSeconds, visibleRange.start - 1, visibleRange.end + 1);
  const topPadding = 6;
  const bottomPadding = 6;
  const bandRows = resolveBandRows(bandCount, topPadding, bottomPadding);

  context.save();
  for (const bucket of buckets) {
    const left = Math.floor(timeToPx(bucket.start_s, timeline, zoom));
    const right = Math.ceil(timeToPx(bucket.end_s, timeline, zoom));
    const widthPx = Math.max(1, right - left);
    bucket.levels.forEach((level, bandIndex) => {
      const intensity = clamp(Number(level) || 0, 0, 1);
      if (intensity <= FFT_BAND_VISIBILITY_THRESHOLD) { return; }
      const row = bandRows[bandIndex];
      const visibleIntensity = (intensity - FFT_BAND_VISIBILITY_THRESHOLD) / (1 - FFT_BAND_VISIBILITY_THRESHOLD);
      context.fillStyle = bandColor(bandIndex, visibleIntensity);
      context.fillRect(left, row.top, widthPx, row.height);
    });
  }
  context.restore();
  track.__laneRegions = [];
}