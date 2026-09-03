import { test, expect } from "@playwright/test";
import {
  assertNoRuntimeErrors,
  FIXTURES,
  gotoSong,
  injectDeterminism,
  waitReady,
} from "../helpers";

const GRID = ".app-timeline__grid";

// Item 4 (R2): the left panel mounts collapsed by default, the burger toggles
// it, esc closes it, and the open/closed state persists across a reload.

test("item 4 — left panel collapsed by default, toggle, esc, persistence", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // On a fresh load the drawer is absent / collapsed and the timeline starts at
  // the label column's right edge.
  const panel = page.getByTestId("left-panel");
  if ((await panel.count()) > 0) {
    await expect(panel).toHaveAttribute("data-open", "false");
  }
  const viewport = page.getByTestId("timeline-viewport");
  const vpBox1 = await viewport.boundingBox();
  // Collapsed: the timeline fills the width from the main area's left edge.
  expect(vpBox1!.x).toBeLessThanOrEqual(2);
  // (the collapsed-panel full-song baseline is `song-full.png` in song-full.spec.ts)

  // Burger opens it; the timeline reflows right (not covered).
  await page.getByTestId("burger-toggle").click();
  await waitReady(page);
  await expect(page.getByTestId("left-panel")).toHaveAttribute("data-open", "true");
  const drawerBox = await page.getByTestId("left-panel").boundingBox();
  expect(drawerBox!.width).toBeGreaterThan(0);
  const vpBox2 = await viewport.boundingBox();
  expect(vpBox2!.x).toBeGreaterThan(vpBox1!.x + drawerBox!.width - 4);

  await expect(page.locator(GRID)).toHaveScreenshot("left-panel-open.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  // esc closes it.
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("left-panel")).toHaveCount(0);

  // Persistence: leave it open, reload, it comes back open.
  await page.getByTestId("burger-toggle").click();
  await expect(page.getByTestId("left-panel")).toHaveAttribute("data-open", "true");
  await page.reload();
  await waitReady(page);
  await expect(page.getByTestId("left-panel")).toHaveAttribute("data-open", "true");

  expect(errors.list()).toEqual([]);
});

// Item 2 (plan v1.5, R4/R5): the left panel hides on any outside click and on
// picking a song; an inside click never dismisses it, and the burger's
// mousedown/click pair does not leave it open. No new baseline image —
// `left-panel-open.png` is unchanged and covered by the first test.
test("item 2 — left panel hides on outside click and on song pick", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const panel = page.getByTestId("left-panel");
  const burger = page.getByTestId("burger-toggle");

  // Open it.
  await burger.click();
  await waitReady(page);
  await expect(panel).toHaveAttribute("data-open", "true");

  // An inside click never dismisses.
  await page.getByRole("button", { name: "Timeline" }).click();
  await expect(panel).toHaveAttribute("data-open", "true");

  // A click on the timeline viewport closes it.
  await page.getByTestId("timeline-viewport").click();
  await expect(panel).toHaveCount(0);

  // The burger's mousedown (close) → click (toggle) pair does not re-open it.
  await burger.click();
  await expect(panel).toHaveAttribute("data-open", "true");
  await burger.click();
  await expect(panel).toHaveCount(0);

  // esc still closes (re-asserted — the new listener sits next to it).
  await burger.click();
  await expect(panel).toHaveAttribute("data-open", "true");
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);

  // R4 path: picking a song from the drawer closes the panel.
  await injectDeterminism(page);
  await page.goto("/");
  await page.waitForSelector('[data-testid="burger-toggle"]', { timeout: 20_000 });
  await burger.click();
  await expect(panel).toHaveAttribute("data-open", "true");
  await page.getByRole("button", { name: "Select Song" }).click();
  await page.getByRole("button", { name: FIXTURES.full }).click();
  await expect(panel).toHaveCount(0);
  expect(page.url()).toMatch(/song=RegFull(\+|%20| )-(\+|%20| )Fixture/);

  expect(errors.list()).toEqual([]);
});
