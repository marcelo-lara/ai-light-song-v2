import { describe, expect, it } from "vitest";

import {
  clampPxPerBar,
  fitToWidthPxPerBar,
  fitToWidthPxPerSec,
  ppbLabel,
  PX_PER_BAR_MAX,
  PX_PER_BAR_MIN,
  pxPerBarFromPxPerSec,
  pxPerSecFromPxPerBar,
  semanticZoom,
  zoomInPxPerBar,
  zoomOutPxPerBar,
} from "./zoom";

describe("clamp + zoom steps", () => {
  it("clamps to the 14-180 range and rounds", () => {
    expect(clampPxPerBar(5)).toBe(PX_PER_BAR_MIN);
    expect(clampPxPerBar(999)).toBe(PX_PER_BAR_MAX);
    expect(clampPxPerBar(61.6)).toBe(62);
  });

  it("zoom in / out step by 1.3x", () => {
    expect(zoomInPxPerBar(50)).toBe(65);
    expect(zoomOutPxPerBar(65)).toBe(50);
  });

  it("ppbLabel is the canvas-style px/bar string", () => {
    expect(ppbLabel(62)).toBe("62 px/bar");
  });
});

describe("pxPerBar <-> pxPerSec", () => {
  it("round-trips through medianBarSeconds", () => {
    const mbs = 1.94;
    const pps = pxPerSecFromPxPerBar(62, mbs);
    expect(pxPerBarFromPxPerSec(pps, mbs)).toBeCloseTo(62, 9);
  });
});

describe("fit to width", () => {
  it("solves pxPerSec = (viewport - 212 - 12) / duration", () => {
    expect(fitToWidthPxPerSec(1224, 200)).toBeCloseTo((1224 - 224) / 200, 9);
  });

  it("back-solves a clamped pxPerBar for the label", () => {
    // usable 1000 px, 100 s => 10 px/s; * 2 s/bar => 20 px/bar
    expect(fitToWidthPxPerBar(1224, 100, 2)).toBe(20);
    // a very long song clamps at the minimum
    expect(fitToWidthPxPerBar(1224, 100_000, 2)).toBe(PX_PER_BAR_MIN);
  });
});

describe("semanticZoom threshold table (design notes §2)", () => {
  it("bar-label cadence by pxPerBar", () => {
    expect(semanticZoom(180).barLabelEvery).toBe(1);
    expect(semanticZoom(56).barLabelEvery).toBe(1);
    expect(semanticZoom(55).barLabelEvery).toBe(2);
    expect(semanticZoom(26).barLabelEvery).toBe(2);
    expect(semanticZoom(25).barLabelEvery).toBe(4);
    expect(semanticZoom(16).barLabelEvery).toBe(4);
    expect(semanticZoom(15).barLabelEvery).toBe(8);
  });

  it("beat sub-ticks only at pxPerBar >= 44", () => {
    expect(semanticZoom(44).beatSubTicks).toBe(true);
    expect(semanticZoom(43).beatSubTicks).toBe(false);
  });
});
