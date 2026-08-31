import { dynamicLaneIds } from "../config.js";

import { drawSparseLane } from "./sparseLane.js";
import { renderDrumsLane } from "./drumsLane.js";
import { renderFftBandsLane } from "./fftBandsLane.js";
import { renderLoudnessLane } from "./loudnessLane.js";
import { renderSeriesLane } from "./seriesLane.js";
import { renderValidationLane } from "./validationLane.js";
import { renderWaveformLane } from "./waveformLane.js";

export function renderTrackLane(track, laneId, timeline, zoom, visibleRange, waveformPeaks) {
  if (!track || !timeline) { return; }
  if (!dynamicLaneIds.has(laneId)) { drawSparseLane(track, laneId, timeline, zoom); return; }
  if (laneId === "waveform") { renderWaveformLane(track, timeline, zoom, visibleRange, waveformPeaks); return; }
  if (laneId === "fftBands") { renderFftBandsLane(track, timeline, zoom, visibleRange); return; }
  if (laneId === "rmsLoudness" || laneId === "loudnessEnvelope") { renderLoudnessLane(track, laneId, timeline, zoom, visibleRange); return; }
  if (laneId === "drums") { renderDrumsLane(track, timeline, zoom, visibleRange); return; }
  if (laneId === "energy") { renderSeriesLane(track, laneId, timeline, zoom, visibleRange); return; }
  if (laneId === "validation") { renderValidationLane(track, timeline, zoom, visibleRange); }
}
