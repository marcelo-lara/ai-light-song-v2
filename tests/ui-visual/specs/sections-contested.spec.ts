import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, expectHealthy, FIXTURES, gotoSong } from "../helpers";

// Plan v3.4 item 3: the phase-3 energy contest flags (never flips) a `chorus`
// whose energy contradicts the following section. The flag lands on the
// top-level `sections.json` row as `function_status: "contested"` +
// `contested_by: "energy"`. The frozen full fixture (build-fixtures.py
// `inject_section_contest`) marks its first `chorus` contested.
//
// Checks: the contested section's events-panel card tint differs from an
// uncontested section's; the card names `contested` and `energy`; an
// uncontested card does not.

test("item 3 — contested section is visually distinct and labelled in the panel", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  await page.getByTestId("lane-events-sections").click();
  const panel = page.getByTestId("lane-events-panel");
  await expect(panel).toHaveAttribute("data-lane", "sections");

  const contested = panel.locator('[data-block-id="section-005"]');
  const uncontested = panel.locator('[data-block-id="section-002"]');
  await expect(contested).toHaveCount(1);
  await expect(uncontested).toHaveCount(1);

  const contestedBg = await contested.evaluate((el) => getComputedStyle(el).backgroundColor);
  const uncontestedBg = await uncontested.evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(contestedBg).not.toBe(uncontestedBg);

  await expect(contested).toContainText("contested");
  await expect(contested).toContainText("energy");
  await expect(uncontested).not.toContainText("contested");

  await expectHealthy(errors);
});
