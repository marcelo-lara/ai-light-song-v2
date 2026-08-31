// follow.ts — follow-playhead scroll maths (design notes §2).
//
// While playing: if the playhead x runs past `scrollLeft + viewportWidth - 120`,
// scroll so it sits at 55% of the viewport; if it slips behind the sticky label
// column, scroll back so it clears the column with a small margin. Pure so it
// can be unit-tested; the caller applies the result to `scroller.scrollLeft`.

export const LABEL_WIDTH = 212;
const LEAD_MARGIN = 120;
const CENTER_FRACTION = 0.55;
const BEHIND_MARGIN = 40;

export interface FollowInput {
  /** playhead x in scroll-content coordinates: timeToX(t) + LABEL_WIDTH */
  playheadX: number;
  scrollLeft: number;
  /** scroller.clientWidth */
  viewportWidth: number;
  /** scrollWidth - clientWidth */
  maxScrollLeft: number;
  playing: boolean;
}

/**
 * The scrollLeft the timeline should have. Returns the current `scrollLeft`
 * unchanged when no scroll is needed (or when not playing), so the caller can
 * cheaply skip a no-op assignment.
 */
export function followScrollLeft(input: FollowInput): number {
  const { playheadX, scrollLeft, viewportWidth, maxScrollLeft, playing } = input;
  if (!playing) return scrollLeft;

  let next = scrollLeft;
  if (playheadX > scrollLeft + viewportWidth - LEAD_MARGIN) {
    next = playheadX - viewportWidth * CENTER_FRACTION;
  } else if (playheadX < scrollLeft + LABEL_WIDTH) {
    next = playheadX - LABEL_WIDTH - BEHIND_MARGIN;
  }

  const clamped = Math.max(0, Math.min(next, Math.max(maxScrollLeft, 0)));
  return clamped;
}
