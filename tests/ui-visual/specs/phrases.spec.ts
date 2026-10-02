import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, expectHealthy, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.10 item 15 — the "Phrases" lane (experiments/phrases). The lane title
// equals the experiment's name, the lane shows exactly as many blocks as the
// fixture's `reference/proposals/phrases.json` has rows, and the last block ends
// within 1 s of the song's end (phrases tile the song). Runtime assertions (no
// console error/warning, no pageerror, no failed or removed-artifact request)
// are the same as every spec's (helpers.ts).

const analysisFile = (fixture: string, rel: string) =>
  JSON.parse(fs.readFileSync(path.join(process.cwd(), "fixtures/analysis", fixture, rel), "utf-8"));

// the lane's own range formatter (ui/src/timeline/laneContent/shared.ts fmtTime)
const fmtTime = (s: number): string => {
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, "0")}`;
};

for (const [label, fixture] of [
  ["primary fixture", FIXTURES.full],
  ["_test_song", FIXTURES.noAudio],
] as const) {
  test(`item 15 — Phrases lane block count equals the ${label}'s phrases.json rows and the last block ends at the song end`, async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page, { allowMissingAudio: fixture === FIXTURES.noAudio });
    await gotoSong(page, fixture);
    await waitReady(page);

    const blocks = analysisFile(fixture, "reference/proposals/phrases.json").blocks as {
      start_s: number;
      end_s: number;
    }[];
    const duration = analysisFile(fixture, "info.json").duration as number;
    expect(blocks.length).toBeGreaterThan(0); // a vacuous count would prove nothing
    expect(Math.abs(blocks[blocks.length - 1]!.end_s - duration)).toBeLessThanOrEqual(1);

    const head = page.locator('.tl-lane-head[data-lane="phrases"]');
    await expect(head).toHaveCount(1);
    await expect(head.locator(".tl-lane-head__name-text")).toHaveText("Phrases");

    // The events panel lists one card per block of the lane.
    await page.getByTestId("lane-events-phrases").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveAttribute("data-lane", "phrases");
    const cards = page.locator('[data-testid^="lane-event-phrases-"]');
    await expect(cards).toHaveCount(blocks.length);
    // ...and the last card's range ends where the song ends.
    await expect(cards.last()).toContainText(`–${fmtTime(blocks[blocks.length - 1]!.end_s)}`);

    await expectHealthy(errors);
  });
}
