import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

// Plan v3.4 item 7: the Phrase Periodicity experiment lane. Reads
// `reference/proposals/phrase_periodicity.json` (one block per operator hint,
// each carrying a repetition `regime` + `period`), sits below Human Hints,
// carries a flask badge (it is `experiments/` output). The experiment PASSED
// its kill condition.
//
// The frozen fixture (build-fixtures.py `inject_phrase_periodicity`) writes 3
// blocks: through-composed (period null), bar-loop (period 1), half-bar-loop
// (period 0.5).

test("item 7 — Phrase Periodicity lane: badge, order, null-period string", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  // 1. lane head present.
  const head = page.locator('.tl-lane-head[data-lane="phrasePeriodicity"]');
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
      phrase: lanes.indexOf("phrasePeriodicity"),
    };
  });
  expect(order.hints).toBeGreaterThanOrEqual(0);
  expect(order.phrase).toBeGreaterThan(order.hints);

  // 4. events panel opens and its header carries exactly one flask badge.
  await page.getByTestId("lane-events-phrasePeriodicity").click();
  const panel = page.getByTestId("lane-events-panel");
  await expect(panel).toHaveAttribute("data-lane", "phrasePeriodicity");
  expect(
    await page.locator(".app-rightpanel .tl-lane-head__flask").count(),
  ).toBe(1);

  // 5. three blocks; the null-period block prints the honest string, not a
  //    fabricated number; an interior block prints its period.
  await expect(panel.locator('[data-block-id="phrase-periodicity-1"]')).toHaveCount(1);
  await expect(
    panel.locator('[data-block-id="phrase-periodicity-1"]'),
  ).toContainText("no phrase structure detected");
  await expect(
    panel.locator('[data-block-id="phrase-periodicity-1"]'),
  ).not.toContainText("repeat unit");
  await expect(
    panel.locator('[data-block-id="phrase-periodicity-2"]'),
  ).toContainText("repeat unit 1 bar");
  await expect(panel.locator('[data-block-id="phrase-periodicity-3"]')).toHaveCount(1);

  // negative checks (§3).
  expect(errors.list()).toEqual([]);
});
