import { describe, expect, it } from "vitest";

import { followScrollLeft, LABEL_WIDTH } from "./follow";

const base = {
  scrollLeft: 0,
  viewportWidth: 1000,
  maxScrollLeft: 10_000,
  playing: true,
};

describe("followScrollLeft", () => {
  it("does nothing while paused", () => {
    expect(followScrollLeft({ ...base, playing: false, playheadX: 99_999 })).toBe(0);
  });

  it("leaves scroll alone while the playhead is comfortably in view", () => {
    expect(followScrollLeft({ ...base, playheadX: 400 })).toBe(0);
  });

  it("recenters to 55% when the playhead passes viewport - 120", () => {
    // playheadX 900 > 0 + 1000 - 120 = 880
    expect(followScrollLeft({ ...base, playheadX: 900 })).toBe(900 - 1000 * 0.55);
  });

  it("scrolls back when the playhead slips behind the label column", () => {
    const scrollLeft = 5000;
    const playheadX = scrollLeft + LABEL_WIDTH - 10; // behind the sticky column
    expect(
      followScrollLeft({ ...base, scrollLeft, playheadX }),
    ).toBe(playheadX - LABEL_WIDTH - 40);
  });

  it("clamps to [0, maxScrollLeft]", () => {
    expect(followScrollLeft({ ...base, playheadX: 50 })).toBe(0);
    expect(
      followScrollLeft({ ...base, scrollLeft: 9999, playheadX: 999_999, maxScrollLeft: 12_000 }),
    ).toBe(12_000);
  });
});
