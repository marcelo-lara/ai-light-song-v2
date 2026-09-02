import { describe, expect, it } from "vitest";

import {
  barStartTimes,
  buildBarLines,
  makeCoords,
  medianBarSeconds,
  type BeatLike,
} from "./coords";

/** 4/4 beats with a deliberate tempo drift: each bar is `step` longer. */
function driftBeats(barCount: number, firstBarSeconds = 2.0, step = 0.4): BeatLike[] {
  const beats: BeatLike[] = [];
  let t = 0;
  for (let bar = 1; bar <= barCount; bar += 1) {
    const barSeconds = firstBarSeconds + (bar - 1) * step;
    const beatSeconds = barSeconds / 4;
    for (let beat = 1; beat <= 4; beat += 1) {
      beats.push({
        time: Number(t.toFixed(6)),
        beat,
        bar,
        type: beat === 1 ? "downbeat" : "beat",
      });
      t += beatSeconds;
    }
  }
  return beats;
}

describe("medianBarSeconds", () => {
  it("takes the median real bar length under tempo drift", () => {
    // bar lengths: 2.0, 2.4, 2.8, 3.2  ->  median (2.4 + 2.8) / 2 = 2.6
    const beats = driftBeats(5);
    expect(barStartTimes(beats)).toHaveLength(5);
    expect(medianBarSeconds(beats)).toBeCloseTo(2.6, 6);
  });

  it("falls back to 4x the median beat interval when there is only one bar", () => {
    const beats: BeatLike[] = [
      { time: 0, beat: 1, bar: 1, type: "downbeat" },
      { time: 0.5, beat: 2, bar: 1 },
      { time: 1.0, beat: 3, bar: 1 },
      { time: 1.5, beat: 4, bar: 1 },
    ];
    expect(medianBarSeconds(beats)).toBeCloseTo(2.0, 6);
  });

  it("uses the fallback with no beats", () => {
    expect(medianBarSeconds([], 1.75)).toBe(1.75);
  });
});

describe("makeCoords time <-> x", () => {
  const beats = driftBeats(6);
  const duration = 24;
  const coords = makeCoords({ beats, duration, pxPerBar: 60 });

  it("pxPerSec = pxPerBar / medianBarSeconds", () => {
    expect(coords.pxPerSec).toBeCloseTo(60 / coords.medianBarSeconds, 9);
  });

  it("timeToX / xToTime round-trip inside the song", () => {
    for (const t of [0, 1.234, 7.5, 15.9, 23.999]) {
      expect(coords.xToTime(coords.timeToX(t))).toBeCloseTo(t, 6);
    }
  });

  it("clamps outside the song", () => {
    expect(coords.timeToX(-5)).toBe(0);
    expect(coords.xToTime(-10)).toBe(0);
    expect(coords.xToTime(coords.timelineW * 10)).toBeCloseTo(duration, 6);
  });

  it("timelineW = duration * pxPerSec", () => {
    expect(coords.timelineW).toBe(Math.ceil(duration * coords.pxPerSec));
  });
});

describe("bar lines under tempo drift", () => {
  const beats = driftBeats(5);
  const coords = makeCoords({ beats, duration: 20, pxPerBar: 48 });

  it("places a line at each bar's real start time (not equal pixel widths)", () => {
    const starts = barStartTimes(beats);
    const realLines = coords.barLines.filter((l) => !l.extrapolated);
    expect(realLines.map((l) => l.time)).toEqual(starts);

    const gaps: number[] = [];
    for (let i = 1; i < realLines.length; i += 1) {
      gaps.push(realLines[i]!.x - realLines[i - 1]!.x);
    }
    // drift => strictly increasing pixel gaps, never uniform
    for (let i = 1; i < gaps.length; i += 1) {
      expect(gaps[i]!).toBeGreaterThan(gaps[i - 1]!);
    }
  });

  it("extrapolates bar lines past the last beat up to the duration", () => {
    const extrapolated = coords.barLines.filter((l) => l.extrapolated);
    expect(extrapolated.length).toBeGreaterThan(0);
    for (const line of coords.barLines) {
      expect(line.time).toBeLessThanOrEqual(20 + 1e-9);
    }
  });

  it("buildBarLines is a pure helper over a timeToX fn", () => {
    const lines = buildBarLines(beats, 20, 2.6, (t) => t * 10);
    expect(lines[0]).toMatchObject({ bar: 1, time: 0, x: 0, downbeat: true });
  });
});

describe("beat helpers", () => {
  const beats = driftBeats(4);
  const coords = makeCoords({ beats, duration: 16, pxPerBar: 60 });

  it("beatToBarBeat maps an index to 1-based bar/beat", () => {
    expect(coords.beatToBarBeat(0)).toEqual({ bar: 1, beat: 1 });
    expect(coords.beatToBarBeat(5)).toEqual({ bar: 2, beat: 2 });
  });

  it("timeToBarBeat uses the last beat at or before the time", () => {
    const b6 = beats[6]!; // bar 2, beat 3
    expect(coords.timeToBarBeat(b6.time + 0.01)).toEqual({ bar: b6.bar, beat: b6.beat });
  });

  it("xToBeat returns the nearest beat index", () => {
    const idx = 5;
    const x = coords.beatToX(idx);
    expect(coords.xToBeat(x)).toBe(idx);
    expect(coords.xToBeat(x + 1)).toBe(idx);
  });
});
