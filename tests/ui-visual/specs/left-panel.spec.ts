import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

const GRID = ".app-timeline__grid";

// Item 1 baseline for the left panel. Item 4 changes the default to collapsed
// and fleshes out the open/close + persistence assertions.
test("left-panel-open — drawer visible beside the timeline", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const panel = page.getByTestId("left-panel");
  if ((await panel.count()) === 0 || (await panel.getAttribute("data-open")) !== "true") {
    await page.getByTestId("burger-toggle").click();
  }
  await expect(page.getByTestId("left-panel")).toHaveAttribute("data-open", "true");

  await expect(page.locator(GRID)).toHaveScreenshot("left-panel-open.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  expect(errors.list()).toEqual([]);
});
