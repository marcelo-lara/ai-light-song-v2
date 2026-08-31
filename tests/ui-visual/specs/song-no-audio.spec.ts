import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

const GRID = ".app-timeline__grid";

test("song-no-audio — synthetic fixture, waveform beat-pulse fallback", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page, { allowMissingAudio: true });
  await gotoSong(page, FIXTURES.noAudio);

  await expect(page.locator(GRID)).toHaveScreenshot("song-no-audio.png");

  // Only the missing mp3 is tolerated; nothing under /data/analysis/ may fail.
  expect(errors.list()).toEqual([]);
});
