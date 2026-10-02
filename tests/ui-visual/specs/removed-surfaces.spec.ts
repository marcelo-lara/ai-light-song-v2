import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import {
  assertNoRuntimeErrors,
  expectHealthy,
  FIXTURES,
  fullExtentOfLane,
  gotoSong,
  waitReady,
} from "../helpers";

// v3.10 item 9 (Cut stages — debugger UI). The analyzer no longer writes
// `genre.json`, the harmonic/energy layers or the section `key`/`energy`/
// `tension`/`rhythm` clue fields (item 8), so the debugger must neither show
// nor edit them:
//   1. no runtime error, and no request for a removed artifact (helpers.ts
//      `assertNoRuntimeErrors` fails on both, for every spec);
//   2. the main timeline has no lane titled or keyed with energy, tension,
//      rhythm, key or seeds, and every remaining canvas lane's content reaches
//      the timeline's right edge (the guide's §5 full-extent check);
//   3. the segment editor, opened on the first Human Section, has no energy,
//      tension or rhythm control;
//   4. saving a section writes start/end/label (and description) and leaves any
//      other key already in reference/human/segments.json as it was. The
//      `RegFull` fixture's first row still carries legacy energy/tension keys
//      for exactly this check.

const SEGMENTS_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/human/segments.json",
);
let backup = "";

test.describe("v3.10 item 9 — removed surfaces", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(() => {
    backup = fs.readFileSync(SEGMENTS_FIXTURE, "utf-8");
  });
  test.afterAll(() => {
    if (backup) fs.writeFileSync(SEGMENTS_FIXTURE, backup);
  });
  test.afterEach(() => {
    if (backup) fs.writeFileSync(SEGMENTS_FIXTURE, backup);
  });

  test("main timeline has no energy / tension / key lane and every canvas lane reaches the right edge", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);

    const heads = page.locator(".tl-lane-head[data-lane]");
    expect(await heads.count()).toBeGreaterThan(5);
    const lanes = await heads.evaluateAll((els) =>
      els.map((el) => ({
        id: (el as HTMLElement).dataset.lane ?? "",
        title: el.querySelector(".tl-lane-head__name-text")?.textContent ?? "",
      })),
    );
    for (const lane of lanes) {
      expect(`${lane.id} ${lane.title}`, `lane ${lane.id}`).not.toMatch(
        /energy|tension|rhythm|\bkey\b|seed/i,
      );
    }

    // the header carries no key tag either
    await expect(page.locator(".app-header__tags")).not.toContainText(/major|minor|key/i);

    // §5 full-extent check on every remaining canvas lane that has data
    for (const id of ["fftBands", "rmsLoudness", "loudnessEnvelope"]) {
      const head = page.locator(`.tl-lane-head[data-lane="${id}"]`);
      await expect(head).toHaveCount(1);
      const ext = await fullExtentOfLane(page, id);
      expect(ext.hasCanvas, `${id} has a canvas`).toBe(true);
      expect(ext.lastNonEmptyX, `${id} reaches the right edge`).toBeGreaterThan(
        ext.contentWidth * 0.95,
      );
    }

    await expectHealthy(errors);
  });

  test("segment editor on the first section has no energy / tension / rhythm control, and a save leaves legacy keys untouched", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);

    await page.getByTestId("lane-events-humanSections").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveAttribute(
      "data-lane",
      "humanSections",
    );
    // the events panel has no rating control, count or Save-ratings footer
    await expect(page.locator(".lane-events__rating")).toHaveCount(0);
    await expect(page.getByTestId("block-energy-save")).toHaveCount(0);

    await page.getByTestId("lane-event-segment-001").dblclick();
    const editor = page.getByTestId("segment-editor");
    await expect(editor).toHaveAttribute("data-segment-id", "segment-001");

    for (const sel of [
      "#segment-energy",
      "#segment-tension",
      '[id^="segment-rhythm"]',
      ".seg-rating",
    ]) {
      await expect(editor.locator(sel), sel).toHaveCount(0);
    }
    // the controls that remain are exactly Start / End / Label / Description
    await expect(editor.locator("label")).toHaveText(["Start", "End", "Label", "Description"]);

    // change the end time and save
    const end = editor.locator("#segment-end");
    await end.fill("61");
    await end.blur();
    await editor.getByRole("button", { name: "Save" }).click();
    // The "Saved" note is transient (the editor's selection-follow effect resets
    // it on the re-seed), so wait on the file itself, not on the note.
    await expect
      .poll(() => JSON.parse(fs.readFileSync(SEGMENTS_FIXTURE, "utf-8"))[0].end)
      .toBe(61);

    const saved = JSON.parse(fs.readFileSync(SEGMENTS_FIXTURE, "utf-8"));
    expect(saved[0]).toEqual({
      start: 40,
      end: 61,
      label: "Build",
      // legacy keys, exactly as they were
      energy: 4,
      tension: 2,
    });
    expect(saved[1]).toEqual({ start: 60, end: 80, label: "Drop" });

    await expectHealthy(errors);
  });
});
