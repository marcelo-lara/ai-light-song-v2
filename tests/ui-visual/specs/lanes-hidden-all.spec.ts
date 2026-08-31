import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

const GRID = ".app-timeline__grid";

// Item 8 (R4): "Hide all" on the lane list removes every lane row in one action;
// the sticky Segments + Bars header rows remain and nothing crashes. Individual
// lanes are still re-showable afterward.

test("item 8 — hide all clears every lane row, header rows remain, re-show works", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  await page.getByRole("button", { name: "Lanes" }).click();
  await expect(page.getByTestId("lane-list")).toBeVisible();

  await page.getByTestId("lane-list-hide-all").click();
  await waitReady(page);

  // No lane rows; header rows (Segments + Bars) still present.
  await expect(page.locator('.tl-lane-head[data-lane]')).toHaveCount(0);
  await expect(page.locator('.tl-lane-body[data-lane]')).toHaveCount(0);
  await expect(page.locator(".tl-sticky-head")).toHaveCount(2);

  await expect(page.locator(GRID)).toHaveScreenshot("lanes-hidden-all.png");
  expect(errors.list()).toEqual([]);

  // Re-show one lane from the list → its row reappears and renders.
  await page
    .locator('.tl-lanelist__row', { hasText: "FFT Bands" })
    .getByRole("checkbox")
    .check();
  await waitReady(page);
  await expect(page.locator('.tl-lane-head[data-lane="fftBands"]')).toHaveCount(1);
  await expect(page.locator('.tl-lane-body[data-lane="fftBands"] canvas')).toHaveCount(1);

  expect(errors.list()).toEqual([]);
});
