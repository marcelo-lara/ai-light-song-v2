import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

const GRID = ".app-timeline__grid";

test("lane-collapsed — one lane collapsed via its caret", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const head = page.locator('.tl-lane-head[data-lane="rmsLoudness"]');
  if ((await head.getAttribute("data-lane-collapsed")) !== "true") {
    await page.getByTestId("lane-collapse-rmsLoudness").click();
  }
  await expect(head).toHaveAttribute("data-lane-collapsed", "true");

  await expect(page.locator(GRID)).toHaveScreenshot("lane-collapsed.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  expect(errors.list()).toEqual([]);
});
