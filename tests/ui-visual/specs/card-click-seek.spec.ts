import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

// Plan v1.5 item 1 (R3 / D1): a card click while the transport is *playing*
// must not move the playhead. The suite cannot press Play (see "Conventions for
// every item" in the plan), so the playing half is unit-tested in
// `ui/src/app/transportRules.test.ts`. Here we assert the paused half — every
// one of those clicks still seeks and still opens its panel — and that the
// background-click seeks (Bars ruler) are untouched.

const HUMAN_HINTS_LANE = '.tl-canvas-lane[data-lane="humanHints"]';
const DRAG_READY = '[data-lane="humanHints"][data-hint-drag-ready="1"]';

/**
 * Left/right edges (lane-body-local CSS px) of every tinted block drawn on the
 * humanHints canvas, left to right. RegFull freezes three clearly separated
 * blocks — hint-001 (40–48), hint-002 (52–60), hint-003 (64–72) — so the runs
 * map 1:1 to hint-001 / hint-002 / hint-003.
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
  }, HUMAN_HINTS_LANE);
}

/**
 * Absolute (page) coordinates for a lane-body-local x, at lane mid-height. The
 * fixture's hint blocks sit far past the 1280px viewport, so scroll the
 * timeline to bring the requested x ~360px inside the visible strip first —
 * `page.mouse` never auto-scrolls.
 */
async function lanePoint(page: Page, localX: number): Promise<{ x: number; y: number }> {
  await page.evaluate((x) => {
    const scroller = document.querySelector(".app-timeline") as HTMLElement | null;
    if (scroller) scroller.scrollLeft = Math.max(0, x - 360);
  }, localX);
  await page.waitForTimeout(50);
  const rect = await page.locator(HUMAN_HINTS_LANE).boundingBox();
  if (!rect) throw new Error("humanHints lane body not found");
  return { x: rect.x + localX, y: rect.y + rect.height / 2 };
}

async function clockText(page: Page): Promise<string> {
  return (await page.locator(".app-header__time").first().innerText()).trim();
}

test.describe("plan v1.5 item 1 — a card click never moves the playhead while playing", () => {
  test("paused card clicks still seek and open a panel; background clicks still seek", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await page.waitForSelector(DRAG_READY, { timeout: 20_000 });

    const edges = await blockEdges(page);
    expect(edges.length).toBeGreaterThanOrEqual(3);

    // 2 — paused click on the hint-002 block seeks to 52.0 s.
    const b2mid = (edges[1].x1 + edges[1].x2) / 2;
    let pt = await lanePoint(page, b2mid);
    await page.mouse.click(pt.x, pt.y);
    await expect.poll(() => clockText(page)).toBe("0:52.0");

    // 3 — and it opened the panel (humanHints routes to the hint editor).
    await expect(page.locator(".app-rightpanel")).toHaveCount(1);

    // 4 — click the hint-003 block; clock reads 1:04.0.
    const edges2 = await blockEdges(page);
    const b3mid = (edges2[2].x1 + edges2[2].x2) / 2;
    pt = await lanePoint(page, b3mid);
    await page.mouse.click(pt.x, pt.y);
    await expect.poll(() => clockText(page)).toBe("1:04.0");

    // 5 — a segment card seeks too. The first .tl-seg-block starts at 0.0 where
    // the playhead may already sit, so click the second.
    const seg = page.locator(".tl-seg-block").nth(1);
    await seg.scrollIntoViewIfNeeded();
    await seg.click();
    await expect.poll(() => clockText(page)).toBe("0:15.2");

    // 6 — background clicks still seek: click the Bars ruler at the horizontal
    // centre of the *visible* timeline. Position-relative clicks land off-screen
    // once the timeline has scrolled, so click by absolute page coordinates.
    const vp = await page.getByTestId("timeline-viewport").boundingBox();
    const ruler = await page.locator(".tl-ruler-body").boundingBox();
    if (!vp || !ruler) throw new Error("timeline viewport / ruler not found");
    await page.mouse.click(vp.x + vp.width / 2, ruler.y + ruler.height / 2);
    await expect
      .poll(() => clockText(page).then((t) => parseFloat(t.split(":")[1])))
      .toBeGreaterThan(20.0);

    expect(errors.list()).toEqual([]);
  });
});
