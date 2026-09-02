import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

const GRID = ".app-timeline__grid";

test("timeline-zoom-max — zoomed all the way in", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const zoomIn = page.getByTestId("zoom-in");
  for (let i = 0; i < 16; i++) await zoomIn.click();
  await waitReady(page);

  await expect(page.locator(GRID)).toHaveScreenshot("timeline-zoom-max.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });
  expect(errors.list()).toEqual([]);
});

test("timeline-zoom-min — fit-to-width (whole song visible)", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  await page.getByTestId("fit-to-width").click();
  await waitReady(page);

  await expect(page.locator(GRID)).toHaveScreenshot("timeline-zoom-min.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });
  expect(errors.list()).toEqual([]);
});
