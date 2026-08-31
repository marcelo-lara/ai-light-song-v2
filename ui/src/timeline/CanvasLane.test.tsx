// CanvasLane render geometry — item 3 (continuous lanes span the full timeline).
//
// jsdom has no 2D canvas, so we stub `getContext` with a recorder that captures
// every x coordinate the lane renderers draw at. The assertions are on the
// rightmost drawn x relative to `coords.timeToX(duration)` / the last data
// frame — proving the lane's x-domain runs the whole song, not just the
// opening viewport span.

import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FftBands, LoudnessSeries } from "../data/types";

import { CanvasLane, type CanvasLaneSource } from "./CanvasLane";
import { makeCoords } from "./coords";
import type { Lane } from "./laneState";

const DURATION = 200;
const PX_PER_BAR = 40;

// A minimal, evenly-spaced beat list so `medianBarSeconds` is well defined.
const beats = Array.from({ length: 101 }, (_, i) => ({
  time: i * 2,
  beat: (i % 4) + 1,
  bar: Math.floor(i / 4) + 1,
  type: i % 4 === 0 ? "downbeat" : "beat",
}));

const coords = makeCoords({ beats, duration: DURATION, pxPerBar: PX_PER_BAR });

interface Recorder {
  xs: number[];
  max(): number;
}

function installCanvasStub(): Recorder {
  const rec: Recorder = { xs: [], max: () => (rec.xs.length ? Math.max(...rec.xs) : -1) };
  const push = (x: unknown) => {
    if (typeof x === "number" && Number.isFinite(x)) rec.xs.push(x);
  };
  const ctx = {
    canvas: null as unknown,
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    clip: vi.fn(),
    setTransform: vi.fn(),
    clearRect: vi.fn(),
    fillRect: (x: number, _y: number, w: number) => {
      push(x);
      push(x + w);
    },
    strokeRect: (x: number, _y: number, w: number) => push(x + w),
    moveTo: (x: number) => push(x),
    lineTo: (x: number) => push(x),
    arc: (x: number) => push(x),
    fillText: (_t: string, x: number) => push(x),
    measureText: (t: string) => ({ width: t.length * 6 }),
    createLinearGradient: () => ({ addColorStop: vi.fn() }),
    set fillStyle(_v: unknown) {},
    set strokeStyle(_v: unknown) {},
    set lineWidth(_v: unknown) {},
    set font(_v: unknown) {},
    set globalAlpha(_v: unknown) {},
    set textBaseline(_v: unknown) {},
    set textAlign(_v: unknown) {},
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D,
  );
  return rec;
}

function laneFor(id: string, kind: Lane["kind"]): Lane {
  return {
    id,
    label: id,
    sub: "",
    kind,
    height: 112,
    expanded: true,
    visible: true,
    renderHeight: 112,
  };
}

function fftFixture(lastFrameTime: number): FftBands {
  const bands = Array.from({ length: 7 }, (_, i) => ({
    id: `b${i}`,
    label: `b${i}`,
    start_hz: i,
    end_hz: i + 1,
  }));
  const step = 2;
  const frames = [];
  for (let t = 0; t <= lastFrameTime + 1e-9; t += step) {
    frames.push({
      frame_index: frames.length,
      time: Number(t.toFixed(3)),
      levels: bands.map(() => 0.8),
      brightness_ratio: 0.5,
      transient_strength: 0,
      dropout_strength: 0,
    });
  }
  return {
    schema_version: "1.0",
    song_name: "t",
    bands,
    frames,
    metadata: { interval_ms: 2000 },
  };
}

function loudnessFixture(lastFrameTime: number): LoudnessSeries {
  const sources = [{ id: "mix", label: "Mix", path: "", kind: "mix" as const }];
  const frames = [];
  for (let t = 0; t <= lastFrameTime + 1e-9; t += 2) {
    frames.push({
      frame_index: frames.length,
      time: Number(t.toFixed(3)),
      start_s: Number(t.toFixed(3)),
      end_s: Number((t + 2).toFixed(3)),
      values: [0.7],
      normalized_values: [0.7],
      history: null,
    });
  }
  return {
    schema_version: "1.0",
    song_name: "t",
    sources,
    frames,
    metadata: { interval_ms: 2000 },
  };
}

function renderLane(source: CanvasLaneSource, rec: Recorder, opts?: { scrollLeft?: number; viewportWidth?: number }) {
  render(
    <CanvasLane
      lane={laneFor(source.kind === "fft" ? "fftBands" : "rmsLoudness", source.kind === "fft" ? "fft" : "rms")}
      coords={coords}
      source={source}
      status="ready"
      error={null}
      scrollLeft={opts?.scrollLeft ?? 0}
      viewportWidth={opts?.viewportWidth ?? 400}
      onSeek={() => {}}
    />,
  );
  return rec;
}

let rec: Recorder;
beforeEach(() => {
  rec = installCanvasStub();
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("CanvasLane — full-timeline x-domain (item 3)", () => {
  it("a full-length fixture draws to timeToX(duration) within 1px", () => {
    renderLane({ kind: "fft", data: fftFixture(DURATION) }, rec);
    expect(rec.max()).toBeGreaterThan(0);
    expect(Math.abs(rec.max() - coords.timeToX(DURATION))).toBeLessThanOrEqual(1);
  });

  it("is independent of scroll offset and viewport width (not clipped to the viewport)", () => {
    // Tiny viewport, scrolled hard right: old code clipped drawing to
    // [scrollLeft, scrollLeft+viewport]; the fix draws the whole song regardless.
    renderLane({ kind: "rms", data: loudnessFixture(DURATION) }, rec, {
      scrollLeft: 0,
      viewportWidth: 50,
    });
    expect(Math.abs(rec.max() - coords.timeToX(DURATION))).toBeLessThanOrEqual(1);
  });

  it("a short-data fixture draws to its last frame and no further, canvas still full width", () => {
    renderLane({ kind: "fft", data: fftFixture(DURATION / 2) }, rec);
    const lastFrameX = coords.timeToX(DURATION / 2);
    expect(rec.max()).toBeGreaterThan(lastFrameX - 4);
    expect(rec.max()).toBeLessThan(coords.timeToX(DURATION / 2 + 20));

    const canvas = document.querySelector("canvas") as HTMLCanvasElement;
    // backing store spans the whole timeline, not the truncated data
    expect(canvas.width).toBeGreaterThanOrEqual(Math.floor(coords.timelineW) - 1);
    expect(canvas.style.width).toBe(`${coords.timelineW}px`);
  });
});
