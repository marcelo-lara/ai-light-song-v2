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

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { ArtifactStatus } from "../data";

import type { Coords } from "./coords";
import type { Lane } from "./laneState";
import type { LaneMarker } from "./laneRenderers";
import type { SparseBlock } from "./laneContent";
import {
  BEAT_SNAP_PX,
  computeDrag,
  isClick,
  resolveZone,
  type DragZone,
} from "./hintDrag";
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
  /**
   * humanHints lane only (plan v2.1 item 10): persist a block's new
   * start/end after a drag. When present AND the lane is the expanded
   * `humanHints` lane, block edges / interiors become drag handles. A
   * rejected promise reverts the on-canvas preview to the pre-drag position.
   */
  onCommitHintTimes?:
    | ((id: string, start: number, end: number) => void | Promise<void>)
    | undefined;
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
  onCommitHintTimes,
}: SparseLaneProps): React.JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hitsRef = useRef<HitBox[]>([]);

  const cssWidth = coords.timelineW;
  const cssHeight = lane.renderHeight;
  const tint = sparseTint(laneId);

  // --- item 10: drag-to-edit on the expanded humanHints lane --------------
  const dragEnabled =
    laneId === "humanHints" && lane.expanded && typeof onCommitHintTimes === "function";

  // live start/end for the block currently being (or just) dragged; overrides
  // the drawn geometry so the block follows the pointer. Cleared whenever the
  // `blocks` prop changes (a successful save reloads them at the new times).
  const [preview, setPreview] = useState<{ id: string; start: number; end: number } | null>(
    null,
  );
  const [hitsReady, setHitsReady] = useState(false);

  const dragRef = useRef<
    | null
    | {
        id: string;
        zone: DragZone;
        pointerId: number;
        startClientX: number;
        startClientY: number;
        origStart: number;
        origEnd: number;
        block: SparseBlock;
        travel: number;
        moved: boolean;
      }
  >(null);
  const suppressClickRef = useRef(false);

  // Clear the optimistic preview only when the blocks' actual times change
  // (a successful save reloads them) — not on every unrelated parent re-render,
  // which would hand back a fresh `blocks` array reference.
  const blocksSig = useMemo(
    () => blocks.map((b) => `${b.id}:${b.start_s}:${b.end_s}`).join("|"),
    [blocks],
  );
  useEffect(() => {
    setPreview(null);
  }, [blocksSig]);

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
      // item 10: the dragged block follows the pointer via `preview`.
      const dragging = preview != null && preview.id === p.block.id;
      const baseX = dragging ? coords.timeToX(preview.start) : p.x;
      const baseW = dragging
        ? Math.max(0, coords.timeToX(preview.end) - coords.timeToX(preview.start))
        : p.width;
      const x = baseX * xScale;
      const w = Math.max(2, baseW * xScale);
      const layout = blockTextLayout(w, p.height);
      const selected = activeId != null && p.block.id === activeId;

      ctx.fillStyle = tint.fill;
      ctx.fillRect(x, p.y, w, p.height);
      ctx.strokeStyle = selected ? tint.label : tint.stroke;
      ctx.strokeRect(x, p.y, w, p.height);

      hitsRef.current.push({
        x1: baseX,
        x2: baseX + baseW,
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

    setHitsReady(hitsRef.current.length > 0);
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
    preview,
  ]);

  useLayoutEffect(draw, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => draw());
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [draw]);

  const localPoint = useCallback(
    (clientX: number, clientY: number): { x: number; y: number } => {
      const rect = containerRef.current?.getBoundingClientRect();
      return {
        x: clientX - (rect?.left ?? 0),
        y: clientY - (rect?.top ?? 0),
      };
    },
    [],
  );

  // Drag/hover hit-test with a few px of slack around each block so a grab that
  // lands right on (or a hair past) an edge still resolves to that block — the
  // way a resize handle normally extends slightly outside its element. The
  // click-to-open path keeps its own exact-bounds test.
  const findHit = useCallback((x: number, y: number): HitBox | undefined => {
    const m = 4;
    return hitsRef.current.find(
      (h) => x >= h.x1 - m && x <= h.x2 + m && y >= h.y1 - m && y <= h.y2 + m,
    );
  }, []);

  // item 9: snap targets for a hint drag — the union of every OTHER block's
  // edges and every beat-line x at the current zoom. `computeDrag` picks the
  // nearest within BEAT_SNAP_PX (so the block edges effectively also beat-snap,
  // matching the tighter threshold).
  const snapTargets = useCallback(
    (draggedId: string): number[] => {
      const out: number[] = [];
      for (const b of blocks) {
        if (b.id === draggedId) continue;
        out.push(coords.timeToX(b.start_s), coords.timeToX(b.end_s));
      }
      for (const beat of coords.beats) out.push(coords.timeToX(beat.time));
      return out;
    },
    [blocks, coords],
  );

  const handlePointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!dragEnabled || event.button !== 0) return;
      const { x, y } = localPoint(event.clientX, event.clientY);
      const hit = findHit(x, y);
      if (!hit) return; // a miss still seeks via the click handler
      const zone = resolveZone(x - hit.x1, hit.x2 - hit.x1);
      dragRef.current = {
        id: hit.block.id,
        zone,
        pointerId: event.pointerId,
        startClientX: event.clientX,
        startClientY: event.clientY,
        origStart: hit.block.start_s,
        origEnd: hit.block.end_s,
        block: hit.block,
        travel: 0,
        moved: false,
      };
      event.currentTarget.setPointerCapture(event.pointerId);
      setPreview({ id: hit.block.id, start: hit.block.start_s, end: hit.block.end_s });
    },
    [dragEnabled, localPoint, findHit],
  );

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag) {
        // hover cursor feedback only
        if (!dragEnabled) return;
        const el = containerRef.current;
        if (!el) return;
        const { x, y } = localPoint(event.clientX, event.clientY);
        const hit = findHit(x, y);
        if (!hit) {
          el.style.cursor = "";
          return;
        }
        const zone = resolveZone(x - hit.x1, hit.x2 - hit.x1);
        el.style.cursor = zone === "interior" ? "grab" : "ew-resize";
        return;
      }

      const dx = event.clientX - drag.startClientX;
      const dy = event.clientY - drag.startClientY;
      drag.travel = Math.max(drag.travel, Math.hypot(dx, dy));
      if (!isClick(drag.travel)) drag.moved = true;
      if (!drag.moved) return;

      if (containerRef.current) containerRef.current.style.cursor = "grabbing";

      // item 9: ⌘/Ctrl held during the drag disables snapping entirely.
      const snap = !(event.metaKey || event.ctrlKey);
      const next = computeDrag({
        zone: drag.zone,
        original: { start: drag.origStart, end: drag.origEnd },
        dxPx: dx,
        pxPerSec: coords.pxPerSec,
        duration: coords.duration,
        snapTargetsPx: snap ? snapTargets(drag.id) : [],
        snapThresholdPx: BEAT_SNAP_PX,
        snapAnchor: drag.zone === "interior" ? "start" : "nearest",
      });
      setPreview({ id: drag.id, start: next.start, end: next.end });
    },
    [dragEnabled, localPoint, findHit, snapTargets, coords.pxPerSec, coords.duration],
  );

  const endDrag = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag) return;
      dragRef.current = null;
      if (containerRef.current) containerRef.current.style.cursor = "";
      try {
        event.currentTarget.releasePointerCapture(drag.pointerId);
      } catch {
        /* pointer already released */
      }
      suppressClickRef.current = true;

      if (!drag.moved) {
        setPreview(null);
        onSelectMarker(markerFor(drag.block, laneId));
        return;
      }

      const dx = event.clientX - drag.startClientX;
      // item 9: mirror handlePointerMove — beat-snap unless ⌘/Ctrl is held on
      // the pointerup event.
      const snap = !(event.metaKey || event.ctrlKey);
      const next = computeDrag({
        zone: drag.zone,
        original: { start: drag.origStart, end: drag.origEnd },
        dxPx: dx,
        pxPerSec: coords.pxPerSec,
        duration: coords.duration,
        snapTargetsPx: snap ? snapTargets(drag.id) : [],
        snapThresholdPx: BEAT_SNAP_PX,
        snapAnchor: drag.zone === "interior" ? "start" : "nearest",
      });
      setPreview({ id: drag.id, start: next.start, end: next.end });

      const preDrag = { start: drag.origStart, end: drag.origEnd };
      Promise.resolve(onCommitHintTimes?.(drag.id, next.start, next.end)).catch(
        () => {
          setPreview({ id: drag.id, start: preDrag.start, end: preDrag.end });
        },
      );
    },
    [snapTargets, coords, laneId, onCommitHintTimes, onSelectMarker],
  );

  const handlePointerCancel = useCallback(() => {
    if (!dragRef.current) return;
    dragRef.current = null;
    if (containerRef.current) containerRef.current.style.cursor = "";
    setPreview(null);
  }, []);

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (suppressClickRef.current) {
        suppressClickRef.current = false;
        return;
      }
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
      ref={containerRef}
      className="tl-canvas-lane tl-sparse-lane"
      style={{ position: "absolute", inset: 0, width: cssWidth }}
      role="presentation"
      data-lane={dragEnabled ? laneId : undefined}
      data-hint-drag-ready={dragEnabled && hitsReady ? "1" : undefined}
      onClick={handleClick}
      onPointerDown={dragEnabled ? handlePointerDown : undefined}
      onPointerMove={dragEnabled ? handlePointerMove : undefined}
      onPointerUp={dragEnabled ? endDrag : undefined}
      onPointerCancel={dragEnabled ? handlePointerCancel : undefined}
      onPointerLeave={
        dragEnabled
          ? () => {
              if (!dragRef.current && containerRef.current)
                containerRef.current.style.cursor = "";
            }
          : undefined
      }
    >
      <canvas ref={canvasRef} className="tl-canvas-lane__canvas" />
      {state && <div className="tl-canvas-lane__state">{state}</div>}
    </div>
  );
}
