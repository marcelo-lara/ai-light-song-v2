import { test, expect, type Page } from "@playwright/test";

import {
  assertNoRuntimeErrors,
  FIXTURES,
  fullExtentOfLane,
  gotoSong,
  waitReady,
} from "../helpers";

// Plan v3.4 item 1 — Per-stem FFT bands.
// Four dense canvas lanes (`FFT Bands · Bass/Drums/Harmonic/Vocals`), one per
// Demucs stem, beside the existing mix `FFT Bands` lane. Same renderer
// (`kind: "fft"`), each reads its own `artifacts/essentia/fft_bands.<stem>.json`.
// They are `src/` output, so they carry NO flask badge.
//
// D1.2 (resolved, 2026-09-10): the item's Visual QA lists a "within 4px of the
// right content edge" full-extent check. The FFT renderer has a spectral
// visibility floor — a near-silent tail legitimately paints nothing at the far
// right without the canvas being "short" — which is why the existing mix-lane
// spec (`continuous-lanes-extent.spec.ts`) asserts the FFT extent at 95% of the
// timeline, not 4px. The per-stem lanes use the identical renderer, so this
// spec matches that precedent (>= 95%) rather than the literal 4px.

const STEM_LANES = [
  "fftBandsBass",
  "fftBandsDrums",
  "fftBandsHarmonic",
  "fftBandsVocals",
] as const;

async function expandLanes(page: Page, ids: readonly string[]) {
  for (const id of ids) {
    const head = page.locator(`.tl-lane-head[data-lane="${id}"]`);
    if ((await head.getAttribute("data-lane-collapsed")) === "true")
      await page.getByTestId(`lane-collapse-${id}`).click();
  }
  await page.waitForFunction(
    (list) =>
      list.every(
        (id) =>
          document
            .querySelector(`.tl-lane-head[data-lane="${id}"]`)
            ?.getAttribute("data-lane-collapsed") === "false",
      ),
    [...ids],
  );
}

test("item 1 — four per-stem FFT lane heads, none badged", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // exactly one head per stem lane id
  for (const id of STEM_LANES) {
    expect(await page.locator(`.tl-lane-head[data-lane="${id}"]`).count(), id).toBe(1);
  }
  // exactly four lanes match the per-stem id prefix and are not the mix lane
  const stemHeadCount = await page
    .locator(".tl-lane-head[data-lane^='fftBands']:not([data-lane='fftBands'])")
    .count();
  expect(stemHeadCount).toBe(4);

  // src/ output — no flask badge on any of them, in the head or (once opened) the panel
  for (const id of STEM_LANES) {
    expect(
      await page.locator(`.tl-lane-head[data-lane="${id}"] .tl-lane-head__flask`).count(),
      `${id} flask`,
    ).toBe(0);
  }

  expect(errors.list()).toEqual([]);
});

test("item 1 — each stem canvas backs the full timeline and paints its data", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);
  await expandLanes(page, STEM_LANES);
  await page.getByTestId("fit-to-width").click();
  await waitReady(page);

  for (const id of STEM_LANES) {
    const ext = await fullExtentOfLane(page, id);
    expect(ext.hasCanvas, `${id} has a canvas`).toBe(true);

    const backing = await page.evaluate((lane) => {
      const c = document.querySelector(
        `.tl-lane-body[data-lane="${lane}"] canvas`,
      ) as HTMLCanvasElement | null;
      return c ? { w: c.width, styleW: parseFloat(c.style.width || "0") } : null;
    }, id);
    expect(backing, `${id} canvas present`).not.toBeNull();
    expect(
      Math.abs(backing!.styleW - ext.contentWidth),
      `${id} canvas CSS width matches the timeline content width`,
    ).toBeLessThanOrEqual(1);
    expect(backing!.w, `${id} backing store non-trivial`).toBeGreaterThan(
      ext.contentWidth * 0.9,
    );

    // spectral visibility floor — data reaches past 95% of the timeline (D1.2)
    expect(
      ext.lastNonEmptyX,
      `${id} data reaches past 95% (last=${ext.lastNonEmptyX} of ${ext.contentWidth})`,
    ).toBeGreaterThanOrEqual(ext.contentWidth * 0.95);
  }

  expect(errors.list()).toEqual([]);
});

test("item 1 — stem canvases redraw at min and max zoom", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);
  await expandLanes(page, STEM_LANES);

  // max zoom
  for (let i = 0; i < 16; i++) await page.getByTestId("zoom-in").click();
  await waitReady(page);
  for (const id of STEM_LANES) {
    const ext = await fullExtentOfLane(page, id);
    expect(ext.hasCanvas, `${id} canvas at max zoom`).toBe(true);
    expect(ext.lastNonEmptyX, `${id} painted at max zoom`).toBeGreaterThan(0);
  }

  // min zoom
  await page.getByTestId("fit-to-width").click();
  await waitReady(page);
  for (const id of STEM_LANES) {
    const ext = await fullExtentOfLane(page, id);
    expect(ext.lastNonEmptyX, `${id} painted at min zoom`).toBeGreaterThanOrEqual(
      ext.contentWidth * 0.95,
    );
  }

  expect(errors.list()).toEqual([]);
});

test("item 1 — per-stem lane baseline (min + max zoom)", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);
  await expandLanes(page, STEM_LANES);
  await page.getByTestId("fit-to-width").click();
  await waitReady(page);

  const region = page.locator(".app-timeline__grid");
  await expect(region).toHaveScreenshot("fft-bands-stems-min-zoom.png", {
    mask: [page.locator("[data-lane='waveform'] canvas")],
  });

  for (let i = 0; i < 16; i++) await page.getByTestId("zoom-in").click();
  await waitReady(page);
  await expect(region).toHaveScreenshot("fft-bands-stems-max-zoom.png", {
    mask: [page.locator("[data-lane='waveform'] canvas")],
  });

  expect(errors.list()).toEqual([]);
});
