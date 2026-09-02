import { test, expect } from "@playwright/test";
import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

const GRID = ".app-timeline__grid";

// Item 4 (R2): the left panel mounts collapsed by default, the burger toggles
// it, esc closes it, and the open/closed state persists across a reload.

test("item 4 — left panel collapsed by default, toggle, esc, persistence", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // On a fresh load the drawer is absent / collapsed and the timeline starts at
  // the label column's right edge.
  const panel = page.getByTestId("left-panel");
  if ((await panel.count()) > 0) {
    await expect(panel).toHaveAttribute("data-open", "false");
  }
  const viewport = page.getByTestId("timeline-viewport");
  const vpBox1 = await viewport.boundingBox();
  // Collapsed: the timeline fills the width from the main area's left edge.
  expect(vpBox1!.x).toBeLessThanOrEqual(2);
  // (the collapsed-panel full-song baseline is `song-full.png` in song-full.spec.ts)

  // Burger opens it; the timeline reflows right (not covered).
  await page.getByTestId("burger-toggle").click();
  await waitReady(page);
  await expect(page.getByTestId("left-panel")).toHaveAttribute("data-open", "true");
  const drawerBox = await page.getByTestId("left-panel").boundingBox();
  expect(drawerBox!.width).toBeGreaterThan(0);
  const vpBox2 = await viewport.boundingBox();
  expect(vpBox2!.x).toBeGreaterThan(vpBox1!.x + drawerBox!.width - 4);

  await expect(page.locator(GRID)).toHaveScreenshot("left-panel-open.png", {
    mask: [page.locator('.tl-lane-body[data-lane="waveform"]')],
  });

  // esc closes it.
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("left-panel")).toHaveCount(0);

  // Persistence: leave it open, reload, it comes back open.
  await page.getByTestId("burger-toggle").click();
  await expect(page.getByTestId("left-panel")).toHaveAttribute("data-open", "true");
  await page.reload();
  await waitReady(page);
  await expect(page.getByTestId("left-panel")).toHaveAttribute("data-open", "true");

  expect(errors.list()).toEqual([]);
});
