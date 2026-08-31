// laneState — item 8 ("Hide all" zeroes every visible flag + round-trips) and
// the item 1 `hideAll()` helper it finishes.

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  LANE_DEFS,
  defaultLaneState,
  loadLaneState,
  saveLaneState,
  setAllVisible,
} from "./laneState";

const hideAllReducer = (state: Parameters<typeof setAllVisible>[0]) =>
  setAllVisible(state, false);

describe("item 8 — hide all", () => {
  beforeEach(() => globalThis.localStorage?.clear());
  afterEach(() => globalThis.localStorage?.clear());

  it("zeroes every `visible` flag while preserving `expanded`", () => {
    const before = defaultLaneState();
    const after = hideAllReducer(before);
    for (const def of LANE_DEFS) {
      expect(after[def.id]!.visible).toBe(false);
      expect(after[def.id]!.expanded).toBe(before[def.id]!.expanded);
    }
  });

  it("round-trips through the persistence helper", () => {
    const hidden = hideAllReducer(defaultLaneState());
    saveLaneState(hidden);
    const reloaded = loadLaneState();
    for (const def of LANE_DEFS) expect(reloaded[def.id]!.visible).toBe(false);
  });

  it("individual lanes are still re-showable after hide all", () => {
    const hidden = hideAllReducer(defaultLaneState());
    hidden.waveform = { ...hidden.waveform!, visible: true };
    saveLaneState(hidden);
    const reloaded = loadLaneState();
    expect(reloaded.waveform!.visible).toBe(true);
    expect(reloaded.fftBands!.visible).toBe(false);
  });
});
