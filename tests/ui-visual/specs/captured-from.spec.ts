import fs from "node:fs";
import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// Plan v1.5 item 8: the optional `captured_from` note on a human hint.
//
// The fixture's three hints are hand-authored and must stay that way — none
// carries `captured_from`, and saving an untouched hint through the editor must
// not introduce it. Saving goes through the real `PUT /api/human-hints/<song>`,
// which writes the (writable, under the visual compose) fixture file, so
// snapshot it up front and restore it after — same pattern as `hint-drag.spec.ts`.
const HINTS_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/human/human_hints.json",
);
let hintsFixtureBackup = "";

const LANE = '.tl-canvas-lane[data-lane="humanHints"]';
const DRAG_READY = '[data-lane="humanHints"][data-hint-drag-ready="1"]';

// hint-001 spans 40–48 s; bring its block into the viewport and click its centre.
async function clickFirstHintBlock(page: Page): Promise<void> {
  const localX = await page.evaluate((laneSel) => {
    const body = document.querySelector(laneSel) as HTMLElement | null;
    const canvas = body?.querySelector("canvas") as HTMLCanvasElement | null;
    if (!body || !canvas) return -1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return -1;
    const w = canvas.width;
    const h = canvas.height;
    const data = ctx.getImageData(0, 0, w, h).data;
    const cssWidth = canvas.getBoundingClientRect().width || w;
    for (let x = 0; x < w; x++) {
      for (let y = 0; y < h; y++) {
        if (data[(y * w + x) * 4 + 3] !== 0) return (x / w) * cssWidth;
      }
    }
    return -1;
  }, LANE);
  if (localX < 0) throw new Error("no hint block found on the humanHints lane");

  await page.evaluate((x) => {
    const scroller = document.querySelector(".app-timeline") as HTMLElement | null;
    if (scroller) scroller.scrollLeft = Math.max(0, x - 360);
  }, localX);
  await page.waitForTimeout(50);
  const rect = await page.locator(LANE).boundingBox();
  if (!rect) throw new Error("humanHints lane body not found");
  await page.mouse.click(rect.x + localX + 6, rect.y + rect.height / 2);
}

test.describe("plan v1.5 item 8 — captured_from note", () => {
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

  test("hand-authored hints show no note and saving does not add the key", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);

    await clickFirstHintBlock(page);

    const editor = page.locator('[data-testid="hint-editor"]');
    await expect(editor).toBeVisible();
    await expect(editor).toHaveAttribute("data-hint-id", "hint-001");

    // No read-only "Captured from …" line — the fixture hint is hand-authored.
    await expect(editor.getByText(/^Captured from/)).toHaveCount(0);

    // Save the untouched hint through the real PUT round-trip.
    const put = page
      .waitForResponse(
        (r) =>
          r.request().method() === "PUT" &&
          r.url().includes("/api/human-hints/"),
        { timeout: 10_000 },
      )
      .catch(() => null);
    await editor.getByRole("button", { name: "Save" }).click();
    await put;
    await waitReady(page);

    const onDisk = JSON.parse(fs.readFileSync(HINTS_FIXTURE, "utf-8")) as {
      human_hints: Array<Record<string, unknown>>;
    };
    expect(onDisk.human_hints.map((h) => [h.id, h.start_time, h.end_time])).toEqual([
      ["hint-001", 40.0, 48.0],
      ["hint-002", 52.0, 60.0],
      ["hint-003", 64.0, 72.0],
    ]);
    for (const h of onDisk.human_hints) {
      expect(h).not.toHaveProperty("captured_from");
    }

    expect(errors.list()).toEqual([]);
  });
});
