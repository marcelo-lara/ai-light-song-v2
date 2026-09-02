import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

const GRID = ".app-timeline__grid";

test("song-full — fully populated song, all default lanes", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  await expect(page.locator(GRID)).toHaveScreenshot("song-full.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  expect(errors.list()).toEqual([]);
});
