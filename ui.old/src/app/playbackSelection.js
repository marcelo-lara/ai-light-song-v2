export function buildPlaybackSelection(label, time, detail, summary) {
  return {
    laneLabel: "Playback",
    label,
    start_s: time,
    end_s: time,
    reference: "playback",
    detail,
    summary,
  };
}