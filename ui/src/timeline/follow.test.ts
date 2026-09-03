import { describe, expect, it } from "vitest";

import {
  DEFAULT_FOLLOW_PLAYHEAD,
  followScrollLeft,
  isUserScroll,
  LABEL_WIDTH,
  loadFollowPlayhead,
  saveFollowPlayhead,
} from "./follow";

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

describe("isUserScroll (plan v1.5 D6)", () => {
  it("is true when the effect has written nothing yet", () => {
    expect(isUserScroll(0, null)).toBe(true);
    expect(isUserScroll(4200, null)).toBe(true);
  });

  it("is false when the observed offset is within tolerance of the last write", () => {
    expect(isUserScroll(500, 500)).toBe(false);
    expect(isUserScroll(500.6, 500)).toBe(false);
  });

  it("is true when the observed offset is 400 px from the last write", () => {
    expect(isUserScroll(900, 500)).toBe(true);
  });

  it("is false exactly at the tolerance boundary", () => {
    expect(isUserScroll(501, 500)).toBe(false);
    expect(isUserScroll(500, 501)).toBe(false);
  });
});

describe("follow-playhead persistence (plan v1.5 D7)", () => {
  it("round-trips through localStorage", () => {
    saveFollowPlayhead(false);
    expect(loadFollowPlayhead()).toBe(false);
    saveFollowPlayhead(true);
    expect(loadFollowPlayhead()).toBe(true);
  });

  it("falls back to the default when storage is blocked", () => {
    const real = globalThis.localStorage;
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() {
        throw new Error("blocked");
      },
    });
    try {
      expect(loadFollowPlayhead()).toBe(DEFAULT_FOLLOW_PLAYHEAD);
      expect(() => saveFollowPlayhead(false)).not.toThrow();
    } finally {
      Object.defineProperty(globalThis, "localStorage", {
        configurable: true,
        value: real,
      });
    }
  });
});
