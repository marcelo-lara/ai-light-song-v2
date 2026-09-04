// coords.ts — the single time -> x mapping every timeline surface shares.
//
// The canvas mock assumes a uniform px-per-bar (constant tempo). The rebuild is
// *time-proportional*: `x = t * pxPerSec`, where
// `pxPerSec = pxPerBar / medianBarSeconds` and `medianBarSeconds` is the median
// real bar length taken from `beats.json`. Bar lines are then drawn at each
// bar's real start time, so bars are NOT equal pixel widths when the tempo
// drifts, and every lane + the playhead + wavesurfer stay in exact time
// alignment.
//
// `timeToX` / `xToTime` are the primitives. `beatToX`, `xToBeat` and
// `beatToBarBeat` go through the real beat list. Pure and unit-tested.

export interface BeatLike {
  time: number;
  beat: number;
  bar: number;
  type?: string;
}

export interface BarLine {
  /** 1-based bar number */
  bar: number;
  /** real start time (seconds) */
  time: number;
  /** x within the body column (seconds * pxPerSec), label column NOT included */
  x: number;
  /** true when the bar's first beat is a downbeat (taller ruler tick) */
  downbeat: boolean;
  /** true when the line is extrapolated past the last real beat */
  extrapolated: boolean;
}

export interface BarBeat {
  bar: number;
  beat: number;
}

const clamp = (value: number, min: number, max: number): number =>
  value < min ? min : value > max ? max : value;

/** First-seen time for each distinct bar number, in time order. */
export function barStartTimes(beats: readonly BeatLike[]): number[] {
  const out: number[] = [];
  let lastBar: number | null = null;
  for (const b of beats) {
    if (b.bar !== lastBar) {
      out.push(b.time);
      lastBar = b.bar;
    }
  }
  return out;
}

function median(sorted: number[]): number {
  const n = sorted.length;
  if (n === 0) return 0;
  const mid = n >> 1;
  return n % 2 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
}

/**
 * Median real bar length from the beat list. Falls back to 4x the median beat
 * interval, then to `fallback`, when there are too few bars to measure.
 */
export function medianBarSeconds(
  beats: readonly BeatLike[],
  fallback = 2,
): number {
  const starts = barStartTimes(beats);
  if (starts.length >= 2) {
    const durations: number[] = [];
    for (let i = 1; i < starts.length; i += 1) {
      durations.push(starts[i]! - starts[i - 1]!);
    }
    durations.sort((a, b) => a - b);
    const m = median(durations);
    if (m > 0) return m;
  }
  if (beats.length >= 2) {
    const intervals: number[] = [];
    for (let i = 1; i < beats.length; i += 1) {
      intervals.push(beats[i]!.time - beats[i - 1]!.time);
    }
    intervals.sort((a, b) => a - b);
    const m = median(intervals);
    if (m > 0) return m * 4;
  }
  return fallback;
}

export interface CoordsInput {
  beats: readonly BeatLike[];
  duration: number;
  /** the zoom control value (14-360); drives pxPerSec via medianBarSeconds */
  pxPerBar: number;
}

export interface Coords {
  readonly pxPerBar: number;
  readonly pxPerSec: number;
  readonly medianBarSeconds: number;
  readonly duration: number;
  /** total scrollable body width in px (label column NOT included) */
  readonly timelineW: number;
  readonly beats: readonly BeatLike[];
  readonly barLines: readonly BarLine[];
  timeToX(time: number): number;
  xToTime(x: number): number;
  beatToX(beatIndex: number): number;
  /** nearest beat index to an x within the body column */
  xToBeat(x: number): number;
  /** bar/beat for a beat index (1-based bar, 1-based beat) */
  beatToBarBeat(beatIndex: number): BarBeat;
  /** bar/beat for a time — the last beat at or before `time` */
  timeToBarBeat(time: number): BarBeat;
  /** index of the last beat at or before `time` (>= 0 once beats exist) */
  beatIndexAtTime(time: number): number;
}

/** Bar lines at real bar-start times, extrapolated past the last beat. */
export function buildBarLines(
  beats: readonly BeatLike[],
  duration: number,
  mbs: number,
  timeToX: (t: number) => number,
): BarLine[] {
  const seen = new Map<number, { time: number; downbeat: boolean }>();
  for (const b of beats) {
    if (!seen.has(b.bar)) {
      seen.set(b.bar, {
        time: b.time,
        downbeat: b.type === "downbeat" || b.beat === 1,
      });
    }
  }
  const lines: BarLine[] = [...seen.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([bar, info]) => ({
      bar,
      time: info.time,
      x: timeToX(info.time),
      downbeat: info.downbeat,
      extrapolated: false,
    }));

  if (mbs > 0 && duration > 0) {
    const last = lines.at(-1);
    let bar = last ? last.bar : 0;
    let time = last ? last.time : 0;
    // guard against pathological beat data producing a runaway loop
    for (let guard = 0; guard < 100_000; guard += 1) {
      time += mbs;
      bar += 1;
      if (time > duration) break;
      lines.push({
        bar,
        time,
        x: timeToX(time),
        downbeat: true,
        extrapolated: true,
      });
    }
  }
  return lines;
}

export function makeCoords(input: CoordsInput): Coords {
  const beats = input.beats;
  const duration = Math.max(input.duration, 0);
  const mbs = medianBarSeconds(beats);
  const pxPerSec = mbs > 0 ? input.pxPerBar / mbs : input.pxPerBar;
  const timelineW = Math.max(Math.ceil(duration * pxPerSec), 1);

  const timeToX = (time: number): number =>
    clamp(Number(time) || 0, 0, duration) * pxPerSec;
  const xToTime = (x: number): number =>
    clamp(pxPerSec > 0 ? x / pxPerSec : 0, 0, duration);

  const beatIndexAtTime = (time: number): number => {
    if (beats.length === 0) return -1;
    const t = Number(time) || 0;
    // binary search: last beat with time <= t
    let lo = 0;
    let hi = beats.length - 1;
    if (t < beats[0]!.time) return 0;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (beats[mid]!.time <= t) lo = mid;
      else hi = mid - 1;
    }
    return lo;
  };

  const beatToX = (beatIndex: number): number => {
    const beat = beats[clamp(beatIndex, 0, beats.length - 1)];
    return beat ? timeToX(beat.time) : 0;
  };

  const xToBeat = (x: number): number => {
    if (beats.length === 0) return -1;
    const t = xToTime(x);
    const i = beatIndexAtTime(t);
    const next = beats[i + 1];
    if (next && Math.abs(next.time - t) < Math.abs(t - beats[i]!.time)) {
      return i + 1;
    }
    return i;
  };

  const beatToBarBeat = (beatIndex: number): BarBeat => {
    const beat = beats[clamp(beatIndex, 0, beats.length - 1)];
    return beat ? { bar: beat.bar, beat: beat.beat } : { bar: 1, beat: 1 };
  };

  const timeToBarBeat = (time: number): BarBeat => {
    const i = beatIndexAtTime(time);
    return i < 0 ? { bar: 1, beat: 1 } : beatToBarBeat(i);
  };

  const barLines = buildBarLines(beats, duration, mbs, timeToX);

  return {
    pxPerBar: input.pxPerBar,
    pxPerSec,
    medianBarSeconds: mbs,
    duration,
    timelineW,
    beats,
    barLines,
    timeToX,
    xToTime,
    beatToX,
    xToBeat,
    beatToBarBeat,
    timeToBarBeat,
    beatIndexAtTime,
  };
}
