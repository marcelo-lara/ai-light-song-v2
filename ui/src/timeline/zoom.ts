// zoom.ts — the zoom control maths.
//
// `pxPerBar` (14-180) stays the user-facing zoom value and the footer label,
// exactly as the canvas mock. Internally it is converted to `pxPerSec` through
// `medianBarSeconds` (see coords.ts) so the time-proportional timeline stays
// tempo-accurate. `fitToWidth` back-solves a `pxPerBar` for the label from a
// target `pxPerSec`.

export const PX_PER_BAR_MIN = 14;
export const PX_PER_BAR_MAX = 180;
export const ZOOM_FACTOR = 1.3;

/** px reserved left of the body: 212 label column + 12 slack (canvas value). */
export const FIT_INSET = 212 + 12;

export const clampPxPerBar = (value: number): number =>
  Math.min(PX_PER_BAR_MAX, Math.max(PX_PER_BAR_MIN, Math.round(value)));

export const zoomInPxPerBar = (value: number): number =>
  clampPxPerBar(value * ZOOM_FACTOR);
export const zoomOutPxPerBar = (value: number): number =>
  clampPxPerBar(value / ZOOM_FACTOR);

export const pxPerSecFromPxPerBar = (
  pxPerBar: number,
  medianBarSeconds: number,
): number => (medianBarSeconds > 0 ? pxPerBar / medianBarSeconds : pxPerBar);

export const pxPerBarFromPxPerSec = (
  pxPerSec: number,
  medianBarSeconds: number,
): number => pxPerSec * medianBarSeconds;

/** target pxPerSec that fits the whole song in the viewport body */
export function fitToWidthPxPerSec(
  viewportWidth: number,
  durationSeconds: number,
): number {
  const usable = Math.max(viewportWidth - FIT_INSET, 1);
  return usable / Math.max(durationSeconds, 0.001);
}

/** fit-to-width expressed back as a clamped pxPerBar for the label + slider */
export function fitToWidthPxPerBar(
  viewportWidth: number,
  durationSeconds: number,
  medianBarSeconds: number,
): number {
  return clampPxPerBar(
    pxPerBarFromPxPerSec(
      fitToWidthPxPerSec(viewportWidth, durationSeconds),
      medianBarSeconds,
    ),
  );
}

export const ppbLabel = (pxPerBar: number): string =>
  `${Math.round(pxPerBar)} px/bar`;

// --- semantic zoom (design notes §2, keyed on pxPerBar) --------------------

export interface SemanticZoom {
  /** draw a bar-number label every N bars */
  barLabelEvery: number;
  /** show beat sub-ticks between bar ticks */
  beatSubTicks: boolean;
}

/** minimum block width (px) before a segment shows its "N bars" suffix and a
 *  chord shows its roman numeral (canvas `buildSegments` / `renderVals`). */
export const SEGMENT_LABEL_MIN_WIDTH = 92;

export function semanticZoom(pxPerBar: number): SemanticZoom {
  const barLabelEvery =
    pxPerBar >= 56 ? 1 : pxPerBar >= 26 ? 2 : pxPerBar >= 16 ? 4 : 8;
  return { barLabelEvery, beatSubTicks: pxPerBar >= 44 };
}
