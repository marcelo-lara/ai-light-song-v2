// sparseTints.ts — per-lane block tints for SparseLane (replaces ui.old's
// `sparseLaneStyles` table).
//
// The hue assignments are carried over from ui.old — hints amber, sections
// teal, chords cyan, patterns gold, identifiers blue, machine red, ml violet,
// beatdrop orange, phrases deep-violet — but instead of nine hand-written rgba
// quads the values are now derived from one documented base hue per lane
// (`BASE_HUE`) plus a fixed alpha ramp (`FILL_A` / `STROKE_A`). Canvas needs
// concrete colour strings, so these resolve to `hsl()` / `hsla()` here rather
// than Nocturne CSS custom properties; the label + caption inks are the shared
// Nocturne foreground tokens' literal values.

export interface SparseTint {
  /** rounded-rect fill */
  fill: string;
  /** rounded-rect 1px stroke */
  stroke: string;
  /** block label ink */
  label: string;
  /** block caption ink */
  caption: string;
}

/** documented base hue (deg) + saturation (%) per lane id */
const BASE: Record<string, [hue: number, sat: number, light: number]> = {
  humanHints: [35, 92, 48], // amber   (ui.old rgba(217,119,6))
  sections: [174, 78, 38], // teal    (ui.old rgba(15,118,110))
  chords: [193, 82, 44], // cyan    (ui.old rgba(14,116,144))
  patterns: [43, 96, 40], // gold    (ui.old rgba(202,138,4))
  identifierHints: [201, 96, 33], // blue    (ui.old rgba(3,105,161))
  machineEvents: [0, 74, 42], // red     (ui.old rgba(185,28,28))
  mlEvents: [263, 70, 42], // violet  (ui.old rgba(91,33,182))
  beatdropPlan: [25, 95, 49], // orange  (ui.old rgba(234,88,12))
  phrases: [265, 68, 43], // deep violet (ui.old rgba(76,29,149))
};

/** fixed alpha ramp shared by every lane */
const FILL_A = 0.16;
const STROKE_A = 0.3;

/** shared Nocturne foreground inks (literal values of the CSS tokens) */
const LABEL_INK = "rgba(233, 233, 237, 0.96)";
const CAPTION_INK = "rgba(201, 200, 208, 0.82)";

function tintFor(id: string): SparseTint {
  const [h, s, l] = BASE[id] ?? BASE.sections!;
  return {
    fill: `hsla(${h}, ${s}%, ${l}%, ${FILL_A})`,
    stroke: `hsla(${h}, ${s}%, ${l}%, ${STROKE_A})`,
    label: LABEL_INK,
    caption: CAPTION_INK,
  };
}

export const SPARSE_TINTS: Record<string, SparseTint> = Object.fromEntries(
  Object.keys(BASE).map((id) => [id, tintFor(id)]),
);

export function sparseTint(laneId: string): SparseTint {
  return SPARSE_TINTS[laneId] ?? tintFor("sections");
}

/** discrete-mark colours for the validation (regression overlay) lane */
export const VALIDATION_MARK_COLORS: Record<string, string> = {
  exact: "hsla(174, 78%, 38%, 0.72)",
  shifted: "hsla(43, 96%, 40%, 0.78)",
  not_exported: "hsla(0, 74%, 42%, 0.78)",
  output_only: "hsla(201, 96%, 40%, 0.72)",
};
