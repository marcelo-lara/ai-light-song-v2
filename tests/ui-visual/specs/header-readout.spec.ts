import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// Plan v1.5 item 5 (R9, R10): the header drops the `bar.beat` caption and
// reserves the width of the moving readouts so the centre group does not shift
// as the clock and bar number grow digits. This is the first `.app-header`
// baseline — no existing spec captures the header.

const LANE = '.tl-canvas-lane[data-lane="humanHints"]';

/**
 * Lane-body-local x edges of the humanHints canvas blocks, left to right. The
 * `RegFull` fixture freezes three blocks (hint-001 40–48, hint-002 52–60,
 * hint-003 64–72), so the runs map 1:1 to hint-001 / hint-002 / hint-003.
 */
async function blockEdges(page: Page): Promise<{ x1: number; x2: number }[]> {
  return page.evaluate((laneSel) => {
    const body = document.querySelector(laneSel) as HTMLElement | null;
    const canvas = body?.querySelector("canvas") as HTMLCanvasElement | null;
    if (!body || !canvas) return [];
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return [];
    const w = canvas.width;
    const h = canvas.height;
    const data = ctx.getImageData(0, 0, w, h).data;
    const cssWidth = canvas.getBoundingClientRect().width || w;
    const toCss = (col: number) => (col / w) * cssWidth;

    const runs: { x1: number; x2: number }[] = [];
    let start = -1;
    for (let x = 0; x < w; x++) {
      let filled = false;
      for (let y = 0; y < h; y++) {
        if (data[(y * w + x) * 4 + 3] !== 0) {
          filled = true;
          break;
        }
      }
      if (filled && start < 0) start = x;
      if (!filled && start >= 0) {
        runs.push({ x1: toCss(start), x2: toCss(x - 1) });
        start = -1;
      }
    }
    if (start >= 0) runs.push({ x1: toCss(start), x2: toCss(w - 1) });
    return runs.filter((r) => r.x2 - r.x1 > 3);
  }, LANE);
}

/**
 * Absolute (page) coordinates for a lane-body-local x, at lane mid-height. The
 * fixture's blocks sit off-screen at the default scroll position and
 * `page.mouse` never auto-scrolls, so scroll the requested x ~360px inside the
 * visible strip first.
 */
async function lanePoint(page: Page, localX: number): Promise<{ x: number; y: number }> {
  await page.evaluate((x) => {
    const scroller = document.querySelector(".app-timeline") as HTMLElement | null;
    if (scroller) scroller.scrollLeft = Math.max(0, x - 360);
  }, localX);
  await page.waitForTimeout(50);
  const rect = await page.locator(LANE).boundingBox();
  if (!rect) throw new Error("humanHints lane body not found");
  return { x: rect.x + localX, y: rect.y + rect.height / 2 };
}

type Box = { x: number; y: number; width: number };

async function boxOf(page: Page, selector: string): Promise<Box> {
  const b = await page.locator(selector).boundingBox();
  if (!b) throw new Error(`${selector} not found`);
  return { x: b.x, y: b.y, width: b.width };
}

test.describe("plan v1.5 item 5 — header readout", () => {
  test("R9: the bar.beat caption is gone", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);

    await expect(page.locator(".app-header__barbeat-caption")).toHaveCount(0);
    const headerText = (await page.locator(".app-header").innerText()).toLowerCase();
    expect(headerText).not.toContain("bar.beat");

    expect(errors.list()).toEqual([]);
  });

  test("R10: readouts do not shift as the values gain digits", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);

    // Start at 0:00.0 / bar 1.1.
    await page.getByRole("button", { name: "To start" }).click();
    await waitReady(page);
    await expect(page.locator(".app-header__time")).toHaveText("0:00.0");
    await expect(page.locator(".app-header__barbeat")).toHaveText("1.1");

    const before = {
      center: await boxOf(page, ".app-header__center"),
      time: await boxOf(page, ".app-header__time"),
      barbeat: await boxOf(page, ".app-header__barbeat"),
    };

    // Reserved widths are real, not incidental (rendered strings are shorter).
    expect(before.time.width).toBeGreaterThanOrEqual(48);
    expect(before.barbeat.width).toBeGreaterThanOrEqual(40);

    // Bring hint-003 (64.0–72.0 s) into view, then click it — a paused card
    // click seeks to its start (plan v1.5 D1), moving the clock to 1:04.0 and
    // the bar number from one digit to two/three.
    const edges = await blockEdges(page);
    expect(edges.length).toBe(3);
    const mid = (edges[2].x1 + edges[2].x2) / 2;
    const pt = await lanePoint(page, mid);
    await page.mouse.move(pt.x, pt.y);
    await page.mouse.down();
    await page.mouse.move(pt.x + 2, pt.y);
    await page.waitForTimeout(50);
    await page.mouse.up();

    await expect(page.locator(".app-header__time")).toHaveText("1:04.0");
    await waitReady(page);

    const after = {
      center: await boxOf(page, ".app-header__center"),
      time: await boxOf(page, ".app-header__time"),
      barbeat: await boxOf(page, ".app-header__barbeat"),
    };

    for (const key of ["center", "time", "barbeat"] as const) {
      expect(Math.abs(after[key].x - before[key].x)).toBeLessThanOrEqual(0.5);
      expect(Math.abs(after[key].y - before[key].y)).toBeLessThanOrEqual(0.5);
      expect(Math.abs(after[key].width - before[key].width)).toBeLessThanOrEqual(0.5);
    }

    // Baseline — playhead at 1:04.0. Not generated here; the orchestrator runs
    // `--update-snapshots`.
    await expect(page.locator(".app-header")).toHaveScreenshot("header-readout.png");

    expect(errors.list()).toEqual([]);
  });
});
