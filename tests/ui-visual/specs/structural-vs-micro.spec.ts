import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

// Plan v3.4 item 8: the Structural vs Micro experiment lane. Reads
// `reference/proposals/structural_vs_micro.json` (one block per operator hint,
// each carrying `kind` "structural" | "micro" by 4-bar phrase-grid fit, plus
// `grid_fit_bars`), sits below Human Hints, carries a flask badge (it is
// `experiments/` output). The experiment FAILED its kill condition — the lane is
// kept for one operator review pass.
//
// The frozen fixture (build-fixtures.py `inject_structural_vs_micro`) writes 2
// blocks: one structural (grid_fit_bars 0.04), one micro (grid_fit_bars 1.12).

test("item 8 — Structural vs Micro lane: badge, order, kind + grid_fit_bars, per-block tint", async ({
  page,
}) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // 1. lane head present.
  const head = page.locator('.tl-lane-head[data-lane="structuralVsMicro"]');
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
      svm: lanes.indexOf("structuralVsMicro"),
    };
  });
  expect(order.hints).toBeGreaterThanOrEqual(0);
  expect(order.svm).toBeGreaterThan(order.hints);

  // 4. events panel opens and its header carries exactly one flask badge.
  await page.getByTestId("lane-events-structuralVsMicro").click();
  const panel = page.getByTestId("lane-events-panel");
  await expect(panel).toHaveAttribute("data-lane", "structuralVsMicro");
  expect(
    await page.locator(".app-rightpanel .tl-lane-head__flask").count(),
  ).toBe(1);

  // 5. each card prints its kind and grid_fit_bars, not a fabricated value.
  const structural = panel.locator('[data-block-id="structural-vs-micro-1"]');
  const micro = panel.locator('[data-block-id="structural-vs-micro-2"]');
  await expect(structural).toHaveCount(1);
  await expect(structural).toContainText("structural");
  await expect(structural).toContainText("grid fit 0.04 bars");
  await expect(micro).toContainText("micro");
  await expect(micro).toContainText("grid fit 1.12 bars");

  // 6. per-block tint: the micro card's background-color differs from the
  //    structural card's (structuralVsMicroMicro override).
  const bg = (loc: typeof structural) =>
    loc.evaluate((el) => getComputedStyle(el as HTMLElement).backgroundColor);
  expect(await bg(structural)).not.toBe(await bg(micro));

  // negative checks (§3).
  expect(errors.list()).toEqual([]);
});
