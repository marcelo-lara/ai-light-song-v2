export function beatAtTime(timeline, time) {
  if (!timeline) {
    return null;
  }
  for (let index = 0; index < timeline.beats.length; index += 1) {
    const beat = timeline.beats[index];
    const next = timeline.beats[index + 1];
    const end = next ? next.time : timeline.duration;
    if (beat.time <= time && time < end) {
      return beat;
    }
  }
  return timeline.beats.at(-1) || null;
}

export function previousBeatTime(timeline, currentTime, fallback = 0) {
  if (!timeline || !Array.isArray(timeline.beats) || timeline.beats.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) - 0.001;
  for (let index = timeline.beats.length - 1; index >= 0; index -= 1) {
    const markerTime = Number(timeline.beats[index]?.time);
    if (markerTime < threshold) {
      return markerTime;
    }
  }
  return fallback;
}

export function nextBeatTime(timeline, currentTime, fallback = 0) {
  if (!timeline || !Array.isArray(timeline.beats) || timeline.beats.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) + 0.001;
  for (const beat of timeline.beats) {
    const markerTime = Number(beat?.time);
    if (markerTime > threshold) {
      return markerTime;
    }
  }
  return fallback;
}

export function previousMarkerTime(rows, currentTime, getTime, fallback = 0) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) - 0.05;
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    const markerTime = Number(getTime(rows[index]));
    if (markerTime < threshold) {
      return markerTime;
    }
  }
  return fallback;
}

export function nextMarkerTime(rows, currentTime, getTime, fallback = 0) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) + 0.05;
  for (const row of rows) {
    const markerTime = Number(getTime(row));
    if (markerTime > threshold) {
      return markerTime;
    }
  }
  return fallback;
}