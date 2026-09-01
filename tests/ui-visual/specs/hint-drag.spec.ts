import fs from "node:fs";
import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// The drag commit goes through the real `PUT /api/human-hints/<song>` handler,
// which writes `<analysis>/<song>/reference/human/human_hints.json`. Under the
// visual compose that path is the (now writable) fixture file — snapshot it up
// front and restore it after, so a run leaves the fixture byte-for-byte intact.
const HINTS_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/human/human_hints.json",
);
let hintsFixtureBackup = "";

const GRID = ".app-timeline__grid";
const LANE_BODY = '.tl-lane-body[data-lane="humanHints"]';
const LANE = '.tl-canvas-lane[data-lane="humanHints"]';  // The actual SparseLane container with handlers
const DRAG_READY = '[data-lane="humanHints"][data-hint-drag-ready="1"]';

/**
 * Scan the humanHints lane canvas for the tinted block rectangles and return
 * each block's left/right edge in lane-body-local CSS px, left to right. Item
 * 10's fixture (`RegFull`) freezes three clearly-separated blocks
 * (hint-001 40–48, hint-002 52–60, hint-003 64–72), so the runs map 1:1 to
 * hint-001 / hint-002 / hint-003.
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
    // ignore hairline runs (grid lines never register here, but be safe)
    return runs.filter((r) => r.x2 - r.x1 > 3);
  }, LANE);
}

/**
 * Absolute (page) coordinates for a lane-body-local x, at lane mid-height.
 *
 * The fixture's hint blocks sit ~1300px+ into a timeline far wider than the
 * 1280px viewport, so the target x is off-screen at the default scroll
 * position and `page.mouse` (which never auto-scrolls) would dispatch its
 * events into empty space. Scroll the timeline so the requested lane-local x
 * lands ~360px inside the visible content strip first.
 */
async function lanePoint(
  page: Page,
  localX: number,
): Promise<{ x: number; y: number }> {
  await page.evaluate((x) => {
    const scroller = document.querySelector(".app-timeline") as HTMLElement | null;
    if (scroller) scroller.scrollLeft = Math.max(0, x - 360);
  }, localX);
  await page.waitForTimeout(50);
  const rect = await page.locator(LANE).boundingBox();
  if (!rect) throw new Error("humanHints lane body not found");
  return { x: rect.x + localX, y: rect.y + rect.height / 2 };
}

async function dragEdge(
  page: Page,
  fromLocalX: number,
  dxPx: number,
): Promise<void> {
  const from = await lanePoint(page, fromLocalX);

  // Move and start drag
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();

  // Drag with multiple intermediate steps to ensure events fire
  const steps = 8;
  for (let i = 1; i <= steps; i++) {
    const x = from.x + (dxPx * i) / steps;
    await page.mouse.move(x, from.y);
    // Allow browser time to process events
    await page.waitForTimeout(10);
  }

  // The drop fires a real `PUT /api/human-hints/...` whose success reloads the
  // song. Wait for that round-trip AND the reload to settle before returning,
  // otherwise the next canvas read can land in the blank reload window.
  const put = page
    .waitForResponse(
      (r) =>
        r.request().method() === "PUT" &&
        r.url().includes("/api/human-hints/"),
      { timeout: 10_000 },
    )
    .catch(() => null);
  await page.mouse.up();
  await put;
  await waitReady(page);
  await page.waitForSelector(DRAG_READY, { timeout: 20_000 });
  await settleBlocks(page);
}

/**
 * Poll the canvas until the block count is a stable 3 across consecutive reads —
 * the post-save `reloadSong()` briefly empties the lane and this bridges that
 * window without a bare timeout.
 */
async function settleBlocks(page: Page): Promise<void> {
  let prev = -1;
  for (let i = 0; i < 40; i++) {
    const n = (await blockEdges(page)).length;
    if (n >= 2 && n === prev) return;
    prev = n;
    await page.waitForTimeout(50);
  }
}

test.describe("plan v2.1 item 10 — drag to edit a human-hint block", () => {
  // serial: both cases share one on-disk fixture file (the save target).
  test.describe.configure({ mode: "serial" });

  test.beforeAll(() => {
    hintsFixtureBackup = fs.readFileSync(HINTS_FIXTURE, "utf-8");
  });
  test.afterAll(() => {
    if (hintsFixtureBackup) fs.writeFileSync(HINTS_FIXTURE, hintsFixtureBackup);
  });

  test.beforeEach(async ({ page }) => {
    fs.writeFileSync(HINTS_FIXTURE, hintsFixtureBackup);
    await gotoSong(page, FIXTURES.full);
    await page.waitForSelector(DRAG_READY, { timeout: 20_000 });
  });

  test("right-edge resize, interior move, snap, persistence, min-gap, no errors", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);

    // Diagnostic: verify the drag-ready marker and element properties
    const laneElement = await page.locator(LANE).first();
    const marker = await page.locator(DRAG_READY).first();
    const hasDragReady = await marker.count().then(c => c > 0);
    const elementBox = await laneElement.boundingBox();
    const elementAttrs = await page.evaluate((sel) => {
      const el = document.querySelector(sel) as HTMLElement | null;
      return el ? { className: el.className, dateLane: el.getAttribute("data-lane"), dragReady: el.getAttribute("data-hint-drag-ready") } : null;
    }, LANE);

    expect(hasDragReady).toBe(true);
    expect(elementBox).not.toBeNull();
    expect(elementAttrs?.dragReady).toBe("1");

    const before = await blockEdges(page);
    expect(before.length).toBeGreaterThanOrEqual(3);

    // --- right-edge resize: block 1 right edge +40px --------------------
    const b1 = before[0];
    await dragEdge(page, b1.x2, 40);
    let now = await blockEdges(page);
    expect(now[0].x2 - b1.x2).toBeGreaterThan(38);
    expect(now[0].x2 - b1.x2).toBeLessThan(42);
    expect(Math.abs(now[0].x1 - b1.x1)).toBeLessThanOrEqual(1.5);

    // --- left-edge resize: block 2 left edge -25px ---------------------
    const b2 = now[1];
    await dragEdge(page, b2.x1, -25);
    now = await blockEdges(page);
    expect(now[1].x1 - b2.x1).toBeLessThan(-23);
    expect(now[1].x1 - b2.x1).toBeGreaterThan(-27);
    expect(Math.abs(now[1].x2 - b2.x2)).toBeLessThanOrEqual(1.5);

    // --- interior move: block 3 centre +60px -------------------------
    const b3 = now[2];
    const b3mid = (b3.x1 + b3.x2) / 2;
    const width3 = b3.x2 - b3.x1;
    await dragEdge(page, b3mid, 60);
    now = await blockEdges(page);
    expect(now[2].x1 - b3.x1).toBeGreaterThan(58);
    expect(now[2].x1 - b3.x1).toBeLessThan(62);
    expect(Math.abs(now[2].x2 - now[2].x1 - width3)).toBeLessThanOrEqual(1.5);

    // baseline captured after the resize + move, before reload.
    await expect(page.locator(GRID)).toHaveScreenshot("hint-drag-resized.png", {
      mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
    });

    const postDrag = await blockEdges(page);

    // --- persistence across reload -----------------------------------
    // The three edits above each went through the real PUT; a fresh load must
    // read them straight back from disk.
    await gotoSong(page, FIXTURES.full);
    await page.waitForSelector(DRAG_READY, { timeout: 20_000 });
    const afterReload = await blockEdges(page);
    expect(afterReload.length).toBe(postDrag.length);
    for (let i = 0; i < postDrag.length; i++) {
      expect(Math.abs(afterReload[i].x1 - postDrag[i].x1)).toBeLessThanOrEqual(2);
      expect(Math.abs(afterReload[i].x2 - postDrag[i].x2)).toBeLessThanOrEqual(2);
    }

    // --- snap: block 1 right edge dragged to 3px short of block 2 left --
    // A successful snap makes blocks 1 and 2 edge-flush, so the canvas scan
    // fuses them into a single run: proof of the snap is the run count dropping
    // to 2 with the fused span from block 1's left to block 2's right. (If it
    // lands a hair off, we still tolerate <=1.5px against block 2's left.)
    const gap = afterReload[1].x1 - afterReload[0].x2;
    await dragEdge(page, afterReload[0].x2, gap - 3);
    const snapped = await blockEdges(page);
    if (snapped.length === 2) {
      expect(Math.abs(snapped[0].x1 - afterReload[0].x1)).toBeLessThanOrEqual(2);
      expect(Math.abs(snapped[0].x2 - afterReload[1].x2)).toBeLessThanOrEqual(2);
    } else {
      expect(Math.abs(snapped[0].x2 - afterReload[1].x1)).toBeLessThanOrEqual(1.5);
    }

    // --- constraint: block 3 right edge cannot cross its own left ------
    // Overshoot the drag well past the block's own left edge; the clamp pins
    // `end` to `start + MIN_GAP_S`, so the block stays forward (never inverts).
    // It collapses to a sub-pixel sliver the canvas scan filters out, so assert
    // on the persisted file, which is the ground truth the clamp protects.
    const b3r = (snapped.length === 2 ? snapped[1] : snapped[2]);
    await dragEdge(page, b3r.x2, -(b3r.x2 - b3r.x1) - 40);
    const hint3 = JSON.parse(fs.readFileSync(HINTS_FIXTURE, "utf-8")).human_hints.find(
      (h: { id: string }) => h.id === "hint-003",
    );
    expect(hint3.end_time).toBeGreaterThan(hint3.start_time);
    expect(hint3.end_time - hint3.start_time).toBeGreaterThanOrEqual(0.049);

    expect(errors.list()).toEqual([]);
  });

  test("a click (<4px travel) still opens the hint editor", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);

    const edges = await blockEdges(page);
    const b2mid = (edges[1].x1 + edges[1].x2) / 2;
    const pt = await lanePoint(page, b2mid);

    // Minimal travel (2px < 4px click threshold) - should trigger click handler, not drag
    await page.mouse.move(pt.x, pt.y);
    await page.mouse.down();
    await page.mouse.move(pt.x + 2, pt.y);
    await page.waitForTimeout(50);
    await page.mouse.up();

    const editor = page.locator('[data-testid="hint-editor"]');
    await expect(editor).toBeVisible();
    await expect(editor).toHaveAttribute("data-hint-id", "hint-002");

    expect(errors.list()).toEqual([]);
  });
});
