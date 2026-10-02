import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, expectHealthy, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.10 item 14 — the "Filter Sweeps" lane (experiments/filter_sweep). The lane
// title equals the experiment's name, and the lane shows exactly as many blocks
// as the fixture's `reference/proposals/filter_sweep.json` has rows. Runtime
// assertions (no console error/warning, no pageerror, no failed or removed-
// artifact request) are the same as every spec's (helpers.ts).

const rowsOf = (fixture: string): number => {
  const file = path.join(
    process.cwd(),
    "fixtures/analysis",
    fixture,
    "reference/proposals/filter_sweep.json",
  );
  return (JSON.parse(fs.readFileSync(file, "utf-8")).blocks as unknown[]).length;
};

for (const [label, fixture] of [
  ["primary fixture", FIXTURES.full],
  ["_test_song", FIXTURES.noAudio],
] as const) {
  test(`item 14 — Filter Sweeps lane block count equals the ${label}'s filter_sweep.json rows`, async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page, { allowMissingAudio: fixture === FIXTURES.noAudio });
    await gotoSong(page, fixture);
    await waitReady(page);

    const expected = rowsOf(fixture);
    expect(expected).toBeGreaterThan(0); // a vacuous count would prove nothing

    const head = page.locator('.tl-lane-head[data-lane="filterSweep"]');
    await expect(head).toHaveCount(1);
    await expect(head.locator(".tl-lane-head__name-text")).toHaveText("Filter Sweeps");

    // The events panel lists one card per block of the lane.
    await page.getByTestId("lane-events-filterSweep").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveAttribute("data-lane", "filterSweep");
    await expect(page.locator('[data-testid^="lane-event-filter-sweep-"]')).toHaveCount(expected);

    await expectHealthy(errors);
  });
}
