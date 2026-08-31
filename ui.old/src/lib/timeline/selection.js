import { laneDefinitions } from "../config.js";
import { formatDuration } from "../utils.js";

export function buildSelectionFromDataset(dataset) {
  return { laneLabel: dataset.laneLabel, label: dataset.label, start_s: Number(dataset.startS), end_s: Number(dataset.endS), reference: dataset.reference, detail: dataset.detail, summary: dataset.summary };
}

export function buildScrubSelection(trackLaneId, time) {
  return { laneLabel: laneDefinitions.find((lane) => lane.id === trackLaneId)?.label || "Timeline", label: `Cursor ${formatDuration(time)}`, start_s: time, end_s: time, reference: trackLaneId || "timeline", detail: "scrub", summary: "The shared playback cursor was moved directly on the synchronized timeline." };
}

export function findSelectionAtTrackPosition(track, absoluteX, offsetY) {
  const laneRegions = track?.__laneRegions;
  if (!Array.isArray(laneRegions) || !laneRegions.length) { return null; }
  return laneRegions.find((region) => absoluteX >= region.x && absoluteX <= (region.x + region.width) && offsetY >= region.y && offsetY <= (region.y + region.height))?.selection || null;
}