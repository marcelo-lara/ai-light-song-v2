// laneEvents.ts — the pure selector behind the lane-events panel's active-card
// highlight (plan v1.5 item 4 / R1 "highlight the active card").

import type { SparseBlock } from "../timeline/laneContent";

/**
 * Index of the card to highlight at `time`, or -1 when none covers it.
 * Half-open [start_s, end_s): a boundary instant belongs to the block
 * that is starting. Overlapping blocks resolve to the one with the
 * latest start_s (the innermost). A degenerate block (end_s <= start_s)
 * is never active (plan v1.5 D5).
 */
export function activeBlockIndex(
  blocks: readonly SparseBlock[],
  time: number,
): number {
  let best = -1;
  let bestStart = -Infinity;
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    if (!block) continue;
    if (block.end_s <= block.start_s) continue; // degenerate — never active (D5)
    if (time < block.start_s || time >= block.end_s) continue;
    if (block.start_s >= bestStart) {
      best = i;
      bestStart = block.start_s;
    }
  }
  return best;
}

/**
 * Whether `time` falls inside this block's window — half-open [start_s, end_s),
 * same convention as `activeBlockIndex`, and the same D5 rule that a
 * degenerate block (end_s <= start_s) is never active. Unlike
 * `activeBlockIndex`, this is evaluated per block rather than resolved to one
 * "innermost" winner: overlapping blocks can all report `true` at once, which
 * is what the card's left-border playhead marker is for.
 */
export function isInPlayheadWindow(block: SparseBlock, time: number): boolean {
  if (block.end_s <= block.start_s) return false;
  return time >= block.start_s && time < block.end_s;
}
