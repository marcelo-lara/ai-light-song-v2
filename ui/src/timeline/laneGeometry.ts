// laneGeometry.ts — pure, unit-tested geometry + bucketing maths for the
// canvas data lanes (FFT / RMS / Envelope / drums / energy). Ported from
// ui.old/src/lib/timeline/{fftBandsLane,loudnessLane,drumsLane,seriesLane,
// dynamicHelpers}.js. No canvas, no React — just numbers in, numbers out.
//
// "zoom" in the ported constants === pxPerSec (design notes §2 / item 5 note).

import { clamp01 } from "./palette";

export const FFT_VISIBILITY_FLOOR = 0.02;
export const RMS_VISIBILITY_FLOOR = 0.02;

/** `max(intervalSeconds || fallback, 1 / max(pxPerSec, 1))` — never sub-pixel. */
export function bucketSeconds(
  intervalSeconds: number | null | undefined,
  pxPerSec: number,
  fallback: number,
): number {
  const interval = Number(intervalSeconds) || fallback;
  return Math.max(interval, 1 / Math.max(pxPerSec, 1));
}

/**
 * Row rectangles for an `n`-band FFT lane. Band 0 (Sub) is drawn at the BOTTOM
 * (`displayIndex = bandCount − 1 − bandIndex`); edges are integer-rounded across
 * `laneHeight − topPadding − bottomPadding`. Returned array is indexed by
 * band index (not display index).
 */
export function fftBandRows(
  bandCount: number,
  laneHeight: number,
  topPadding = 6,
  bottomPadding = 6,
): Array<{ top: number; height: number }> {
  const drawable = laneHeight - topPadding - bottomPadding;
  const edges = Array.from({ length: bandCount + 1 }, (_, i) =>
    Math.round(topPadding + (drawable * i) / bandCount),
  );
  return Array.from({ length: bandCount }, (_, bandIndex) => {
    const displayIndex = bandCount - 1 - bandIndex;
    const top = edges[displayIndex]!;
    const bottom = edges[displayIndex + 1]!;
    return { top, height: Math.max(1, bottom - top) };
  });
}

/** FFT visibility floor → rescaled intensity, or null when below the floor. */
export function fftVisibleIntensity(intensity: number): number | null {
  const v = clamp01(intensity);
  if (v <= FFT_VISIBILITY_FLOOR) return null;
  return (v - FFT_VISIBILITY_FLOOR) / (1 - FFT_VISIBILITY_FLOOR);
}

/** RMS visibility floor → rescaled intensity, or null when below the floor. */
export function rmsVisibleIntensity(intensity: number): number | null {
  const v = clamp01(intensity);
  if (v <= RMS_VISIBILITY_FLOOR) return null;
  return (v - RMS_VISIBILITY_FLOOR) / (1 - RMS_VISIBILITY_FLOOR);
}

/**
 * Per-stem row rectangles for the RMS / Envelope lane.
 * `rowHeight = (laneHeight − topPadding − bottomPadding − (n−1)·rowGap) / n`.
 */
export function stemRows(
  laneHeight: number,
  count: number,
  topPadding = 5,
  bottomPadding = 5,
  rowGap = 2,
): Array<{ rowTop: number; rowHeight: number }> {
  const rowHeight =
    (laneHeight - topPadding - bottomPadding - (count - 1) * rowGap) / count;
  return Array.from({ length: count }, (_, i) => ({
    rowTop: topPadding + i * (rowHeight + rowGap),
    rowHeight,
  }));
}

/** Envelope trace geometry per row (design notes §3a). */
export function envelopeRowGeometry(rowTop: number, rowHeight: number): {
  baseline: number;
  amplitude: number;
} {
  return {
    baseline: rowTop + rowHeight - 4,
    amplitude: Math.max(6, rowHeight - 14),
  };
}

/**
 * Sub-label x, anchored to the visible viewport's left edge:
 * `round(scrollStart · pxPerSec) + 6`. `scrollStart` is `scrollLeft / pxPerSec`,
 * so this is effectively `round(scrollLeft) + 6`, recomputed on every scroll.
 */
export function subLabelX(scrollStart: number, pxPerSec: number): number {
  return Math.round(scrollStart * pxPerSec) + 6;
}

// ---------------------------------------------------------------------------
// Bucketing
// ---------------------------------------------------------------------------

export interface LevelBucket {
  start_s: number;
  end_s: number;
  /** per-channel max across the frames in the bucket */
  maxes: number[];
  /** per-channel average across the frames in the bucket */
  averages: number[];
}

interface TimeFrame {
  time?: number | null;
  start_s?: number | null;
  end_s?: number | null;
}

function frameStart(frame: TimeFrame): number {
  return Number(frame.start_s ?? frame.time ?? 0) || 0;
}

/**
 * Bucket `frames` (each with `levels` or `normalized_values`) into fixed
 * `secondsPerBucket` windows within `[start, end]`, tracking per-channel max
 * and average.
 */
export function bucketLevels(
  frames: ReadonlyArray<TimeFrame & { levels?: number[]; normalized_values?: number[] }>,
  channelCount: number,
  secondsPerBucket: number,
  start: number,
  end: number,
): LevelBucket[] {
  const buckets = new Map<
    number,
    { start_s: number; end_s: number; sums: number[]; counts: number[]; maxes: number[] }
  >();
  for (const frame of frames) {
    const s = frameStart(frame);
    const e = Number(frame.end_s ?? s) || s;
    if (e < start || s > end) continue;
    const index = Math.floor(s / secondsPerBucket);
    let bucket = buckets.get(index);
    if (!bucket) {
      bucket = {
        start_s: index * secondsPerBucket,
        end_s: (index + 1) * secondsPerBucket,
        sums: new Array(channelCount).fill(0),
        counts: new Array(channelCount).fill(0),
        maxes: new Array(channelCount).fill(0),
      };
      buckets.set(index, bucket);
    }
    const values = frame.levels ?? frame.normalized_values ?? [];
    for (let c = 0; c < channelCount; c += 1) {
      const v = clamp01(Number(values[c]) || 0);
      bucket.sums[c] = (bucket.sums[c] ?? 0) + v;
      bucket.counts[c] = (bucket.counts[c] ?? 0) + 1;
      bucket.maxes[c] = Math.max(bucket.maxes[c] ?? 0, v);
    }
  }
  return [...buckets.values()]
    .sort((a, b) => a.start_s - b.start_s)
    .map((b) => ({
      start_s: b.start_s,
      end_s: b.end_s,
      maxes: b.maxes,
      averages: b.sums.map((sum, i) => (b.counts[i]! > 0 ? sum / b.counts[i]! : 0)),
    }));
}

export interface DrumBucket {
  start_s: number;
  end_s: number;
  byType: { kick: number; snare: number; hat: number };
  count: number;
}

/** Bucket drum events by `event_type` count (used below the marker-zoom cutoff). */
export function bucketDrums(
  events: ReadonlyArray<{ time: number; event_type: string }>,
  secondsPerBucket: number,
  start: number,
  end: number,
): DrumBucket[] {
  const buckets = new Map<number, DrumBucket>();
  for (const ev of events) {
    const t = Number(ev.time) || 0;
    if (t < start || t > end) continue;
    const index = Math.floor(t / secondsPerBucket);
    let bucket = buckets.get(index);
    if (!bucket) {
      bucket = {
        start_s: index * secondsPerBucket,
        end_s: (index + 1) * secondsPerBucket,
        byType: { kick: 0, snare: 0, hat: 0 },
        count: 0,
      };
      buckets.set(index, bucket);
    }
    bucket.count += 1;
    if (ev.event_type === "kick" || ev.event_type === "snare" || ev.event_type === "hat") {
      bucket.byType[ev.event_type] += 1;
    }
  }
  return [...buckets.values()].sort((a, b) => a.start_s - b.start_s);
}

/** The px/sec at/above which drum events are drawn as individual markers. */
export const DRUM_MARKER_PXPERSEC = 42;
