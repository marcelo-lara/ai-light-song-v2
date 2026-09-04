import { test, expect } from "@playwright/test";
import {
  assertNoRuntimeErrors,
  FIXTURES,
  fullExtentOfLane,
  gotoSong,
  waitReady,
} from "../helpers";

const LANES = ["fftBands", "rmsLoudness", "loudnessEnvelope"] as const;
// `drums` / `energy` share the CanvasLane base — the fix must hold for them too.
const ALSO = ["drums", "energy"] as const;

async function expandLanes(page: import("@playwright/test").Page, ids: readonly string[]) {
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

async function scrollTimeline(page: import("@playwright/test").Page, ratio: number) {
  await page.getByTestId("timeline-viewport").evaluate((el, r) => {
    el.scrollLeft = Math.round((el.scrollWidth - el.clientWidth) * r);
  }, ratio);
  await page.evaluate(
    () => new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))),
  );
}

/**
 * The lane's backing canvas must be sized to the whole timeline (not the
 * viewport) and its rendered content must reach the content right edge — within
 * 4px for the lanes that paint a continuous field (rms / envelope / energy /
 * drums), or within 5% for FFT Bands, whose right edge tracks the last frame
 * that clears the spectral visibility floor (a near-silent outro legitimately
 * renders nothing without the canvas being "short").
 */
async function expectFullExtent(page: import("@playwright/test").Page, lane: string) {
  const ext = await fullExtentOfLane(page, lane);
  expect(ext.hasCanvas, `${lane} has a canvas`).toBe(true);

  // Backing store spans the full content width, not just the viewport.
  const backing = await page.evaluate((id) => {
    const c = document.querySelector(
      `.tl-lane-body[data-lane="${id}"] canvas`,
    ) as HTMLCanvasElement | null;
    return c ? { w: c.width, styleW: parseFloat(c.style.width || "0") } : null;
  }, lane);
  expect(backing, `${lane} canvas present`).not.toBeNull();
  expect(
    Math.abs(backing!.styleW - ext.contentWidth),
    `${lane} canvas CSS width matches the timeline content width`,
  ).toBeLessThanOrEqual(1);
  // The backing store spans the full content width — as long as that fits under
  // Chrome's ~32k canvas ceiling. At the 360 px/bar max zoom a long song blows
  // past it; CanvasLane then keeps the CSS width exact (asserted above) and
  // downscales the backing store, so only require it to stay substantial.
  const MAX_CANVAS_PX = 32000;
  expect(backing!.w, `${lane} canvas backing store is non-trivial`).toBeGreaterThan(
    ext.contentWidth > MAX_CANVAS_PX
      ? MAX_CANVAS_PX / 2
      : ext.contentWidth * 0.9,
  );

  const shortfall = ext.contentWidth - ext.lastNonEmptyX;
  // FFT Bands (spectral visibility floor) and Drums (last discrete event) have a
  // content-dependent right edge — assert they run well past the opening span,
  // not to an exact pixel. The continuous-field lanes reach the exact edge.
  if (lane === "fftBands" || lane === "drums") {
    expect(
      ext.lastNonEmptyX,
      `${lane} data reaches past 95% of the timeline (last=${ext.lastNonEmptyX} of ${ext.contentWidth})`,
    ).toBeGreaterThanOrEqual(ext.contentWidth * 0.95);
  } else {
    expect(
      shortfall,
      `${lane} draws to the content right edge (last=${ext.lastNonEmptyX} of ${ext.contentWidth})`,
    ).toBeLessThanOrEqual(4);
  }
}

test("item 3 — continuous lanes span the full timeline at min zoom", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);
  await expandLanes(page, ALSO);
  await page.getByTestId("fit-to-width").click();
  await waitReady(page);

  for (const lane of [...LANES, ...ALSO]) await expectFullExtent(page, lane);

  expect(errors.list()).toEqual([]);
});

test("item 3 — full extent survives horizontal scroll (redraw covers the whole song)", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);
  await expandLanes(page, ALSO);
  await waitReady(page);

  for (const ratio of [0.5, 1]) {
    await scrollTimeline(page, ratio);
    for (const lane of [...LANES, ...ALSO]) await expectFullExtent(page, lane);
  }

  expect(errors.list()).toEqual([]);
});

test("item 3 — full extent holds at max zoom", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);
  await expandLanes(page, ALSO);
  for (let i = 0; i < 16; i++) await page.getByTestId("zoom-in").click();
  await waitReady(page);
  await scrollTimeline(page, 1);

  for (const lane of [...LANES, ...ALSO]) await expectFullExtent(page, lane);

  expect(errors.list()).toEqual([]);
});
