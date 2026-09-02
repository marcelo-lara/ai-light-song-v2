import { test, expect } from "@playwright/test";
import {
  assertNoRuntimeErrors,
  FIXTURES,
  fullExtentOfLane,
  gotoSong,
  waitReady,
} from "../helpers";

const GRID = ".app-timeline__grid";

/** Non-empty pixel columns of the waveform, in lane-body-local CSS px. */
async function waveformColumns(page: import("@playwright/test").Page): Promise<{
  width: number;
  nonEmpty: number[];
}> {
  return page.evaluate(() => {
    const surface = document.querySelector(
      '.tl-lane-body[data-lane="waveform"] .tl-waveform__surface',
    ) as HTMLElement | null;
    const shadow = (surface?.firstElementChild as HTMLElement | null)?.shadowRoot;
    const body = document.querySelector('.tl-lane-body[data-lane="waveform"]') as HTMLElement;
    const width = body.getBoundingClientRect().width;
    const nonEmpty: number[] = [];
    for (const c of (shadow?.querySelectorAll("canvas") ?? []) as unknown as HTMLCanvasElement[]) {
      const ctx = c.getContext("2d", { willReadFrequently: true });
      if (!ctx || !c.width || !c.height) continue;
      const cssW = c.getBoundingClientRect().width;
      const left = parseFloat(c.style.left || "0") || 0;
      const data = ctx.getImageData(0, 0, c.width, c.height).data;
      for (let x = 0; x < c.width; x++) {
        for (let y = 0; y < c.height; y++) {
          if (data[(y * c.width + x) * 4 + 3] !== 0) {
            nonEmpty.push(left + (x / c.width) * cssW);
            break;
          }
        }
      }
    }
    return { width, nonEmpty };
  });
}

/**
 * wavesurfer decodes + paints off the readiness-marker path — wait for its
 * shadow-DOM canvases to exist AND to have painted content reaching the full
 * width of the lane (not just the opening span).
 */
async function waitForWaveform(page: import("@playwright/test").Page): Promise<void> {
  await page.waitForFunction(() => {
    const body = document.querySelector(
      '.tl-lane-body[data-lane="waveform"]',
    ) as HTMLElement | null;
    const surface = body?.querySelector(".tl-waveform__surface") as HTMLElement | null;
    const shadow = (surface?.firstElementChild as HTMLElement | null)?.shadowRoot;
    const canvases = shadow
      ? (Array.from(shadow.querySelectorAll("canvas")) as HTMLCanvasElement[])
      : [];
    if (!canvases.length || !body) return false;
    const width = body.getBoundingClientRect().width;
    let maxX = -1;
    for (const c of canvases) {
      const ctx = c.getContext("2d", { willReadFrequently: true });
      if (!ctx || !c.width || !c.height) return false;
      const cssW = c.getBoundingClientRect().width;
      const left = parseFloat(c.style.left || "0") || 0;
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      for (let x = c.width - 1; x >= 0; x--) {
        let hit = false;
        for (let y = 0; y < c.height; y++) if (d[(y * c.width + x) * 4 + 3] !== 0) { hit = true; break; }
        if (hit) { maxX = Math.max(maxX, left + (x / c.width) * cssW); break; }
      }
    }
    return maxX >= width * 0.97;
  }, undefined, { timeout: 15_000 });
}

test("item 2 — waveform lane renders across the full timeline on a real song", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);
  await waitReady(page);
  await waitForWaveform(page);

  const { width, nonEmpty } = await waveformColumns(page);
  expect(nonEmpty.length).toBeGreaterThan(0);

  // No blank 100px band anywhere up to the waveform's right edge (proves the
  // lane is not truncated to its opening span and is not painted over).
  const lastX = Math.max(...nonEmpty);
  for (let band = 0; band + 100 <= lastX; band += 100) {
    const hit = nonEmpty.some((x) => x >= band && x < band + 100);
    expect(hit, `waveform has content in [${band}, ${band + 100})`).toBe(true);
  }

  // Reaches (near enough) the same right edge as the Bars ruler / every other
  // lane — a silent tail sample can leave a hair of the container unpainted, but
  // the waveform is emphatically not clipped to its opening span.
  const ext = await fullExtentOfLane(page, "waveform");
  expect(ext.hasCanvas).toBe(true);
  expect(ext.lastNonEmptyX).toBeGreaterThanOrEqual(ext.contentWidth * 0.97);
  expect(lastX).toBeGreaterThanOrEqual(width * 0.97);

  // Dedicated snapshot with the waveform region UNMASKED.
  await expect(page.locator(GRID)).toHaveScreenshot("song-full-waveform.png");

  expect(errors.list()).toEqual([]);
});

test("item 2 — waveform renders its unchanged no-audio state with no mp3", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page, { allowMissingAudio: true });
  await gotoSong(page, FIXTURES.noAudio);
  await waitReady(page);

  // With no mp3 wavesurfer decodes nothing — no shadow-DOM waveform canvases.
  // The lane falls back to its no-audio render (unchanged: covered pixel-for-
  // pixel by song-no-audio.png).
  const shadowCanvases = await page.evaluate(() => {
    const surface = document.querySelector(
      '.tl-lane-body[data-lane="waveform"] .tl-waveform__surface',
    ) as HTMLElement | null;
    const shadow = (surface?.firstElementChild as HTMLElement | null)?.shadowRoot;
    return shadow ? shadow.querySelectorAll("canvas").length : 0;
  });
  expect(shadowCanvases).toBe(0);

  await expect(
    page.locator('.tl-lane-body[data-lane="waveform"]'),
  ).toHaveScreenshot("waveform-no-audio.png");

  // Only the missing mp3 may fail; nothing under /data/analysis/.
  expect(errors.list()).toEqual([]);
});
