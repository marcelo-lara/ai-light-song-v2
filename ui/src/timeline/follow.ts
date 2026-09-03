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

// ---- Follow-playhead toggle (plan v1.5 item 6 / R6) -----------------------
//
// The footer toggle's flag persists per session, default on (D7): turning
// following *off* is what R6 asks for, so a first-time load keeps today's
// behaviour. Storage shape copied from `app/panelState.ts` — a versioned key,
// try/catch around both accessors, the default on anything unreadable.

/** First-load / unreadable-storage default: follow the playhead (plan v1.5 D7). */
export const DEFAULT_FOLLOW_PLAYHEAD = true;

const STORAGE_KEY = "als.ui.followPlayhead.v1";

/** Read the persisted follow flag; absent or unreadable → the default. */
export function loadFollowPlayhead(): boolean {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    if (raw == null) return DEFAULT_FOLLOW_PLAYHEAD;
    return raw === "true";
  } catch {
    return DEFAULT_FOLLOW_PLAYHEAD;
  }
}

/** Persist the follow flag. Best-effort — persistence is a convenience. */
export function saveFollowPlayhead(on: boolean): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, String(on));
  } catch {
    // ignore — private window / blocked storage
  }
}

/**
 * D6: did the user scroll, or did the follow effect? The follow effect writes
 * `el.scrollLeft` itself, so the scroll listener cannot tell whose scroll it is
 * observing without help. `lastProgrammatic` is the offset the effect last
 * wrote (null when it has written none — so the observed scroll must be the
 * user's). Any observed offset further than `tolerancePx` from the last
 * programmatic write is the user's; this covers wheel, trackpad, scrollbar drag
 * and keyboard alike. Pure — unit-testable without a browser.
 */
export function isUserScroll(
  observed: number,
  lastProgrammatic: number | null,
  tolerancePx = 1,
): boolean {
  if (lastProgrammatic == null) return true;
  return Math.abs(observed - lastProgrammatic) > tolerancePx;
}
