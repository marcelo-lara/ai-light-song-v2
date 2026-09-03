// transportRules.ts — pure transport interaction rules (plan v1.5 item 1).
//
// Kept as a pure module so the rule is unit-testable without React / DOM
// (`src/app/transportRules.test.ts`). The visual suite cannot press Play, so
// this function is where R3's playing-half behaviour is actually verified.

/**
 * R3: a click on a card (lane block, segment block, right-panel event card)
 * must not reposition the playhead while the transport is playing.
 * Returns the time to seek to, or null for "do not seek".
 *
 * `playing === true` → `null`. `playing === false` → `time` (a falsy `time`
 * such as `0` is still a valid seek target).
 */
export function seekTimeForCardClick(playing: boolean, time: number): number | null {
  return playing ? null : time;
}
