// Waveform lane wiring — item 2 (waveform renders on a real song).
//
// The bug: wavesurfer 7.8+ derives the drawn waveform width from
// `minPxPerSec * duration`, not the `width` option, so the lane rendered a
// zero-width (blank) waveform. These tests pin the create options: a positive
// per-second scale AND a resolved, non-transparent wave colour.

import { render } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const createSpy = vi.fn();

vi.mock("wavesurfer.js", () => {
  class FakeWaveSurfer {
    static create(options: Record<string, unknown>) {
      createSpy(options);
      return new FakeWaveSurfer();
    }
    on() {}
    once() {}
    un() {}
    setOptions() {}
    getDuration() {
      return 0;
    }
    setTime() {}
    play() {}
    pause() {}
    playPause() {}
    destroy() {}
  }
  return { default: FakeWaveSurfer };
});

import { makeCoords } from "./coords";
import { useTransport, WAVE_COLOR } from "./useTransport";
import { WaveformLane } from "./WaveformLane";

const beats = Array.from({ length: 40 }, (_, i) => ({
  time: i * 2,
  beat: (i % 4) + 1,
  bar: Math.floor(i / 4) + 1,
}));
const coords = makeCoords({ beats, duration: 180, pxPerBar: 48 });

const TRANSPARENT = new Set(["", "transparent", "none", "rgba(0,0,0,0)", "#0000", "#00000000"]);

afterEach(() => {
  vi.clearAllMocks();
});

describe("useTransport — wavesurfer create options (item 2)", () => {
  it("passes a positive per-second scale and container width", () => {
    renderHook(() => useTransport({ audioUrl: "/data/songs/x.mp3", coords }));

    expect(createSpy).toHaveBeenCalledTimes(1);
    const opts = createSpy.mock.calls[0]![0] as Record<string, number>;
    expect(opts.minPxPerSec).toBeGreaterThan(0);
    expect(opts.width).toBeGreaterThan(0);
    // the per-second scale is the timeline's own, so the waveform spans timelineW
    expect(opts.minPxPerSec).toBeCloseTo(coords.pxPerSec, 5);
  });

  it("resolves a non-transparent wave colour", () => {
    renderHook(() => useTransport({ audioUrl: "/data/songs/x.mp3", coords }));
    const opts = createSpy.mock.calls[0]![0] as Record<string, string>;
    expect(opts.waveColor).toBe(WAVE_COLOR);
    expect(/^#([0-9a-f]{6}|[0-9a-f]{3})$/i.test(WAVE_COLOR)).toBe(true);
    expect(TRANSPARENT.has(WAVE_COLOR.toLowerCase())).toBe(false);
  });

  it("does not create an instance when there is no audio url", () => {
    renderHook(() => useTransport({ audioUrl: null, coords }));
    expect(createSpy).not.toHaveBeenCalled();
  });
});

describe("WaveformLane — render surface (item 2)", () => {
  it("gives the wavesurfer mount a positive width", () => {
    const surface = document.createElement("div");
    const { container } = render(
      <WaveformLane surface={surface} ready error={null} width={coords.timelineW} />,
    );
    const el = container.querySelector(".tl-waveform") as HTMLElement;
    expect(el).toBeTruthy();
    expect(el.style.width).toBe(`${coords.timelineW}px`);
    expect(coords.timelineW).toBeGreaterThan(0);
    expect(el.querySelector(".tl-waveform__mount")).toBeTruthy();
  });
});
