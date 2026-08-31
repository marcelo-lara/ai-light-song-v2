import { clamp, formatRange } from "../../lib/utils.js";

export function getPlaybackIndicators(timeline, currentTime) {
  const playbackTime = clamp(Number(currentTime) || 0, 0, Number(timeline?.duration) || 0);
  const currentBeat = timeline?.beats?.reduce((activeBeat, beat) => Number(beat.time) <= playbackTime ? beat : activeBeat, null) || null;
  const currentBar = timeline?.bars?.reduce((activeBar, bar) => Number(bar.start_s) <= playbackTime ? bar : activeBar, null) || null;
  return { beatIndicator: currentBeat?.beat_in_bar ?? "-", barIndicator: currentBar?.bar ?? currentBeat?.bar ?? "-" };
}

export function buildTimelineLabels(timeline, selection) {
  return {
    visibleWindowLabel: timeline ? selection.visibleWindowLabel || `Visible ${formatRange(0, 0)}` : "Visible 0:00.0-0:00.0",
    selectionLabel: selection.region ? `${selection.region.laneLabel}: ${selection.region.label} ${formatRange(selection.region.start_s, selection.region.end_s)}` : "No region selected.",
  };
}