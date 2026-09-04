import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// Plan v1.5 item 3 (R1 stack + R2 opener): every sparse lane head carries a
// `columns-plus-right` opener; clicking it stacks that lane's events in the
// right panel. The panel is non-modal (D3) — it survives Play, timeline drags
// and scrolls — and a second click on the opener, `esc`, or opening another
// lane's panel closes / replaces it.

const HEAD_RIGHT_PADDING = 11.2; // --space-4

const BLOCK_LANES = [
  "humanHints",
  "moisesLyrics",
  "dropProposals",
  "allin1Transitions",
  "sections",
  "character",
  "vocalTranscription",
  "allin1Sections",
  "chords",
  "patterns",
  "identifierHints",
  "machineEvents",
  "mlEvents",
  "phrases",
] as const;

const NON_BLOCK_LANES = [
  "waveform",
  "fftBands",
  "rmsLoudness",
  "loudnessEnvelope",
  "drums",
  "energy",
  "validation",
] as const;

async function box(page: Page, selector: string) {
  const b = await page.locator(selector).first().boundingBox();
  if (!b) throw new Error(`no bounding box for ${selector}`);
  return b;
}

test("item 3 — lane events opener + stacked non-modal panel", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // 1. runtime assertions clean (checked again at the end).

  // 2. opener present on every block lane.
  for (const id of BLOCK_LANES) {
    expect(await page.getByTestId(`lane-events-${id}`).count()).toBe(1);
  }

  // 3. absent where there is no event list.
  for (const id of NON_BLOCK_LANES) {
    expect(await page.getByTestId(`lane-events-${id}`).count()).toBe(0);
  }

  // 4. right-aligned in the head (R2).
  const headBox = await box(page, '.tl-lane-head[data-lane="humanHints"]');
  const openerBox = await box(page, '[data-testid="lane-events-humanHints"]');
  expect(
    Math.abs(
      openerBox.x + openerBox.width - (headBox.x + headBox.width - HEAD_RIGHT_PADDING),
    ),
  ).toBeLessThanOrEqual(2.0);

  // 5. the opener does not move the caret.
  const caret = page.getByTestId("lane-collapse-humanHints");
  const before = await caret.boundingBox();
  await page.getByTestId("lane-collapse-humanHints").click();
  await waitReady(page);
  await page.getByTestId("lane-collapse-humanHints").click();
  await waitReady(page);
  const after = await caret.boundingBox();
  expect(Math.abs(after!.x - before!.x)).toBeLessThanOrEqual(1.0);
  expect(Math.abs(after!.y - before!.y)).toBeLessThanOrEqual(1.0);

  // 6. opening.
  await page.getByTestId("lane-events-humanHints").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  await expect(page.getByTestId("lane-events-panel")).toHaveAttribute(
    "data-lane",
    "humanHints",
  );
  await expect(page.getByTestId("lane-events-humanHints")).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  // 7. contents — the frozen fixture's three hints, in order.
  const cards = page.locator(".lane-events__card");
  await expect(cards).toHaveCount(3);
  expect(await cards.evaluateAll((els) => els.map((e) => e.getAttribute("data-block-id")))).toEqual(
    ["hint-001", "hint-002", "hint-003"],
  );
  expect(
    await page
      .locator(".lane-events__label")
      .evaluateAll((els) => els.map((e) => e.textContent)),
  ).toEqual(["Drop - approach", "drop build", "drop tension"]);

  // 8. no intermediate spaces (R1).
  const rects = await cards.evaluateAll((els) =>
    els.map((e) => e.getBoundingClientRect()).map((r) => ({ y: r.y, h: r.height })),
  );
  for (let i = 1; i < rects.length; i++) {
    expect(rects[i].y - (rects[i - 1].y + rects[i - 1].h)).toBeLessThanOrEqual(1.0);
  }

  // 9. inset, not full-bleed — the card sits inside `.app-rightpanel`'s own
  // padding (`--space-2` each side) rather than reaching its edge.
  const RIGHTPANEL_PADDING = 5.6; // --space-2, each side
  const panelBox = await box(page, ".app-rightpanel");
  const cardBox = await box(page, ".lane-events__card");
  expect(
    Math.abs(panelBox.width - cardBox.width - 2 * RIGHTPANEL_PADDING),
  ).toBeLessThanOrEqual(1.0);

  // 10. non-modal (D3): these interactions must not dismiss it.
  await page.getByTestId("timeline-viewport").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  await page.getByTestId("lane-collapse-sections").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  await page.getByTestId("zoom-in").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);

  // 11. replacement (R2) — never two panels.
  await page.getByTestId("lane-events-allin1Sections").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  await expect(page.getByTestId("lane-events-panel")).toHaveAttribute(
    "data-lane",
    "allin1Sections",
  );
  await expect(page.getByTestId("lane-events-humanHints")).toHaveAttribute(
    "aria-pressed",
    "false",
  );

  // 12. toggle off.
  await page.getByTestId("lane-events-allin1Sections").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(0);

  // 13. esc closes.
  await page.getByTestId("lane-events-humanHints").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(0);

  // 14. baseline — the paused, at-start panel.
  await page.getByTestId("lane-events-humanHints").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  await page.getByRole("button", { name: "To start" }).click();
  await waitReady(page);
  await expect(page.locator(".app-rightpanel")).toHaveScreenshot(
    "lane-events-panel.png",
  );

  expect(errors.list()).toEqual([]);
});

// Plan v1.5 item 4 (R1 highlight): the card covering the playhead carries
// `data-active="true"` / `aria-current`. The suite cannot press Play, so it
// drives `currentTime` by seeking; the pure rule is `activeBlockIndex`
// (`ui/src/panel/laneEvents.test.ts`).
test("item 4 — active-card highlight follows the playhead", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // 1. runtime assertions clean (checked again at the end).

  await page.getByTestId("lane-events-humanHints").click();
  await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);

  // 2. nothing active at the start (first hint starts at 40.0 s).
  await page.getByRole("button", { name: "To start" }).click();
  await waitReady(page);
  await expect(page.locator('.app-header__time')).toHaveText("0:00.0");
  await expect(page.locator('[data-active="true"]')).toHaveCount(0);

  // 3. a paused card click highlights it.
  await page.getByTestId("lane-event-hint-002").click();
  await expect(page.locator(".app-header__time")).toHaveText("0:52.0");
  const active = page.locator('.lane-events__card[data-active="true"]');
  await expect(active).toHaveCount(1);
  await expect(active).toHaveAttribute("data-block-id", "hint-002");

  // 4. and it moves with the playhead.
  await page.getByTestId("lane-event-hint-003").click();
  await expect(page.locator(".app-header__time")).toHaveText("1:04.0");
  await expect(active).toHaveCount(1);
  await expect(active).toHaveAttribute("data-block-id", "hint-003");

  // 5. baseline — hint-003 active.
  await expect(page.locator(".app-rightpanel")).toHaveScreenshot(
    "lane-events-active.png",
  );

  // 6. the highlight clears in a gap (48.0–52.0, between hint-001 and hint-002).
  await page.getByTestId("lane-event-hint-002").click();
  await expect(page.locator(".app-header__time")).toHaveText("0:52.0");
  await page.getByRole("button", { name: "Previous beat" }).click();
  await expect(page.locator(".app-header__time")).toHaveText("0:51.8");
  await expect(page.locator('[data-active="true"]')).toHaveCount(0);

  expect(errors.list()).toEqual([]);
});
