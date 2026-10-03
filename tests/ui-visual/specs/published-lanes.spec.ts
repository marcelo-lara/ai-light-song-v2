import fs from "node:fs";
import path from "node:path";

import { test, expect, type Page } from "@playwright/test";

import { assertNoRuntimeErrors, expectHealthy, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.12 item 35 — "Bar Features" and "Light Changes" read published files
// (`bar_features.json`, `song_event_timeline.json` `light_change` rows), not
// `reference/proposals/`. Assertions only, no screenshot. `RegFull` carries both
// files; `RegPartial` carries neither, so neither lane is drawn (no header).
// Fixture times sit on bar starts, so the ruler's `.tl-bar-tick` for bar N is
// the x of that time (the ruler and every lane body share one x origin).

const fixtureJson = (fixture: string, rel: string) =>
  JSON.parse(fs.readFileSync(path.join(process.cwd(), "fixtures/analysis", fixture, rel), "utf-8"));

async function expandLane(page: Page, laneId: string): Promise<void> {
  const caret = page.getByTestId(`lane-collapse-${laneId}`);
  if ((await caret.getAttribute("aria-expanded")) !== "true") await caret.click();
  await waitReady(page);
}

/** Left x of every `.tl-bar-tick` (index = bar - 1), in ruler-local CSS px. */
const barTickXs = (page: Page): Promise<number[]> =>
  page.locator(".tl-ruler-body .tl-bar-tick").evaluateAll((els) =>
    els.map((e) => parseFloat((e as HTMLElement).style.left)),
  );

/** Filled column runs of a lane canvas (lane-local CSS px) and the sampled RGBA at each run's middle, near the band top. */
async function canvasRuns(page: Page, laneId: string) {
  return page.evaluate((id) => {
    const canvas = document.querySelector(`.tl-lane-body[data-lane="${id}"] canvas`) as HTMLCanvasElement | null;
    if (!canvas) return [];
    const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
    const w = canvas.width;
    const h = canvas.height;
    const data = ctx.getImageData(0, 0, w, h).data;
    const k = (canvas.getBoundingClientRect().width || w) / w;
    const filled = (x: number) => {
      for (let y = 0; y < h; y++) if (data[(y * w + x) * 4 + 3] !== 0) return true;
      return false;
    };
    const runs: { x1: number; x2: number; rgb: number[] }[] = [];
    let s = -1;
    const close = (end: number) => {
      const mid = Math.round((s + end) / 2);
      const i = (9 * w + mid) * 4;
      runs.push({ x1: s * k, x2: (end + 1) * k, rgb: [data[i]!, data[i + 1]!, data[i + 2]!] });
    };
    for (let x = 0; x < w; x++) {
      const f = filled(x);
      if (f && s < 0) s = x;
      if (!f && s >= 0) {
        close(x - 1);
        s = -1;
      }
    }
    if (s >= 0) close(w - 1);
    return runs;
  }, laneId);
}

/** RGBA of the lane canvas at each lane-local CSS x, near the top of the block band (clear of the label). */
async function pixelsAt(page: Page, laneId: string, xs: number[]) {
  return page.evaluate(
    ([id, list]) => {
      const canvas = document.querySelector(`.tl-lane-body[data-lane="${id}"] canvas`) as HTMLCanvasElement;
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      const k = canvas.width / (canvas.getBoundingClientRect().width || canvas.width);
      return (list as number[]).map((x) => Array.from(ctx.getImageData(Math.round(x * k), 9, 1, 1).data));
    },
    [laneId, xs] as const,
  );
}

const chroma = (rgb: number[]) => Math.max(...rgb) - Math.min(...rgb);

test.describe("item 35 — lanes from published files", () => {
  test("song-full: Light Changes lane has 3 markers groove_in/build/drop, each at its ruler x", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);

    const rows = (fixtureJson(FIXTURES.full, "song_event_timeline.json").events as {
      type: string;
      role: string;
      start_time: number;
    }[]).filter((e) => e.type === "light_change");
    expect(rows.map((r) => r.role)).toEqual(["groove_in", "build", "drop"]);

    const head = page.locator('.tl-lane-head[data-lane="lightChanges"]');
    await expect(head).toHaveCount(1);
    await expect(head.locator(".tl-lane-head__name-text")).toHaveText("Light Changes");
    await expect(head.locator(".tl-lane-head__flask")).toHaveCount(0);

    await page.getByTestId("lane-events-lightChanges").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveAttribute("data-lane", "lightChanges");
    const cards = page.locator('[data-testid^="lane-event-light-change-"]');
    await expect(cards).toHaveCount(3);
    expect(await cards.locator(".lane-events__label").allTextContents()).toEqual(["groove_in", "build", "drop"]);

    // fixture times are bar starts 9 / 13 / 17 → ruler ticks 8 / 12 / 16
    const beats = fixtureJson(FIXTURES.full, "beats.json").beats as { time: number; bar: number }[];
    const barOf = (t: number) => beats.find((b) => Math.abs(b.time - t) < 1e-6)!.bar;
    const ticks = await barTickXs(page);
    await expandLane(page, "lightChanges");
    const runs = await canvasRuns(page, "lightChanges");
    expect(runs.length).toBe(3);
    rows.forEach((r, i) => {
      const want = ticks[barOf(r.start_time) - 1]!;
      expect(Math.abs(runs[i]!.x1 - want), `${r.role} marker x vs ruler`).toBeLessThanOrEqual(2);
    });

    await expectHealthy(errors);
  });

  test("song-full: Bar Features block count, grey irregular bar, last block ends on the ruler", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);

    const bars = fixtureJson(FIXTURES.full, "bar_features.json").bars as {
      bar: number;
      irregular: boolean;
    }[];
    expect(bars.length).toBeGreaterThanOrEqual(8);
    expect(bars.filter((b) => b.irregular).length).toBe(1);

    const head = page.locator('.tl-lane-head[data-lane="barFeatures"]');
    await expect(head).toHaveCount(1);
    await expect(head.locator(".tl-lane-head__name-text")).toHaveText("Bar Features");
    await expect(head.locator(".tl-lane-head__flask")).toHaveCount(0);

    await page.getByTestId("lane-events-barFeatures").click();
    await expect(page.locator('[data-testid^="lane-event-bar-features-"]')).toHaveCount(bars.length);

    const ticks = await barTickXs(page);
    await expandLane(page, "barFeatures");
    const runs = await canvasRuns(page, "barFeatures");
    expect(runs.length).toBeGreaterThan(0);

    // the irregular bar's block is the only grey one
    const mids = bars.map((b) => (ticks[b.bar - 1]! + ticks[b.bar]!) / 2);
    const px = await pixelsAt(page, "barFeatures", mids);
    px.forEach((p, i) => expect(p[3], `bar ${bars[i]!.bar} drawn`).toBeGreaterThan(0));
    const grey = bars.map((b) => b.irregular);
    const greyChroma = chroma(px[grey.indexOf(true)]!);
    px.forEach((p, i) => {
      if (!grey[i]) expect(chroma(p), `bar ${bars[i]!.bar} is tinted, not grey`).toBeGreaterThan(greyChroma + 10);
    });

    // last block's right edge sits on the ruler x of its end (the next bar's tick)
    const last = bars[bars.length - 1]!;
    const lastRun = runs[runs.length - 1]!;
    expect(Math.abs(lastRun.x2 - ticks[last.bar]!)).toBeLessThanOrEqual(4);

    await expectHealthy(errors);
  });

  test("song-partial: neither lane is drawn, no header", async ({ page }) => {
    // no error sink: RegPartial deliberately lacks core artifacts (FFT bands), whose 404s are its purpose
    await gotoSong(page, FIXTURES.partial);
    await waitReady(page);
    for (const id of ["barFeatures", "lightChanges"]) {
      await expect(page.locator(`.tl-lane-head[data-lane="${id}"]`)).toHaveCount(0);
      await expect(page.locator(`.tl-lane-body[data-lane="${id}"]`)).toHaveCount(0);
    }
  });
});
