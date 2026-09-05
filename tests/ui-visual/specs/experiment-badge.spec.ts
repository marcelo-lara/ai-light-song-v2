import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

// Plan v1.5 item 7 (R7): lanes fed by an unpromoted `experiments/` sandbox
// (their proposal file lives under `reference/proposals/`) carry a quiet
// `ph-flask` badge as the first child of `.tl-lane-head__name`, left of the
// label text. Production `src/` lanes are never badged, even the ones
// CLAUDE.md records as untrusted.
//
// The badged set currently has eight lanes. Plan v3.0 item 9 promoted
// `gestures` out of this set: it used to be an `experiments/gestures`
// sandbox lane and now reads the production `song_event_timeline.json`
// deliverable. This list must track `ui/src/timeline/laneState.ts`'s tagged
// set exactly. Plan v3.0 item 14 will shrink it further when the two allin1
// lanes (`allin1Transitions`, `allin1Sections`) are promoted out of
// experiment status — update this list again when that happens.

const BADGED = [
  "dropProposals",
  "vocalPhrases",
  "reactiveBands",
  "gridPhrase",
  "allin1Transitions",
  "character",
  "vocalTranscription",
  "allin1Sections",
] as const;

const NOT_BADGED = [
  "waveform",
  "humanHints",
  "sections",
  "chords",
  "gestures",
  "fftBands",
  "rmsLoudness",
  "loudnessEnvelope",
  "drums",
  "energy",
  "validation",
] as const;

const flask = (page: Page, laneId: string) =>
  page.locator(`.tl-lane-head[data-lane="${laneId}"] .tl-lane-head__flask`);

test("item 7 — flask badge on unpromoted-experiment lane heads", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // 1. runtime assertions clean (re-checked at the end).

  // 2. badged — exactly these eight.
  for (const id of BADGED) {
    expect(await flask(page, id).count()).toBe(1);
  }

  // 3. not badged — every production lane.
  for (const id of NOT_BADGED) {
    expect(await flask(page, id).count()).toBe(0);
  }

  // 4. whole-document count is exactly eight.
  expect(await page.locator(".tl-lane-head__flask").count()).toBe(BADGED.length);

  // 5. left of the title (checked on `character`).
  const chFlask = flask(page, "character");
  await chFlask.scrollIntoViewIfNeeded();
  const flaskBox = await chFlask.boundingBox();
  const textBox = await page
    .locator('.tl-lane-head[data-lane="character"] .tl-lane-head__name-text')
    .boundingBox();
  expect(flaskBox!.x + flaskBox!.width).toBeLessThanOrEqual(textBox!.x);

  // 6. the label still fits — the badge did not push any label into an ellipsis.
  for (const id of BADGED) {
    const overflow = await page
      .locator(`.tl-lane-head[data-lane="${id}"] .tl-lane-head__name-text`)
      .evaluate((el) => el.scrollWidth - el.clientWidth);
    expect(overflow, `label overflow for ${id}`).toBeLessThanOrEqual(0);
  }

  // 7. the accessible name is the same on every badge.
  await expect(flask(page, "character")).toHaveAttribute(
    "aria-label",
    "Experimental lane",
  );

  // 8. panel header — opening `character`'s events panel shows exactly one badge.
  await page.getByTestId("lane-events-character").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  expect(
    await page.locator(".app-rightpanel .tl-lane-head__flask").count(),
  ).toBe(1);

  // 9. baselines — the eleven `.app-timeline__grid` snapshots are re-captured by
  //    the orchestrator (`--update-snapshots`), not this spec; see guide §9.

  expect(errors.list()).toEqual([]);
});

// The badge sits in the flex row that also holds the collapse caret; item 6's
// caret-fixed-position invariant must be unaffected.
test("item 7 — the caret has not moved", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const caret = page.getByTestId("lane-collapse-character");
  await caret.scrollIntoViewIfNeeded();
  const before = await caret.boundingBox();
  await caret.click();
  const afterExpand = await caret.boundingBox();
  expect(Math.abs(afterExpand!.x - before!.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(afterExpand!.y - before!.y)).toBeLessThanOrEqual(1);

  expect(errors.list()).toEqual([]);
});
