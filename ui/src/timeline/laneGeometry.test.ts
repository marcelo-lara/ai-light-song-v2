import { describe, expect, it } from "vitest";

import {
  bucketDrums,
  bucketLevels,
  bucketSeconds,
  envelopeRowGeometry,
  fftBandRows,
  fftVisibleIntensity,
  rmsVisibleIntensity,
  stemRows,
  subLabelX,
} from "./laneGeometry";

describe("bucketSeconds", () => {
  it("never goes below one pixel per bucket", () => {
    expect(bucketSeconds(0.05, 100, 0.05)).toBeCloseTo(0.05);
    expect(bucketSeconds(0.05, 5, 0.05)).toBeCloseTo(0.2); // 1/5
    expect(bucketSeconds(null, 4, 0.01)).toBeCloseTo(0.25); // 1/4 beats fallback
  });
});

describe("fftBandRows", () => {
  it("band 0 (Sub) is the bottom row, last band the top", () => {
    const rows = fftBandRows(7, 84, 6, 6);
    expect(rows).toHaveLength(7);
    const sub = rows[0]!;
    const brilliance = rows[6]!;
    expect(sub.top).toBeGreaterThan(brilliance.top);
    // rows span the drawable area 6 .. 78
    expect(brilliance.top).toBe(6);
    expect(sub.top + sub.height).toBe(78);
  });

  it("edges are integer-rounded and contiguous", () => {
    const rows = fftBandRows(3, 84, 6, 6);
    for (const r of rows) expect(Number.isInteger(r.top)).toBe(true);
    // display order bottom→top: rows[0].top == rows[1].top + rows[1].height
    expect(rows[0]!.top).toBe(rows[1]!.top + rows[1]!.height);
  });
});

describe("visibility floors", () => {
  it("fftVisibleIntensity floors at 0.02 then rescales by /0.98", () => {
    expect(fftVisibleIntensity(0.02)).toBeNull();
    expect(fftVisibleIntensity(0.01)).toBeNull();
    expect(fftVisibleIntensity(1)).toBeCloseTo(1);
    expect(fftVisibleIntensity(0.51)).toBeCloseTo((0.51 - 0.02) / 0.98);
  });
  it("rmsVisibleIntensity behaves the same", () => {
    expect(rmsVisibleIntensity(0.02)).toBeNull();
    expect(rmsVisibleIntensity(0.5)).toBeCloseTo((0.5 - 0.02) / 0.98);
  });
});

describe("stemRows", () => {
  it("rowHeight = (112 - 10 - (n-1)*2) / n for 5 stems", () => {
    const rows = stemRows(112, 5, 5, 5, 2);
    expect(rows).toHaveLength(5);
    expect(rows[0]!.rowHeight).toBeCloseTo((112 - 10 - 4 * 2) / 5); // 18.8
    expect(rows[0]!.rowTop).toBe(5);
    expect(rows[1]!.rowTop).toBeCloseTo(5 + 18.8 + 2);
  });
});

describe("envelopeRowGeometry", () => {
  it("baseline = rowTop + rowHeight - 4, amplitude = max(6, rowHeight - 14)", () => {
    expect(envelopeRowGeometry(5, 18.8)).toEqual({ baseline: 19.8, amplitude: 6 });
    expect(envelopeRowGeometry(10, 40)).toEqual({ baseline: 46, amplitude: 26 });
  });
});

describe("subLabelX", () => {
  it("is round(scrollStart * pxPerSec) + 6", () => {
    expect(subLabelX(0, 90)).toBe(6);
    expect(subLabelX(12.34, 90)).toBe(Math.round(12.34 * 90) + 6);
  });
});

describe("bucketLevels", () => {
  const frames = [
    { start_s: 0.0, end_s: 0.05, levels: [0.1, 0.9] },
    { start_s: 0.05, end_s: 0.1, levels: [0.5, 0.2] },
    { start_s: 0.1, end_s: 0.15, levels: [0.3, 0.3] },
  ];
  it("groups frames into fixed windows, tracking per-channel max + average", () => {
    const buckets = bucketLevels(frames, 2, 0.1, -1, 10);
    expect(buckets).toHaveLength(2);
    expect(buckets[0]!.maxes).toEqual([0.5, 0.9]);
    expect(buckets[0]!.averages[0]).toBeCloseTo(0.3);
    expect(buckets[1]!.maxes).toEqual([0.3, 0.3]);
  });
  it("drops frames whose span is fully outside [start, end]", () => {
    const buckets = bucketLevels(frames, 2, 0.1, 0.08, 10);
    // frame0 (0.0–0.05) is fully before 0.08 and is dropped; the rest stay
    expect(buckets.map((b) => b.start_s)).toEqual([0, 0.1]);
    expect(buckets[0]!.maxes).toEqual([0.5, 0.2]);
  });
});

describe("bucketDrums", () => {
  it("counts kick / snare / hat per window", () => {
    const events = [
      { time: 0.1, event_type: "kick" },
      { time: 0.2, event_type: "hat" },
      { time: 0.9, event_type: "kick" },
      { time: 1.1, event_type: "snare" },
    ];
    const buckets = bucketDrums(events, 1, -1, 10);
    expect(buckets).toHaveLength(2);
    expect(buckets[0]!.byType).toEqual({ kick: 2, snare: 0, hat: 1 });
    expect(buckets[0]!.count).toBe(3);
    expect(buckets[1]!.byType).toEqual({ kick: 0, snare: 1, hat: 0 });
  });
});
