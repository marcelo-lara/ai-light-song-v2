import { describe, expect, it } from "vitest";

import {
  applyDrag,
  clampTimes,
  computeDrag,
  isClick,
  MIN_GAP_S,
  nearestSnapPx,
  pxToSeconds,
  resolveZone,
  snapEdge,
} from "./hintDrag";

describe("resolveZone", () => {
  it("returns left within 6px of the left edge", () => {
    expect(resolveZone(0, 100)).toBe("left");
    expect(resolveZone(6, 100)).toBe("left");
  });

  it("returns right within 6px of the right edge", () => {
    expect(resolveZone(100, 100)).toBe("right");
    expect(resolveZone(94, 100)).toBe("right");
  });

  it("returns interior in the middle", () => {
    expect(resolveZone(50, 100)).toBe("interior");
    expect(resolveZone(7, 100)).toBe("interior");
    expect(resolveZone(93, 100)).toBe("interior");
  });

  it("is interior-only when the block is narrower than 18px", () => {
    expect(resolveZone(0, 17)).toBe("interior");
    expect(resolveZone(16, 17)).toBe("interior");
  });
});

describe("pxToSeconds", () => {
  it("converts a px delta via pxPerSec", () => {
    expect(pxToSeconds(60, 30)).toBe(2);
    expect(pxToSeconds(-45, 30)).toBe(-1.5);
  });

  it("is 0 when pxPerSec is not usable", () => {
    expect(pxToSeconds(60, 0)).toBe(0);
    expect(pxToSeconds(60, -1)).toBe(0);
  });
});

describe("applyDrag", () => {
  const orig = { start: 10, end: 20 };

  it("left moves start only", () => {
    expect(applyDrag("left", orig, 3)).toEqual({ start: 13, end: 20 });
  });

  it("right moves end only", () => {
    expect(applyDrag("right", orig, -4)).toEqual({ start: 10, end: 16 });
  });

  it("interior moves both by the same dt", () => {
    expect(applyDrag("interior", orig, 5)).toEqual({ start: 15, end: 25 });
  });
});

describe("nearestSnapPx / snapEdge", () => {
  it("snaps to a target within 5px", () => {
    expect(nearestSnapPx(103, [100, 200])).toBe(100);
    expect(nearestSnapPx(100, [95, 105])).toBe(95); // tie -> first
  });

  it("does not snap beyond 5px", () => {
    expect(nearestSnapPx(106, [100, 200])).toBeNull();
  });

  it("snaps at exactly 5px", () => {
    expect(nearestSnapPx(105, [100])).toBe(100);
  });

  it("nearest of several wins", () => {
    expect(nearestSnapPx(103, [100, 104, 108])).toBe(104);
  });

  it("snapEdge falls back to the original value", () => {
    expect(snapEdge(500, [100, 200])).toBe(500);
    expect(snapEdge(102, [100])).toBe(100);
  });
});

describe("clampTimes", () => {
  it("keeps start >= 0 on a left-edge drag", () => {
    expect(clampTimes("left", { start: -3, end: 10 }, 100)).toEqual({
      start: 0,
      end: 10,
    });
  });

  it("keeps end <= duration on a right-edge drag", () => {
    expect(clampTimes("right", { start: 10, end: 120 }, 100)).toEqual({
      start: 10,
      end: 100,
    });
  });

  it("stops a left edge at the min-gap limit", () => {
    const r = clampTimes("left", { start: 19.99, end: 20 }, 100);
    expect(r.end).toBe(20);
    expect(r.start).toBeCloseTo(20 - MIN_GAP_S, 10);
  });

  it("stops a right edge at the min-gap limit", () => {
    const r = clampTimes("right", { start: 20, end: 20.01 }, 100);
    expect(r.start).toBe(20);
    expect(r.end).toBeCloseTo(20 + MIN_GAP_S, 10);
  });

  it("interior drag preserves length at the 0 boundary", () => {
    expect(clampTimes("interior", { start: -5, end: 5 }, 100)).toEqual({
      start: 0,
      end: 10,
    });
  });

  it("interior drag preserves length at the duration boundary", () => {
    expect(clampTimes("interior", { start: 95, end: 115 }, 100)).toEqual({
      start: 80,
      end: 100,
    });
  });
});

describe("isClick", () => {
  it("is a click below 4px of travel", () => {
    expect(isClick(0)).toBe(true);
    expect(isClick(3.9)).toBe(true);
  });

  it("is a drag at exactly 4px and above", () => {
    expect(isClick(4)).toBe(false);
    expect(isClick(10)).toBe(false);
  });
});

describe("computeDrag", () => {
  const pxPerSec = 20; // 1s = 20px
  const duration = 100;

  it("right-edge drag: px delta -> time delta on end only", () => {
    const r = computeDrag({
      zone: "right",
      original: { start: 10, end: 20 },
      dxPx: 40,
      pxPerSec,
      duration,
    });
    expect(r).toEqual({ start: 10, end: 22 });
  });

  it("left-edge drag moves start only", () => {
    const r = computeDrag({
      zone: "left",
      original: { start: 10, end: 20 },
      dxPx: -30,
      pxPerSec,
      duration,
    });
    expect(r).toEqual({ start: 8.5, end: 20 });
  });

  it("interior drag moves the whole box", () => {
    const r = computeDrag({
      zone: "interior",
      original: { start: 10, end: 20 },
      dxPx: 60,
      pxPerSec,
      duration,
    });
    expect(r).toEqual({ start: 13, end: 23 });
  });

  it("snaps a dragged edge to a nearby other-block edge", () => {
    // other block left edge at 30s -> 600px. Drag block-1 right edge from
    // 20s(400px) by +196px -> 596px, within 5px of 600 -> snaps to 30s.
    const r = computeDrag({
      zone: "right",
      original: { start: 10, end: 20 },
      dxPx: 196,
      pxPerSec,
      duration,
      snapTargetsPx: [600],
    });
    expect(r.end).toBeCloseTo(30, 10);
    expect(r.start).toBe(10);
  });

  it("does not snap when no target is within 5px", () => {
    const r = computeDrag({
      zone: "right",
      original: { start: 10, end: 20 },
      dxPx: 180, // 580px, 20px from 600
      pxPerSec,
      duration,
      snapTargetsPx: [600],
    });
    expect(r.end).toBeCloseTo(29, 10);
  });

  it("interior move snaps whichever edge is closest to a target", () => {
    // box 10-20s (200-400px). Move +199px: start 399px, end 599px.
    // targets: 400 (2px from start=402? ) compute: start=399, target 400 -> 1px.
    // end=599, target 601 -> 2px. start is closer -> shift +1px = +0.05s.
    const r = computeDrag({
      zone: "interior",
      original: { start: 10, end: 20 },
      dxPx: 199,
      pxPerSec,
      duration,
      snapTargetsPx: [400, 601],
    });
    expect(r.start * pxPerSec).toBeCloseTo(400, 6);
    expect(r.end - r.start).toBeCloseTo(10, 6);
  });

  it("item 9: snapAnchor 'start' ignores a target near the end edge", () => {
    // box 10-20s (200-400px). Move +199px -> start 399px, end 599px.
    // Only target is near the end (600px); with anchor "start" it is ignored.
    const r = computeDrag({
      zone: "interior",
      original: { start: 10, end: 20 },
      dxPx: 199,
      pxPerSec,
      duration,
      snapTargetsPx: [600],
      snapAnchor: "start",
    });
    expect(r.start * pxPerSec).toBeCloseTo(399, 6);
    expect(r.end - r.start).toBeCloseTo(10, 6);
  });

  it("item 9: snapAnchor 'start' snaps the start and preserves duration", () => {
    const r = computeDrag({
      zone: "interior",
      original: { start: 10, end: 20 },
      dxPx: 199,
      pxPerSec,
      duration,
      snapTargetsPx: [400, 601],
      snapAnchor: "start",
    });
    expect(r.start * pxPerSec).toBeCloseTo(400, 6);
    expect(r.end - r.start).toBeCloseTo(10, 6);
  });

  it("clamps the result to the timeline", () => {
    const r = computeDrag({
      zone: "interior",
      original: { start: 90, end: 100 },
      dxPx: 400,
      pxPerSec,
      duration,
    });
    expect(r).toEqual({ start: 90, end: 100 });
  });
});
