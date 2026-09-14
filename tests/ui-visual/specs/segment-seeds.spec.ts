import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.6 item 4 ("Seeds first" + the segment editor). Per field, the segment
// editor shows the operator's own reference/human/segments.json value where
// present, else the unreviewed reference/human/segments.seed.json value as a
// draft (`data-seed-draft="true"`), reported by `data-segment-editor`
// controls `segment-energy` / `segment-tension` /
// `segment-rhythm-{drums,bass,harmonic,vocals}`. Save persists whatever is
// currently shown (draft or not) into segments.json, going through the real
// `PUT /api/human-sections/<song>` handler — snapshot + restore RegFull's
// segments.json exactly as `promote-hint.spec.ts` does.
const SEGMENTS_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/human/segments.json",
);
let segmentsFixtureBackup = "";

test.describe("v3.6 item 4 — segment seeds + segment editor", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(() => {
    segmentsFixtureBackup = fs.readFileSync(SEGMENTS_FIXTURE, "utf-8");
  });
  test.afterAll(() => {
    if (segmentsFixtureBackup) fs.writeFileSync(SEGMENTS_FIXTURE, segmentsFixtureBackup);
  });
  test.afterEach(() => {
    // Restore even on a hard failure, so a dirty fixture is never stranded.
    if (segmentsFixtureBackup) fs.writeFileSync(SEGMENTS_FIXTURE, segmentsFixtureBackup);
  });

  test("RegFull — per-field fusion: operator value wins, else the seed shows as a draft", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);

    await page.getByTestId("lane-events-humanSections").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);

    // Open the first card (segment-001, the 40-60 "Build" span) in the editor.
    await page.getByTestId("lane-event-segment-001").dblclick();
    const editor = page.getByTestId("segment-editor");
    await expect(editor).toBeVisible();
    await expect(editor).toHaveAttribute("data-segment-start", "40");

    // energy: segments.json already has energy:4 for this span -> wins, not a draft.
    await expect(page.locator("#segment-energy")).toHaveAttribute("data-value", "4");
    await expect(page.locator("#segment-energy")).toHaveAttribute("data-seed-draft", "false");

    // tension: no operator value -> the seed's tension:4 shows as a draft.
    await expect(page.locator("#segment-tension")).toHaveAttribute("data-value", "4");
    await expect(page.locator("#segment-tension")).toHaveAttribute("data-seed-draft", "true");

    // rhythm.drums: seed-only -> draft "sixteenth".
    await expect(page.locator("#segment-rhythm-drums")).toHaveValue("sixteenth");
    await expect(page.locator("#segment-rhythm-drums")).toHaveAttribute("data-seed-draft", "true");

    // rhythm.bass: neither operator nor seed has a value for this span -> unset, not a draft.
    await expect(page.locator("#segment-rhythm-bass")).toHaveValue("");
    await expect(page.locator("#segment-rhythm-bass")).toHaveAttribute("data-seed-draft", "false");

    // rhythm.vocals: seed-only -> draft "none".
    await expect(page.locator("#segment-rhythm-vocals")).toHaveValue("none");
    await expect(page.locator("#segment-rhythm-vocals")).toHaveAttribute("data-seed-draft", "true");

    expect(errors.list()).toEqual([]);
  });

  test("RegFull — Save persists the shown draft, turning it into an operator value", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);

    await page.getByTestId("lane-events-humanSections").click();
    await page.getByTestId("lane-event-segment-001").dblclick();
    const editor = page.getByTestId("segment-editor");
    await expect(editor).toBeVisible();
    await expect(page.locator("#segment-tension")).toHaveAttribute("data-seed-draft", "true");

    const put = page
      .waitForResponse(
        (r) => r.request().method() === "PUT" && r.url().includes("/api/human-sections/"),
        { timeout: 10_000 },
      )
      .catch(() => null);
    await editor.getByRole("button", { name: "Save" }).click();
    await put;
    await waitReady(page);

    // Reload, reopen the same card: the persisted draft is now the operator's own.
    await page.reload();
    await page.waitForSelector('html[data-ui-ready="1"]', { timeout: 20_000 });
    await waitReady(page);

    await page.getByTestId("lane-events-humanSections").click();
    await page.getByTestId("lane-event-segment-001").dblclick();
    const reopened = page.getByTestId("segment-editor");
    await expect(reopened).toBeVisible();
    await expect(page.locator("#segment-tension")).toHaveAttribute("data-value", "4");
    await expect(page.locator("#segment-tension")).toHaveAttribute("data-seed-draft", "false");

    expect(errors.list()).toEqual([]);
  });

  test("RegPartial — no segments.json at all: the lane renders off the seed's own spans", async ({
    page,
  }) => {
    // No assertNoRuntimeErrors here: RegPartial is deliberately missing
    // artifacts/essentia/fft_bands*.json (the degraded-banner fixture, see
    // build-fixtures.py's module docstring) — that 404 is an unrelated,
    // by-design property of this fixture, not something this test (segment
    // editor fusion behaviour) is checking.
    await gotoSong(page, FIXTURES.partial);
    await waitReady(page);

    await page.getByTestId("lane-events-humanSections").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
    await expect(page.locator(".lane-events__card")).toHaveCount(2);

    // Second card (segment-002, the 60-80 "Drop" span): energy is seed-only.
    await page.getByTestId("lane-event-segment-002").dblclick();
    const editor = page.getByTestId("segment-editor");
    await expect(editor).toBeVisible();
    await expect(page.locator("#segment-energy")).toHaveAttribute("data-value", "5");
    await expect(page.locator("#segment-energy")).toHaveAttribute("data-seed-draft", "true");
  });
});
