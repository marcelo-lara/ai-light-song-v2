import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

const GRID = ".app-timeline__grid";

test("timeline-scrolled-50 — viewport scrolled to mid-song", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const viewport = page.getByTestId("timeline-viewport");
  await viewport.evaluate((el) => {
    el.scrollLeft = Math.round((el.scrollWidth - el.clientWidth) * 0.5);
  });
  // settle one rAF: the canvas lanes redraw on the scroll listener.
  await page.evaluate(
    () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );

  await expect(page.locator(GRID)).toHaveScreenshot("timeline-scrolled-50.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  expect(errors.list()).toEqual([]);
});
