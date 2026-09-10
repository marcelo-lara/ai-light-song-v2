import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, expectHealthy, FIXTURES, gotoSong } from "../helpers";

// Plan v3.4 item 2: `drums.py` splits a `crash` out of pitch-42 `hat` events.
// The Drum Density lane is canvas-only (no events opener — see lane-events.spec
// `NON_BLOCK_LANES`), so its "legend" is the lane-head sub-caption, which must
// now name `crash`. The frozen full fixture carries 3 `crash` events; the lane
// must render them with no runtime error.

test("item 2 — crash named in the drums lane sub-caption, lane renders clean", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page);
  await gotoSong(page, FIXTURES.full);

  const head = page.locator('.tl-lane-head[data-lane="drums"]');
  await expect(head).toHaveCount(1);

  // The sub-caption ("legend") renders only when the lane is expanded, and the
  // drums lane is collapsed by default.
  if ((await head.getAttribute("data-lane-collapsed")) === "true") {
    await page.getByTestId("lane-collapse-drums").click();
  }
  await expect(head.locator(".tl-lane-head__sub")).toHaveText(
    "kick / snare / hat / crash activity",
  );

  await expectHealthy(errors);
});
