// sparseGeometry.ts — pure, testable block geometry for SparseLane.
//
// Ported from the previous app's src/lib/timeline/sparseLane.js `buildSparseRegions`:
//   * lanes in COMPACT_LANE_IDS row-pack overlapping blocks into as many rows as
//     the worst overlap needs, then split the lane body height across the rows;
//   * every other lane draws every block as one full-height band.
//
// The label/caption visibility thresholds match the old canvas painter.

export const COMPACT_LANE_IDS: ReadonlySet<string> = new Set([
  "identifierHints",
  "machineEvents",
  "mlEvents",
  "phrases",
]);

/** vertical inset of the block band inside the lane body */
export const BLOCK_PADDING = 6;
/** gap between packed rows when a lane has 2+ rows */
export const ROW_GAP = 4;
/** minimum packed-row height */
export const MIN_ROW_HEIGHT = 14;
/** a block narrower than this draws no text at all */
export const MIN_LABEL_WIDTH = 36;
/** a block at least this wide (and tall enough) also draws its caption */
export const MIN_CAPTION_WIDTH = 96;
export const MIN_CAPTION_HEIGHT = 30;
/** roman numeral / wide-only label appears from here up */
export const WIDE_LABEL_WIDTH = 120;

export interface GeomInput {
  /** left edge in body px */
  x: number;
  /** width in px (already floored to a sane minimum by the caller) */
  width: number;
}

export interface PackedBlock<T extends GeomInput = GeomInput> {
  block: T;
  x: number;
  width: number;
  y: number;
  height: number;
  rowIndex: number;
}

export interface PackOptions {
  laneId: string;
  /** expanded lane body height in px */
  laneHeight: number;
}

/**
 * Assign each block a row + vertical box. Non-compact lanes get one row of the
 * full band height; compact lanes greedily pack blocks left-to-right into the
 * lowest row whose last block already ended.
 */
export function packRows<T extends GeomInput>(
  blocks: readonly T[],
  { laneId, laneHeight }: PackOptions,
): PackedBlock<T>[] {
  const top = BLOCK_PADDING;
  const band = Math.max(1, laneHeight - BLOCK_PADDING * 2);

  if (!COMPACT_LANE_IDS.has(laneId) || blocks.length <= 1) {
    return blocks.map((block) => ({
      block,
      x: block.x,
      width: block.width,
      y: top,
      height: band,
      rowIndex: 0,
    }));
  }

  const sorted = [...blocks].sort((a, b) =>
    a.x !== b.x ? a.x - b.x : a.width - b.width,
  );
  const rowEnds: number[] = [];
  const rows: number[] = [];
  let maxRows = 1;
  sorted.forEach((block) => {
    let rowIndex = rowEnds.findIndex((endX) => block.x >= endX);
    if (rowIndex === -1) rowIndex = rowEnds.length;
    rowEnds[rowIndex] = block.x + block.width;
    rows.push(rowIndex);
    maxRows = Math.max(maxRows, rowIndex + 1);
  });

  const rowGap = maxRows > 1 ? ROW_GAP : 0;
  const rowHeight = Math.max(
    MIN_ROW_HEIGHT,
    (band - rowGap * (maxRows - 1)) / maxRows,
  );

  return sorted.map((block, i) => {
    const rowIndex = rows[i]!;
    return {
      block,
      x: block.x,
      width: block.width,
      y: top + rowIndex * (rowHeight + rowGap),
      height: rowHeight,
      rowIndex,
    };
  });
}

export interface BlockTextLayout {
  showLabel: boolean;
  showCaption: boolean;
  showWideLabel: boolean;
  /** px available for text inside the block */
  contentWidth: number;
  /** corner radius for the rounded rect */
  radius: number;
}

export function blockTextLayout(width: number, height: number): BlockTextLayout {
  return {
    showLabel: width >= MIN_LABEL_WIDTH,
    showCaption: width >= MIN_CAPTION_WIDTH && height > MIN_CAPTION_HEIGHT,
    showWideLabel: width >= WIDE_LABEL_WIDTH,
    contentWidth: Math.max(width - 20, 0),
    radius: height <= 22 ? 8 : 12,
  };
}

/** px x/width for a block given a time→x mapping; width floored to 2px. */
export function blockBox(
  start_s: number,
  end_s: number,
  timeToX: (t: number) => number,
): GeomInput {
  const x = timeToX(start_s);
  return { x, width: Math.max(2, timeToX(end_s) - x) };
}
