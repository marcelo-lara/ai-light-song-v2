import { describe, expect, it } from "vitest";

import type { SparseBlock } from "../timeline/laneContent";

import { activeBlockIndex, isInPlayheadWindow } from "./laneEvents";

function block(over: Partial<SparseBlock> & { id: string }): SparseBlock {
  return {
    start_s: 0,
    end_s: 1,
    label: over.id,
    laneLabel: "Human Hints",
    caption: `caption ${over.id}`,
    reference: over.id,
    detail: "-",
    summary: "-",
    raw: {},
    ...over,
  };
}

const BLOCKS = [
  block({ id: "a", start_s: 10, end_s: 20 }),
  block({ id: "b", start_s: 30, end_s: 40 }),
];

describe("activeBlockIndex", () => {
  it("returns -1 for an empty list", () => {
    expect(activeBlockIndex([], 5)).toBe(-1);
  });

  it("returns -1 before the first block", () => {
    expect(activeBlockIndex(BLOCKS, 5)).toBe(-1);
  });

  it("returns -1 in the gap between two blocks", () => {
    expect(activeBlockIndex(BLOCKS, 25)).toBe(-1);
  });

  it("is active exactly at start_s (half-open)", () => {
    expect(activeBlockIndex(BLOCKS, 10)).toBe(0);
    expect(activeBlockIndex(BLOCKS, 30)).toBe(1);
  });

  it("is inactive exactly at end_s", () => {
    expect(activeBlockIndex(BLOCKS, 20)).toBe(-1);
  });

  it("at a shared boundary the starting block wins", () => {
    const abut = [
      block({ id: "a", start_s: 0, end_s: 10 }),
      block({ id: "b", start_s: 10, end_s: 20 }),
    ];
    expect(activeBlockIndex(abut, 10)).toBe(1);
  });

  it("overlapping blocks resolve to the later start (innermost)", () => {
    const nested = [
      block({ id: "outer", start_s: 0, end_s: 100 }),
      block({ id: "inner", start_s: 40, end_s: 60 }),
    ];
    expect(activeBlockIndex(nested, 50)).toBe(1);
    expect(activeBlockIndex(nested, 30)).toBe(0);
    expect(activeBlockIndex(nested, 70)).toBe(0);
  });

  it("a degenerate block (end_s <= start_s) is never active (D5)", () => {
    const degenerate = [
      block({ id: "point", start_s: 10, end_s: 10 }),
      block({ id: "reversed", start_s: 30, end_s: 25 }),
    ];
    expect(activeBlockIndex(degenerate, 10)).toBe(-1);
    expect(activeBlockIndex(degenerate, 27)).toBe(-1);
    expect(activeBlockIndex(degenerate, 30)).toBe(-1);
  });
});

describe("isInPlayheadWindow", () => {
  it("is true inside [start_s, end_s) and false outside it", () => {
    const b = block({ id: "a", start_s: 10, end_s: 20 });
    expect(isInPlayheadWindow(b, 5)).toBe(false);
    expect(isInPlayheadWindow(b, 10)).toBe(true);
    expect(isInPlayheadWindow(b, 15)).toBe(true);
    expect(isInPlayheadWindow(b, 20)).toBe(false);
  });

  it("multiple overlapping blocks can all be in-window at once", () => {
    const outer = block({ id: "outer", start_s: 0, end_s: 100 });
    const inner = block({ id: "inner", start_s: 40, end_s: 60 });
    expect(isInPlayheadWindow(outer, 50)).toBe(true);
    expect(isInPlayheadWindow(inner, 50)).toBe(true);
  });

  it("a degenerate block (end_s <= start_s) is never in-window (D5)", () => {
    expect(isInPlayheadWindow(block({ id: "point", start_s: 10, end_s: 10 }), 10)).toBe(
      false,
    );
    expect(
      isInPlayheadWindow(block({ id: "reversed", start_s: 30, end_s: 25 }), 27),
    ).toBe(false);
  });
});
