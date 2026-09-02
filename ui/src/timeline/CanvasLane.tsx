// CanvasLane.tsx — DPR-aware <canvas> body for the continuous / density data
// lanes. A shared setup (sizing, grid-aligned clear, RenderCtx) plus a
// per-`kind` renderer from laneRenderers.ts. Redraws on pxPerSec / collapse /
// resize / scroll (sub-labels are viewport-anchored) and data change.
//
// Continuous lanes: a click anywhere seeks. Drums / energy lanes additionally
// build hit regions for their discrete markers → onSelectMarker (item 6 stub).

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef } from "react";

import type { ArtifactStatus } from "../data";
import type {
  DrumEventsFile,
  EnergyLayer,
  FftBands,
  LoudnessSeries,
} from "../data/types";

import type { Coords } from "./coords";
import type { Lane } from "./laneState";
import {
  drawCollapsedStrip,
  drawDrums,
  drawEnergy,
  drawFft,
  drawLoudness,
  type HitRegion,
  type LaneMarker,
  type RenderCtx,
} from "./laneRenderers";

const MAX_CANVAS_PX = 32000; // Chrome hard-caps canvas dimensions ~32767

export type CanvasLaneSource =
  | { kind: "fft"; data: FftBands | null }
  | { kind: "rms"; data: LoudnessSeries | null }
  | { kind: "env"; data: LoudnessSeries | null }
  | { kind: "drums"; data: DrumEventsFile | null }
  | { kind: "energy"; data: EnergyLayer | null };

interface CanvasLaneProps {
  lane: Lane;
  coords: Coords;
  source: CanvasLaneSource;
  status: ArtifactStatus;
  error: string | null;
  /** timeline scroll offset (px) — drives the viewport-anchored sub-labels */
  scrollLeft: number;
  /** visible width of the timeline scroller (px) */
  viewportWidth: number;
  onSeek: (time: number) => void;
  onSelectMarker?: (marker: LaneMarker) => void;
}

function hasData(source: CanvasLaneSource): boolean {
  switch (source.kind) {
    case "fft":
      return !!source.data?.frames.length && !!source.data.bands.length;
    case "rms":
    case "env":
      return !!source.data?.frames.length && !!source.data.sources.length;
    case "drums":
      return !!source.data?.events.length;
    case "energy":
      return (
        !!source.data?.beat_energy.length || !!source.data?.accent_candidates.length
      );
  }
}

/** ~600-point down-sample used for the collapsed 26px strip. */
function collapsedSamples(source: CanvasLaneSource): Array<{ t: number; v: number }> {
  const pick = <T,>(rows: readonly T[], project: (row: T) => { t: number; v: number }) => {
    if (!rows.length) return [];
    const step = Math.max(1, Math.floor(rows.length / 600));
    const out: Array<{ t: number; v: number }> = [];
    for (let i = 0; i < rows.length; i += step) out.push(project(rows[i]!));
    return out;
  };
  switch (source.kind) {
    case "fft":
      return pick(source.data?.frames ?? [], (f) => ({
        t: f.time,
        v: Math.max(0, ...f.levels),
      }));
    case "rms":
    case "env":
      return pick(source.data?.frames ?? [], (f) => ({
        t: f.time,
        v: f.normalized_values[0] ?? 0,
      }));
    case "energy":
      return pick(source.data?.beat_energy ?? [], (b) => ({
        t: b.time,
        v: b.energy_score,
      }));
    case "drums":
      return [];
  }
}

export function CanvasLane({
  lane,
  coords,
  source,
  status,
  error,
  scrollLeft,
  viewportWidth,
  onSeek,
  onSelectMarker,
}: CanvasLaneProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hitsRef = useRef<HitRegion[]>([]);

  const cssWidth = coords.timelineW;
  const cssHeight = lane.renderHeight;
  const ready = status === "ready" && hasData(source);
  const empty = status === "ready" && !hasData(source);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    hitsRef.current = [];

    const dpr = Math.min(
      globalThis.devicePixelRatio || 1,
      MAX_CANVAS_PX / Math.max(cssWidth, 1),
      MAX_CANVAS_PX / Math.max(cssHeight, 1),
    );
    const xScale = Math.min(1, MAX_CANVAS_PX / Math.max(cssWidth, 1));
    canvas.width = Math.max(1, Math.round(cssWidth * xScale * dpr));
    canvas.height = Math.max(1, Math.round(cssHeight * dpr));
    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${cssHeight}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssWidth * xScale, cssHeight);
    if (!ready) return;

    const pxPerSec = coords.pxPerSec;
    const scrollStart = pxPerSec > 0 ? scrollLeft / pxPerSec : 0;
    // Every renderer draws the FULL song, `0 .. duration`, so the lane always
    // spans `coords.timelineW` and matches the Bars ruler — regardless of the
    // current scroll offset or viewport width. `scrollStart` is still the real
    // scroll offset so viewport-anchored sub-labels stay pinned to the left
    // edge. When an artifact's data ends before the song does, the renderer
    // simply draws to its last frame and leaves the rest of the (full-width)
    // canvas empty: "data ran out", not "lane is short".
    const rc: RenderCtx = {
      ctx,
      width: cssWidth * xScale,
      height: cssHeight,
      pxPerSec,
      timeToX: (t) => coords.timeToX(t) * xScale,
      visibleStart: 0,
      visibleEnd: coords.duration,
      scrollStart,
    };

    if (!lane.expanded) {
      drawCollapsedStrip(rc, collapsedSamples(source));
      return;
    }

    switch (source.kind) {
      case "fft":
        if (source.data) drawFft(rc, source.data);
        break;
      case "rms":
        if (source.data) drawLoudness(rc, source.data, "rms");
        break;
      case "env":
        if (source.data) drawLoudness(rc, source.data, "env");
        break;
      case "drums":
        if (source.data) {
          hitsRef.current = drawDrums(
            rc,
            source.data.events.map((e) => ({
              id: e.id,
              time: e.time,
              end_s: e.end_s,
              event_type: e.event_type,
            })),
            lane.id,
          );
        }
        break;
      case "energy":
        if (source.data) {
          const beats = source.data.beat_energy;
          const beatRows = beats.map((b, i) => ({
            start_s: b.time,
            end_s: beats[i + 1]?.time ?? coords.duration,
            value: b.energy_score,
          }));
          hitsRef.current = drawEnergy(
            rc,
            beatRows,
            source.data.accent_candidates.map((a) => ({
              id: a.id,
              time: a.time,
              intensity: a.intensity,
              kind: a.kind,
              raw: a,
            })),
            lane.id,
          );
        }
        break;
    }
  }, [
    coords,
    source,
    lane.expanded,
    lane.id,
    cssWidth,
    cssHeight,
    scrollLeft,
    viewportWidth,
    ready,
  ]);

  useLayoutEffect(draw, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => draw());
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [draw]);

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      if (lane.expanded && hitsRef.current.length && onSelectMarker) {
        const hit = hitsRef.current.find(
          (h) => x >= h.x1 && x <= h.x2 && y >= h.y1 && y <= h.y2,
        );
        if (hit) {
          onSelectMarker(hit.marker);
          return;
        }
      }
      onSeek(coords.xToTime(x));
    },
    [coords, lane.expanded, onSeek, onSelectMarker],
  );

  const state = useMemo(() => {
    if (status === "loading") return "Loading…";
    if (status === "error") return `Unavailable${error ? ` — ${error}` : ""}`;
    if (empty) return "No data in this artifact";
    return null;
  }, [status, error, empty]);

  return (
    <div
      className="tl-canvas-lane"
      style={{ position: "absolute", inset: 0, width: cssWidth }}
      role="presentation"
      onClick={handleClick}
    >
      <canvas ref={canvasRef} className="tl-canvas-lane__canvas" />
      {state && <div className="tl-canvas-lane__state">{state}</div>}
    </div>
  );
}
