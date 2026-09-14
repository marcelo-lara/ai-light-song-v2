import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

// Plan v3.4 item 6: the Texture Novelty experiment lane. Reads
// `reference/proposals/texture_novelty.json` (segments between self-similarity
// novelty boundaries), sits below Human Hints, carries a flask badge (it is
// `experiments/` output). The experiment FAILED its kill condition and the lane
// is kept for one operator review pass.
//
// The frozen fixture (build-fixtures.py `inject_texture_novelty`) writes 3
// blocks / 2 interior boundaries at 8.0 s and 20.0 s.

test("item 6 — Texture Novelty lane: badge, order, blocks", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // 1. lane head present.
  const head = page.locator('.tl-lane-head[data-lane="textureNovelty"]');
  await expect(head).toHaveCount(1);

  // 2. flask badge — it is experiments/ output.
  await expect(head.locator(".tl-lane-head__flask")).toHaveCount(1);

  // 3. sits below the humanHints lane row in DOM order.
  const order = await page.evaluate(() => {
    const lanes = [...document.querySelectorAll(".tl-lane-head[data-lane]")].map(
      (el) => el.getAttribute("data-lane"),
    );
    return {
      hints: lanes.indexOf("humanHints"),
      texture: lanes.indexOf("textureNovelty"),
    };
  });
  expect(order.hints).toBeGreaterThanOrEqual(0);
  expect(order.texture).toBeGreaterThan(order.hints);

  // 4. events panel opens and its header carries exactly one flask badge.
  await page.getByTestId("lane-events-textureNovelty").click();
  const panel = page.getByTestId("lane-events-panel");
  await expect(panel).toHaveAttribute("data-lane", "textureNovelty");
  expect(
    await page.locator(".app-rightpanel .tl-lane-head__flask").count(),
  ).toBe(1);

  // 5. three blocks; the first prints its null left edge honestly, an interior
  //    block prints its novelty strength.
  await expect(panel.locator('[data-block-id="texture-novelty-1"]')).toHaveCount(1);
  await expect(
    panel.locator('[data-block-id="texture-novelty-1"]'),
  ).toContainText("first segment");
  await expect(
    panel.locator('[data-block-id="texture-novelty-2"]'),
  ).toContainText("novelty 0.71");
  await expect(panel.locator('[data-block-id="texture-novelty-3"]')).toHaveCount(1);

  // negative checks (§3).
  expect(errors.list()).toEqual([]);
});
