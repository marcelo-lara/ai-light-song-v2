// SparseLane.tsx — the reusable block-lane body for every item-9 sparse lane
// (human hints, sections, chords, patterns, identifier hints, machine / ML
// events, BeatDrop plan, symbolic phrases).
//
// It takes an already-built `SparseBlock[]` from a laneContent adapter, draws
// Nocturne-tinted rounded blocks with a label (+ caption when wide), row-packs
// overlapping blocks for the compact lanes (sparseGeometry.packRows), and
// registers hit regions so a click opens the item-6 block inspector (or, for
// `humanHints`, the hint editor — routed by App via marker.laneId). A click
// that misses every block seeks the playhead.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef } from "react";

import type { ArtifactStatus } from "../data";

import type { Coords } from "./coords";
import type { Lane } from "./laneState";
import type { LaneMarker } from "./laneRenderers";
import type { SparseBlock } from "./laneContent";
import {
  blockBox,
  blockTextLayout,
  packRows,
  type PackedBlock,
} from "./sparseGeometry";
import { sparseTint } from "./sparseTints";

const MAX_CANVAS_PX = 32000;
const LABEL_FONT = '600 11px "Inter", system-ui, sans-serif';
const CAPTION_FONT = '11px "IBM Plex Mono", monospace';

interface SparseLaneProps {
  lane: Lane;
  laneId: string;
  coords: Coords;
  blocks: readonly SparseBlock[];
  status: ArtifactStatus;
  error: string | null;
  activeId?: string | null;
  onSeek: (time: number) => void;
  onSelectMarker: (marker: LaneMarker) => void;
}

interface HitBox {
  x1: number;
  x2: number;
  y1: number;
  y2: number;
  block: SparseBlock;
}

function trimText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string {
  if (!text || maxWidth <= 0) return "";
  if (ctx.measureText(text).width <= maxWidth) return text;
  let out = text;
  while (out.length > 1 && ctx.measureText(`${out}…`).width > maxWidth) {
    out = out.slice(0, -1);
  }
  return `${out}…`;
}

/** marker payload merged so the item-6 inspector sees both adapter + raw fields */
function markerFor(block: SparseBlock, laneId: string): LaneMarker {
  const base =
    block.raw && typeof block.raw === "object"
      ? (block.raw as Record<string, unknown>)
      : {};
  return {
    laneId,
    id: block.id,
    time: block.start_s,
    kind: laneId,
    raw: {
      ...base,
      label: block.label,
      start_s: block.start_s,
      end_s: block.end_s,
      caption: block.caption,
      summary: block.summary,
      ...(block.reference && block.reference !== "-"
        ? { reference: block.reference }
        : {}),
      ...(block.detail && block.detail !== "-" ? { detail: block.detail } : {}),
    },
  };
}

export function SparseLane({
  lane,
  laneId,
  coords,
  blocks,
  status,
  error,
  activeId,
  onSeek,
  onSelectMarker,
}: SparseLaneProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hitsRef = useRef<HitBox[]>([]);

  const cssWidth = coords.timelineW;
  const cssHeight = lane.renderHeight;
  const tint = sparseTint(laneId);

  const packed = useMemo<PackedBlock<SparseBlock & { x: number; width: number }>[]>(() => {
    const boxed = blocks.map((block) => {
      const box = blockBox(block.start_s, block.end_s, coords.timeToX);
      return { ...block, x: box.x, width: box.width };
    });
    return packRows(boxed, { laneId, laneHeight: cssHeight });
  }, [blocks, coords, laneId, cssHeight]);

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
    if (status !== "ready" || !blocks.length) return;

    ctx.textBaseline = "top";
    ctx.lineWidth = 1;

    // Collapsed: a faint tick per block along the strip.
    if (!lane.expanded) {
      ctx.fillStyle = tint.stroke;
      for (const block of blocks) {
        const x = coords.timeToX(block.start_s) * xScale;
        const w = Math.max(2, coords.timeToX(block.end_s) * xScale - x);
        ctx.fillRect(x, cssHeight - 8, w, 5);
      }
      return;
    }

    for (const p of packed) {
      const x = p.x * xScale;
      const w = Math.max(2, p.width * xScale);
      const layout = blockTextLayout(w, p.height);
      const selected = activeId != null && p.block.id === activeId;

      ctx.fillStyle = tint.fill;
      ctx.fillRect(x, p.y, w, p.height);
      ctx.strokeStyle = selected ? tint.label : tint.stroke;
      ctx.strokeRect(x, p.y, w, p.height);

      hitsRef.current.push({
        x1: p.x,
        x2: p.x + p.width,
        y1: p.y,
        y2: p.y + p.height,
        block: p.block,
      });

      if (!layout.showLabel) continue;
      const label =
        layout.showWideLabel && p.block.wideLabel ? p.block.wideLabel : p.block.label;
      ctx.font = LABEL_FONT;
      ctx.fillStyle = tint.label;
      ctx.fillText(
        trimText(ctx, label, layout.contentWidth),
        x + 10,
        p.height <= 24 ? p.y + Math.max(4, (p.height - 12) / 2) : p.y + 7,
      );
      if (layout.showCaption) {
        ctx.font = CAPTION_FONT;
        ctx.fillStyle = tint.caption;
        ctx.fillText(
          trimText(ctx, p.block.caption, layout.contentWidth),
          x + 10,
          p.y + 26,
        );
      }
    }
  }, [
    blocks,
    packed,
    coords,
    lane.expanded,
    cssWidth,
    cssHeight,
    status,
    tint,
    activeId,
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
      if (lane.expanded) {
        const hit = hitsRef.current.find(
          (h) => x >= h.x1 && x <= h.x2 && y >= h.y1 && y <= h.y2,
        );
        if (hit) {
          onSelectMarker(markerFor(hit.block, laneId));
          return;
        }
      }
      onSeek(coords.xToTime(x));
    },
    [coords, lane.expanded, laneId, onSeek, onSelectMarker],
  );

  const state = useMemo(() => {
    if (status === "loading") return "Loading…";
    if (status === "error") return `Unavailable${error ? ` — ${error}` : ""}`;
    if (status === "ready" && !blocks.length) return "No data in this artifact";
    return null;
  }, [status, error, blocks.length]);

  return (
    <div
      className="tl-canvas-lane tl-sparse-lane"
      style={{ position: "absolute", inset: 0, width: cssWidth }}
      role="presentation"
      onClick={handleClick}
    >
      <canvas ref={canvasRef} className="tl-canvas-lane__canvas" />
      {state && <div className="tl-canvas-lane__state">{state}</div>}
    </div>
  );
}
