import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

const GRID = ".app-timeline__grid";

// Item 7 (R3): "Fit to width" is an icon-only control — no text, no border —
// with the same hover-background swap as zoom-in / zoom-out.

test("item 7 — fit-to-width is icon-only with the shared hover treatment", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const fit = page.getByTestId("fit-to-width");
  const zoomIn = page.getByTestId("zoom-in");

  // No visible text, keeps its accessible name.
  expect((await fit.innerText()).trim()).toBe("");
  await expect(fit).toHaveAttribute("aria-label", "Fit to width");

  const bw = await fit.evaluate((el) => getComputedStyle(el).borderTopWidth);
  expect(bw).toBe("0px");

  // Default background matches zoom-in's.
  const bgOf = (loc: typeof fit) =>
    loc.evaluate((el) => getComputedStyle(el).backgroundColor);
  const fitBg = await bgOf(fit);
  expect(await bgOf(zoomIn)).toBe(fitBg);

  // Hover swaps the background; unhover reverts.
  await fit.hover();
  const fitBgHover = await bgOf(fit);
  expect(fitBgHover).not.toBe(fitBg);
  await zoomIn.hover();
  expect(await bgOf(zoomIn)).toBe(fitBgHover);
  await page.mouse.move(0, 0);
  expect(await bgOf(fit)).toBe(fitBg);

  // Action still works: it zooms the timeline out toward fit (content narrows).
  const contentW = () =>
    page.locator('.tl-lane-body[data-lane]').first().evaluate((el) => el.getBoundingClientRect().width);
  const before = await contentW();
  await fit.click();
  await waitReady(page);
  const after = await contentW();
  expect(after).toBeLessThan(before);

  await expect(page.locator(GRID)).toHaveScreenshot("timeline-zoom-min.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  expect(errors.list()).toEqual([]);
});
