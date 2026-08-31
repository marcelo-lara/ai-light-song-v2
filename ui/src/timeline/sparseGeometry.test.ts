import { describe, expect, it } from "vitest";

import {
  blockBox,
  blockTextLayout,
  packRows,
  COMPACT_LANE_IDS,
} from "./sparseGeometry";

describe("blockBox", () => {
  it("floors width to 2px and uses the time→x mapping", () => {
    const timeToX = (t: number) => t * 10;
    expect(blockBox(1, 5, timeToX)).toEqual({ x: 10, width: 40 });
    expect(blockBox(1, 1, timeToX)).toEqual({ x: 10, width: 2 });
  });
});

describe("packRows — non-compact lane", () => {
  it("gives every block one full-height band row", () => {
    const packed = packRows(
      [
        { x: 0, width: 100 },
        { x: 50, width: 100 },
      ],
      { laneId: "sections", laneHeight: 84 },
    );
    expect(packed).toHaveLength(2);
    expect(packed.every((p) => p.rowIndex === 0)).toBe(true);
    expect(packed[0]!.height).toBe(84 - 12);
    expect(packed[0]!.y).toBe(6);
  });
});

describe("packRows — compact lane", () => {
  it("stacks overlapping blocks into separate rows", () => {
    const packed = packRows(
      [
        { x: 0, width: 100 }, // row 0
        { x: 10, width: 100 }, // overlaps -> row 1
        { x: 30, width: 100 }, // overlaps both -> row 2
        { x: 200, width: 50 }, // clear -> back to row 0
      ],
      { laneId: "machineEvents", laneHeight: 84 },
    );
    const byX = new Map(packed.map((p) => [p.x, p.rowIndex]));
    expect(byX.get(0)).toBe(0);
    expect(byX.get(10)).toBe(1);
    expect(byX.get(30)).toBe(2);
    expect(byX.get(200)).toBe(0);
    // three rows share the band, so each is shorter than the full band
    expect(packed.find((p) => p.x === 0)!.height).toBeLessThan(72);
  });

  it("falls back to a single row when there is 0/1 block", () => {
    const packed = packRows([{ x: 0, width: 10 }], {
      laneId: "phrases",
      laneHeight: 84,
    });
    expect(packed[0]!.height).toBe(72);
  });

  it("registers the compact lane ids the old canvas painter used", () => {
    expect([...COMPACT_LANE_IDS].sort()).toEqual([
      "identifierHints",
      "machineEvents",
      "mlEvents",
      "phrases",
    ]);
  });
});

describe("blockTextLayout", () => {
  it("hides all text below 36px, adds caption at 96px + tall, wide label at 120px", () => {
    expect(blockTextLayout(20, 72).showLabel).toBe(false);
    expect(blockTextLayout(40, 72).showLabel).toBe(true);
    expect(blockTextLayout(40, 72).showCaption).toBe(false);
    expect(blockTextLayout(100, 72).showCaption).toBe(true);
    expect(blockTextLayout(100, 20).showCaption).toBe(false);
    expect(blockTextLayout(130, 72).showWideLabel).toBe(true);
    expect(blockTextLayout(90, 72).showWideLabel).toBe(false);
  });
});
