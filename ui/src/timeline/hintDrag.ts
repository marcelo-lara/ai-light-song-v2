// hintDrag.ts — pure geometry + reducer for dragging a human-hint block on the
// timeline (plan v2.1 item 10 / refinement R7).
//
// No React, no DOM. `SparseLane` owns the pointer plumbing and canvas redraw;
// everything that decides *what the new start/end times are* lives here so it is
// unit-testable in isolation.
//
//   - resolveZone      : which part of a block an x landed in (left/right/interior)
//   - pxToSeconds      : a screen-px delta -> a time delta via pxPerSec
//   - applyDrag        : move start / end / both by a time delta, per zone
//   - nearestSnapPx    : nearest snap target within a px threshold (or null)
//   - snapEdge         : nearestSnapPx, falling back to the original value
//   - clampTimes       : start >= 0, end <= duration, min-gap, box-preserving
//   - isClick          : travel-below-threshold => treat pointerup as a click
//   - computeDrag      : the orchestrator SparseLane calls each pointermove

export type DragZone = "left" | "right" | "interior";

/** px width of the left / right edge grab zones. */
export const EDGE_ZONE_PX = 6;
/** blocks narrower than this are interior-only (move, no edge resize). */
export const MIN_BLOCK_PX = 18;
/** an edge within this many screen px of another block's edge snaps to it. */
export const SNAP_PX = 5;
/** pointer travel (px) below this on pointerup is a click, not a drag. */
export const CLICK_PX = 4;
/** the smallest allowed `end - start` (seconds). */
export const MIN_GAP_S = 0.05;

export interface TimeSpan {
  start: number;
  end: number;
}

/** Which grab zone an x (relative to the block's left edge) falls in. */
export function resolveZone(xInBlock: number, blockWidthPx: number): DragZone {
  if (!(blockWidthPx >= MIN_BLOCK_PX)) return "interior";
  if (xInBlock <= EDGE_ZONE_PX) return "left";
  if (xInBlock >= blockWidthPx - EDGE_ZONE_PX) return "right";
  return "interior";
}

/** A screen-px delta -> a seconds delta. Returns 0 when pxPerSec is unusable. */
export function pxToSeconds(dxPx: number, pxPerSec: number): number {
  return pxPerSec > 0 ? dxPx / pxPerSec : 0;
}

/** Move start / end / both by `dtSeconds`, before snap + clamp. */
export function applyDrag(
  zone: DragZone,
  original: TimeSpan,
  dtSeconds: number,
): TimeSpan {
  switch (zone) {
    case "left":
      return { start: original.start + dtSeconds, end: original.end };
    case "right":
      return { start: original.start, end: original.end + dtSeconds };
    case "interior":
      return {
        start: original.start + dtSeconds,
        end: original.end + dtSeconds,
      };
  }
}

/**
 * Nearest member of `targetsPx` within `thresholdPx` of `valuePx`, or `null`.
 * Ties resolve to the first candidate encountered.
 */
export function nearestSnapPx(
  valuePx: number,
  targetsPx: readonly number[],
  thresholdPx: number = SNAP_PX,
): number | null {
  let best: number | null = null;
  let bestDist = Infinity;
  for (const t of targetsPx) {
    const d = Math.abs(t - valuePx);
    if (d <= thresholdPx && d < bestDist) {
      bestDist = d;
      best = t;
    }
  }
  return best;
}

/** Snap `valuePx` to the nearest target within threshold, else return it as-is. */
export function snapEdge(
  valuePx: number,
  targetsPx: readonly number[],
  thresholdPx: number = SNAP_PX,
): number {
  return nearestSnapPx(valuePx, targetsPx, thresholdPx) ?? valuePx;
}

/**
 * Constrain a dragged span:
 *  - edge drag: `start >= 0`, `end <= duration`, `end - start >= MIN_GAP_S`
 *    (an edge that would violate the gap stops at the limit);
 *  - interior drag: the box keeps its length; hitting 0 or `duration` stops the
 *    whole box at that boundary.
 */
export function clampTimes(
  zone: DragZone,
  times: TimeSpan,
  duration: number,
  minGap: number = MIN_GAP_S,
): TimeSpan {
  const dur = duration > 0 ? duration : 0;

  if (zone === "interior") {
    const len = Math.max(0, times.end - times.start);
    let start = times.start;
    if (start < 0) start = 0;
    let end = start + len;
    if (end > dur) {
      end = dur;
      start = Math.max(0, end - len);
    }
    return { start, end };
  }

  let start = times.start;
  let end = times.end;
  if (zone === "left") {
    start = Math.max(0, Math.min(start, end - minGap));
  } else {
    end = Math.min(dur, Math.max(end, start + minGap));
  }
  // final safety net for the fixed edge
  if (start < 0) start = 0;
  if (end > dur) end = dur;
  return { start, end };
}

/** Pointer travel below the click threshold => the pointerup is a click. */
export function isClick(totalTravelPx: number): boolean {
  return totalTravelPx < CLICK_PX;
}

export interface ComputeDragInput {
  zone: DragZone;
  original: TimeSpan;
  /** raw pointer delta from pointerdown, in screen px. */
  dxPx: number;
  pxPerSec: number;
  duration: number;
  /** every OTHER block's start_s / end_s, already converted to px. */
  snapTargetsPx?: readonly number[];
  snapThresholdPx?: number;
}

/**
 * Full pointermove -> new {start,end}: apply the raw delta, snap (edge: the
 * moving edge; interior: whichever of the two moving edges is closest to a
 * target), then clamp.
 */
export function computeDrag(input: ComputeDragInput): TimeSpan {
  const {
    zone,
    original,
    dxPx,
    pxPerSec,
    duration,
    snapTargetsPx,
    snapThresholdPx = SNAP_PX,
  } = input;

  let moved = applyDrag(zone, original, pxToSeconds(dxPx, pxPerSec));

  if (snapTargetsPx && snapTargetsPx.length > 0 && pxPerSec > 0) {
    if (zone === "interior") {
      const startPx = moved.start * pxPerSec;
      const endPx = moved.end * pxPerSec;
      const snapStart = nearestSnapPx(startPx, snapTargetsPx, snapThresholdPx);
      const snapEnd = nearestSnapPx(endPx, snapTargetsPx, snapThresholdPx);
      const dStartPx = snapStart == null ? null : snapStart - startPx;
      const dEndPx = snapEnd == null ? null : snapEnd - endPx;
      let adjPx = 0;
      if (
        dStartPx != null &&
        (dEndPx == null || Math.abs(dStartPx) <= Math.abs(dEndPx))
      ) {
        adjPx = dStartPx;
      } else if (dEndPx != null) {
        adjPx = dEndPx;
      }
      const adj = adjPx / pxPerSec;
      moved = { start: moved.start + adj, end: moved.end + adj };
    } else {
      const key = zone === "left" ? "start" : "end";
      const snapped = nearestSnapPx(
        moved[key] * pxPerSec,
        snapTargetsPx,
        snapThresholdPx,
      );
      if (snapped != null) moved = { ...moved, [key]: snapped / pxPerSec };
    }
  }

  return clampTimes(zone, moved, duration);
}
