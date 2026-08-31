import { TRACK_HEIGHT } from "./constants.js";
import { normalizeWaveformEnvelope } from "./dynamicHelpers.js";
import { getTrackContext, getTrackWidth } from "./shared.js";

export function renderWaveformLane(track, timeline, zoom, visibleRange, waveformPeaks) {
  const context = getTrackContext(track, getTrackWidth(timeline, zoom), TRACK_HEIGHT);
  if (!context) { return; }
  const peaks = normalizeWaveformEnvelope(waveformPeaks, timeline);
  const duration = Math.max(Number(timeline.duration) || 0, 0.001);
  const secondsPerPeak = duration / Math.max(peaks.length, 1);
  const startIndex = Math.max(0, Math.floor((Math.max(0, Number(visibleRange?.start ?? 0) - Math.max(secondsPerPeak * 4, 0.25)) / duration) * peaks.length));
  const endIndex = Math.min(peaks.length, Math.ceil((Math.min(duration, Number(visibleRange?.end ?? duration) + Math.max(secondsPerPeak * 4, 0.25)) / duration) * peaks.length));
  const width = getTrackWidth(timeline, zoom);
  const center = TRACK_HEIGHT / 2;
  const scale = TRACK_HEIGHT * 0.38;
  context.save();
  context.fillStyle = "rgba(15, 118, 110, 0.18)";
  context.strokeStyle = "rgba(15, 118, 110, 0.62)";
  for (let index = startIndex; index < endIndex; index += 1) {
    const x = (index / Math.max(peaks.length, 1)) * width;
    const nextX = ((index + 1) / Math.max(peaks.length, 1)) * width;
    const top = center + (peaks[index].min * scale);
    const bottom = center + (peaks[index].max * scale);
    context.fillRect(x, Math.min(top, bottom), Math.max(1, nextX - x), Math.max(1, Math.abs(bottom - top)));
  }
  for (const key of ["max", "min"]) {
    context.beginPath();
    context.moveTo(((startIndex + 0.5) / Math.max(peaks.length, 1)) * width, center);
    for (let index = startIndex; index < endIndex; index += 1) {
      context.lineTo(((index + 0.5) / Math.max(peaks.length, 1)) * width, center + (peaks[index][key] * scale));
    }
    context.stroke();
  }
  context.restore();
  track.__laneRegions = [];
}