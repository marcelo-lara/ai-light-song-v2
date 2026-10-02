import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, expectHealthy, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.10 item 17 — the "Section Names" lane (experiments/section_names). The lane
// title is "Section Names" (the experiment's name written as a title), and the
// lane shows exactly as many blocks, with exactly the labels, as the fixture's
// `reference/proposals/section_names.json` has rows. Runtime assertions (no
// console error/warning, no pageerror, no failed or removed-artifact request)
// are the same as every spec's (helpers.ts).

const analysisFile = (fixture: string, rel: string) =>
  JSON.parse(fs.readFileSync(path.join(process.cwd(), "fixtures/analysis", fixture, rel), "utf-8"));

for (const [label, fixture] of [
  ["primary fixture", FIXTURES.full],
  ["_test_song", FIXTURES.noAudio],
] as const) {
  test(`item 17 — Section Names lane block count and labels equal the ${label}'s section_names.json rows`, async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page, { allowMissingAudio: fixture === FIXTURES.noAudio });
    await gotoSong(page, fixture);
    await waitReady(page);

    const blocks = analysisFile(fixture, "reference/proposals/section_names.json").blocks as {
      label: string;
    }[];
    expect(blocks.length).toBeGreaterThan(0); // a vacuous count would prove nothing

    const head = page.locator('.tl-lane-head[data-lane="sectionNames"]');
    await expect(head).toHaveCount(1);
    await expect(head.locator(".tl-lane-head__name-text")).toHaveText("Section Names");

    // The events panel lists one card per block of the lane, in order, with its label.
    await page.getByTestId("lane-events-sectionNames").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveAttribute("data-lane", "sectionNames");
    const cards = page.locator('[data-testid^="lane-event-sectionNames-"]');
    await expect(cards).toHaveCount(blocks.length);
    const labels = await cards.locator(".lane-events__label").allTextContents();
    expect(labels).toEqual(blocks.map((b) => b.label));

    await expectHealthy(errors);
  });
}
