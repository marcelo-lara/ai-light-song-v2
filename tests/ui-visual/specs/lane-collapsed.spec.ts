import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

const GRID = ".app-timeline__grid";

// Item 5 (R1): a collapsed lane header shows the title only — no sub-caption —
// while the faint mini data-strip in the lane body is unchanged. Expanding
// restores the sub-caption.

test("item 5 — collapsed lane shows the title only, strip present, expand restores sub", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const head = page.locator('.tl-lane-head[data-lane="rmsLoudness"]');
  if ((await head.getAttribute("data-lane-collapsed")) !== "true") {
    await page.getByTestId("lane-collapse-rmsLoudness").click();
  }
  await expect(head).toHaveAttribute("data-lane-collapsed", "true");
  await waitReady(page);

  // Exactly one text line in the label column: the title, no sub-caption.
  await expect(head.locator(".tl-lane-head__name")).toHaveText("RMS Loudness");
  await expect(head.locator(".tl-lane-head__sub")).toHaveCount(0);

  // The mini strip still paints: a non-transparent column in every 100px band.
  const strip = await page.evaluate(() => {
    const body = document.querySelector(
      '.tl-lane-body[data-lane="rmsLoudness"] canvas',
    ) as HTMLCanvasElement | null;
    if (!body) return { ok: false, bands: 0 };
    const ctx = body.getContext("2d", { willReadFrequently: true })!;
    const { width: w, height: h } = body;
    const data = ctx.getImageData(0, 0, w, h).data;
    const bandPx = Math.round((100 / body.getBoundingClientRect().width) * w);
    let bands = 0;
    let ok = true;
    for (let x0 = 0; x0 < w; x0 += bandPx) {
      let hit = false;
      for (let x = x0; x < Math.min(x0 + bandPx, w) && !hit; x++)
        for (let y = 0; y < h; y++)
          if (data[(y * w + x) * 4 + 3] !== 0) { hit = true; break; }
      bands++;
      if (!hit) ok = false;
    }
    return { ok, bands };
  });
  expect(strip.bands).toBeGreaterThan(1);
  expect(strip.ok).toBe(true);

  await expect(page.locator(GRID)).toHaveScreenshot("lane-collapsed.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  // Expand → the sub-caption node returns.
  await page.getByTestId("lane-collapse-rmsLoudness").click();
  await expect(head).toHaveAttribute("data-lane-collapsed", "false");
  await expect(head.locator(".tl-lane-head__sub")).toHaveCount(1);

  expect(errors.list()).toEqual([]);
});
