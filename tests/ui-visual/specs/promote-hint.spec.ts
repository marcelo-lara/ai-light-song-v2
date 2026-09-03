import fs from "node:fs";
import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// Plan v1.5 item 9 (R8, the button): the block inspector's "Create human hint"
// action promotes the inspected event to a new, editable human hint. It seeds
// an unsaved draft (D10) and never marks the source artifact (D13); the note
// item 8 stores (`captured_from`) records the lane it came from (D11).
//
// Save goes through the real `PUT /api/human-hints/<song>`, which writes the
// (writable, under the visual compose) fixture file — snapshot it in
// `beforeAll` and restore it in `afterAll` / before each test, exactly as
// `hint-drag.spec.ts` does.
const HINTS_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/human/human_hints.json",
);
const ALLIN1_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/proposals/allin1.json",
);
let hintsFixtureBackup = "";
let allin1FixtureBackup = "";

// Only the humanHints SparseLane carries `data-lane` on the `.tl-canvas-lane`
// container (drag is enabled there only); every other sparse lane is reached
// through the grid row's body cell instead.
const bodySel = (laneId: string) => `.tl-lane-body[data-lane="${laneId}"]`;
const canvasContainerSel = (laneId: string) =>
  `${bodySel(laneId)} .tl-canvas-lane`;

/**
 * Left/right edges (container-local CSS px) of every tinted block drawn on a
 * sparse lane's canvas, left to right. The lane must be expanded first — a
 * collapsed lane only draws faint ticks and its click handler ignores hits.
 * (Same pixel-scan `card-click-seek.spec.ts` uses for the humanHints canvas.)
 */
async function blockEdges(
  page: Page,
  laneId: string,
): Promise<{ x1: number; x2: number }[]> {
  return page.evaluate((sel) => {
    const container = document.querySelector(sel) as HTMLElement | null;
    const canvas = container?.querySelector("canvas") as HTMLCanvasElement | null;
    if (!container || !canvas) return [];
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
  }, canvasContainerSel(laneId));
}

async function expandLane(page: Page, laneId: string): Promise<void> {
  const caret = page.getByTestId(`lane-collapse-${laneId}`);
  if ((await caret.getAttribute("aria-expanded")) !== "true") {
    await caret.click();
  }
  await waitReady(page);
  // wait for the newly-shown canvas to have drawn its blocks
  await expect
    .poll(async () => (await blockEdges(page, laneId)).length, { timeout: 10_000 })
    .toBeGreaterThan(0);
}

/** Click a sparse lane's canvas at container-local x `localX`, at mid-height. */
async function clickLaneAt(page: Page, laneId: string, localX: number): Promise<void> {
  // A prior click may have scrolled another (lower) lane into view; bring this
  // lane's head back on-screen before measuring / clicking. `expandLane` only
  // clicks — and so only auto-scrolls — when the lane was collapsed.
  await page
    .locator(`.tl-lane-head[data-lane="${laneId}"]`)
    .scrollIntoViewIfNeeded();
  // The SparseLane click handler measures `clientX - container.left`, so scroll
  // the timeline to put the target x inside the visible strip first —
  // `page.mouse` never auto-scrolls.
  await page.evaluate((x) => {
    const scroller = document.querySelector(".app-timeline") as HTMLElement | null;
    if (scroller) scroller.scrollLeft = Math.max(0, x - 360);
  }, localX);
  await page.waitForTimeout(50);
  const rect = await page.locator(canvasContainerSel(laneId)).boundingBox();
  if (!rect) throw new Error(`${laneId} lane container not found`);
  await page.mouse.click(rect.x + localX, rect.y + rect.height / 2);
}

/** Expand `laneId` and click the midpoint of its first tinted block. Only safe
 *  where the lane's blocks are visually separated (gaps between runs). */
async function clickFirstBlock(page: Page, laneId: string): Promise<void> {
  await expandLane(page, laneId);
  const [first] = await blockEdges(page, laneId);
  if (!first) throw new Error(`no block found on the ${laneId} lane`);
  await clickLaneAt(page, laneId, (first.x1 + first.x2) / 2);
}

/**
 * Expand `laneId`, find the widest tinted run's mid-x and the vertical centre
 * of the filled pixels there, and click that point. Lanes like `machineEvents`
 * pack short blocks into stacked sub-rows, so a blind mid-height click misses.
 */
async function clickWidestBlock(page: Page, laneId: string): Promise<void> {
  await expandLane(page, laneId);
  const hit = await page.evaluate((sel) => {
    const container = document.querySelector(sel) as HTMLElement | null;
    const canvas = container?.querySelector("canvas") as HTMLCanvasElement | null;
    if (!container || !canvas) return null;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return null;
    const w = canvas.width;
    const h = canvas.height;
    const data = ctx.getImageData(0, 0, w, h).data;
    const colFilled = (x: number) => {
      for (let y = 0; y < h; y++) if (data[(y * w + x) * 4 + 3] !== 0) return true;
      return false;
    };
    const runs: Array<[number, number]> = [];
    let s = -1;
    for (let x = 0; x < w; x++) {
      if (colFilled(x) && s < 0) s = x;
      if (!colFilled(x) && s >= 0) {
        runs.push([s, x - 1]);
        s = -1;
      }
    }
    if (s >= 0) runs.push([s, w - 1]);
    const wide = runs
      .filter((r) => r[1] - r[0] > 3)
      .sort((a, b) => b[1] - b[0] - (a[1] - a[0]))[0];
    if (!wide) return null;
    const cx = Math.round((wide[0] + wide[1]) / 2);
    const ys: number[] = [];
    for (let y = 0; y < h; y++) if (data[(y * w + cx) * 4 + 3] !== 0) ys.push(y);
    if (!ys.length) return null;
    const cssW = canvas.getBoundingClientRect().width || w;
    const cssH = canvas.getBoundingClientRect().height || h;
    return {
      localX: (cx / w) * cssW,
      localY: ((ys[0] + ys[ys.length - 1]) / 2 / h) * cssH,
    };
  }, canvasContainerSel(laneId));
  if (!hit) throw new Error(`no block found on the ${laneId} lane`);

  await page.locator(`.tl-lane-head[data-lane="${laneId}"]`).scrollIntoViewIfNeeded();
  await page.evaluate((x) => {
    const scroller = document.querySelector(".app-timeline") as HTMLElement | null;
    if (scroller) scroller.scrollLeft = Math.max(0, x - 360);
  }, hit.localX);
  await page.waitForTimeout(50);
  const rect = await page.locator(canvasContainerSel(laneId)).boundingBox();
  if (!rect) throw new Error(`${laneId} lane container not found`);
  await page.mouse.click(rect.x + hit.localX, rect.y + hit.localY);
}

/** Seconds represented by the whole timeline canvas, from the header total. */
async function totalSeconds(page: Page): Promise<number> {
  const t = (await page.locator(".app-header__total").textContent()) ?? "";
  const m = t.trim().match(/^(\d+):(\d+(?:\.\d+)?)$/);
  if (!m) throw new Error(`unexpected header total ${JSON.stringify(t)}`);
  return Number(m[1]) * 60 + Number(m[2]);
}

/** Expand `laneId` and click the block covering time `t` (seconds). Used for
 *  `allin1Sections`, whose contiguous sections form one filled canvas run. */
async function clickBlockAtTime(page: Page, laneId: string, t: number): Promise<void> {
  await expandLane(page, laneId);
  const canvas = await page.locator(`${canvasContainerSel(laneId)} canvas`).boundingBox();
  if (!canvas) throw new Error(`${laneId} canvas not found`);
  const total = await totalSeconds(page);
  await clickLaneAt(page, laneId, (t / total) * canvas.width);
}

test.describe("plan v1.5 item 9 — Create human hint from the block inspector", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(() => {
    hintsFixtureBackup = fs.readFileSync(HINTS_FIXTURE, "utf-8");
    allin1FixtureBackup = fs.readFileSync(ALLIN1_FIXTURE, "utf-8");
  });
  test.afterAll(() => {
    if (hintsFixtureBackup) fs.writeFileSync(HINTS_FIXTURE, hintsFixtureBackup);
  });
  test.afterEach(() => {
    // Restore even on a hard failure, so a dirty fixture is never stranded.
    if (hintsFixtureBackup) fs.writeFileSync(HINTS_FIXTURE, hintsFixtureBackup);
  });
  test.beforeEach(async ({ page }) => {
    fs.writeFileSync(HINTS_FIXTURE, hintsFixtureBackup);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);
  });

  test("the inspector promotes an event to a pre-filled, unsaved hint", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    const promote = page.getByTestId("promote-hint");

    // 2. nothing before a selection.
    await expect(promote).toHaveCount(0);

    // 3. the inspector offers it for an allin1Sections block.
    await clickBlockAtTime(page, "allin1Sections", 15);
    await expect(page.locator(".block-inspector")).toBeVisible();
    await expect(promote).toHaveCount(1);
    await expect(promote).toHaveAccessibleName(/Create human hint/);

    // 4. Human Hints routes to the hint editor, never the inspector.
    await clickFirstBlock(page, "humanHints");
    await expect(page.getByTestId("hint-editor")).toBeVisible();
    await expect(promote).toHaveCount(0);

    // 5. present for every inspected event (D12), in both transport states.
    await clickBlockAtTime(page, "allin1Sections", 15);
    await expect(promote).toHaveCount(1);
    await clickWidestBlock(page, "machineEvents");
    await expect(promote).toHaveCount(1);
    await page.locator(".tl-seg-block").nth(1).click();
    await expect(promote).toHaveCount(1);

    // 6. it opens a pre-filled, unsaved draft — from the allin1Sections block.
    await clickBlockAtTime(page, "allin1Sections", 15);
    const title = await page.locator(".block-inspector__title").textContent();
    const clockBefore = await page.locator(".app-header__time").textContent();
    await promote.click();

    const editor = page.getByTestId("hint-editor");
    await expect(editor).toBeVisible();
    await expect(page.locator("#hint-title")).toHaveValue(title ?? "");

    const allin1 = JSON.parse(allin1FixtureBackup) as {
      sections: Array<{ id: string; start_s: number; end_s: number }>;
    };
    const first = [...allin1.sections].sort((a, b) => a.start_s - b.start_s)[0]!;
    expect(
      Math.abs(Number(await page.locator("#hint-start").inputValue()) - first.start_s),
    ).toBeLessThanOrEqual(0.01);
    expect(
      Math.abs(Number(await page.locator("#hint-end").inputValue()) - first.end_s),
    ).toBeLessThanOrEqual(0.01);

    await expect(
      editor.getByText("Captured from allin1 Sections · experiments/allin1"),
    ).toHaveCount(1);
    // promoting never seeks.
    expect(await page.locator(".app-header__time").textContent()).toBe(clockBefore);

    // 7. nothing written yet (D10).
    const beforeSave = JSON.parse(fs.readFileSync(HINTS_FIXTURE, "utf-8")) as {
      human_hints: Array<Record<string, unknown>>;
    };
    expect(beforeSave.human_hints.map((h) => [h.id, h.start_time, h.end_time])).toEqual([
      ["hint-001", 40.0, 48.0],
      ["hint-002", 52.0, 60.0],
      ["hint-003", 64.0, 72.0],
    ]);

    // 8. the source artifact is untouched (D13).
    expect(fs.readFileSync(ALLIN1_FIXTURE, "utf-8")).toBe(allin1FixtureBackup);

    // 9. saving writes it, with the note.
    const put = page
      .waitForResponse(
        (r) =>
          r.request().method() === "PUT" && r.url().includes("/api/human-hints/"),
        { timeout: 10_000 },
      )
      .catch(() => null);
    await editor.getByRole("button", { name: "Save" }).click();
    await put;
    await waitReady(page);

    const afterSave = JSON.parse(fs.readFileSync(HINTS_FIXTURE, "utf-8")) as {
      human_hints: Array<Record<string, unknown>>;
    };
    expect(afterSave.human_hints).toHaveLength(4);
    const promoted = afterSave.human_hints[3]!;
    expect(promoted.title).toBe(title);
    expect(Math.abs(Number(promoted.start_time) - first.start_s)).toBeLessThanOrEqual(0.01);
    expect(Math.abs(Number(promoted.end_time) - first.end_s)).toBeLessThanOrEqual(0.01);
    expect(promoted.captured_from).toBe("allin1 Sections · experiments/allin1");
    for (const h of afterSave.human_hints.slice(0, 3)) {
      expect(h).not.toHaveProperty("captured_from");
    }

    // 10. it appears on the Human Hints lane events panel (no reload).
    await page.getByTestId("lane-events-humanHints").click();
    await expect(page.locator(".lane-events__card")).toHaveCount(4);
    await expect(
      page.locator(".lane-events__card").nth(3).locator(".lane-events__label"),
    ).toHaveText(title ?? "");

    expect(errors.list()).toEqual([]);
  });

  test("baseline — inspector with the promote action", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    fs.writeFileSync(HINTS_FIXTURE, hintsFixtureBackup);

    await clickBlockAtTime(page, "allin1Sections", 15);
    await expect(page.getByTestId("promote-hint")).toHaveCount(1);
    await expect(page.locator(".app-rightpanel")).toHaveScreenshot(
      "inspector-promote.png",
    );

    expect(errors.list()).toEqual([]);
  });
});
