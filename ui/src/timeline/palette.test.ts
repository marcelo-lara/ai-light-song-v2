import { describe, expect, it } from "vitest";

import {
  bandColor,
  clamp01,
  FFT_BAND_HUES,
  LANE_HEIGHTS,
  SOURCE_COLORS,
  sourceColor,
  sourceRgb,
} from "./palette";

describe("palette — carried over verbatim from the previous app", () => {
  it("has the 7 FFT band hues, Sub … Brilliance", () => {
    expect([...FFT_BAND_HUES]).toEqual([22, 46, 88, 138, 164, 186, 196]);
  });

  it("bandColor is hsla(hue, 84%, 58%, v*0.9) with the per-index hue", () => {
    expect(bandColor(0, 1)).toBe("hsla(22, 84%, 58%, 0.9)");
    expect(bandColor(3, 0.5)).toBe("hsla(138, 84%, 58%, 0.45)");
  });

  it("bandColor falls back to hue 196 past band 7 and clamps intensity", () => {
    expect(bandColor(99, 2)).toBe("hsla(196, 84%, 58%, 0.9)");
    expect(bandColor(0, -1)).toBe("hsla(22, 84%, 58%, 0)");
  });

  it("SOURCE_COLORS are the 5 Tailwind-400 stem rgbs in sources[] order", () => {
    expect(SOURCE_COLORS.map((c) => [...c])).toEqual([
      [250, 204, 21],
      [248, 113, 113],
      [34, 211, 238],
      [74, 222, 128],
      [192, 132, 252],
    ]);
  });

  it("sourceRgb / sourceColor fall back to the last entry past index 4", () => {
    expect([...sourceRgb(9)]).toEqual([192, 132, 252]);
    expect(sourceColor(2, 0.16 + 1 * 0.72)).toBe("rgba(34, 211, 238, 0.88)");
    expect(sourceColor(0, 0.18)).toBe("rgba(250, 204, 21, 0.18)");
  });

  it("lane heights match design notes §3a", () => {
    expect(LANE_HEIGHTS).toEqual({ fft: 84, rms: 112, env: 112, hints: 58, collapsed: 26 });
  });

  it("clamp01", () => {
    expect(clamp01(-0.2)).toBe(0);
    expect(clamp01(1.5)).toBe(1);
    expect(clamp01(0.4)).toBe(0.4);
  });
});
