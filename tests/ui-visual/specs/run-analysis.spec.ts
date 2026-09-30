import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong } from "../helpers";

// v3.8 item 2 — Debugger analysis trigger. `RunAnalysisControl` (App.tsx
// `.app-header__right`) polls `artifacts/_run_progress.json`; no run has been
// requested for a fixture song, so that file does not exist and the resulting
// 404 is the expected idle state (`OPTIONAL_RUN_PROGRESS_404` in helpers.ts).
//
// This spec writes a transient `_run_progress.json` fixture for the
// running-status case, then deletes it (mirrors `block-energy-rating.spec.ts`'s
// snapshot/restore pattern for a mutated fixture file — here the file starts
// absent, so "restore" is "remove").
const RUN_PROGRESS_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis",
  FIXTURES.full,
  "artifacts/_run_progress.json",
);

function removeRunProgressFixture(): void {
  if (fs.existsSync(RUN_PROGRESS_FIXTURE)) fs.unlinkSync(RUN_PROGRESS_FIXTURE);
}

test.describe("v3.8 item 2 — Run analysis header control", () => {
  test.beforeEach(() => {
    removeRunProgressFixture();
  });
  test.afterEach(() => {
    removeRunProgressFixture();
  });

  test("no _run_progress.json: button enabled, no status, only the progress 404 fails", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);

    await expect(page.getByTestId("run-analysis-control")).toHaveCount(1);
    await expect(page.getByTestId("run-analysis-button")).toBeEnabled();
    await expect(page.getByTestId("run-analysis-button")).toHaveText("Run analysis");
    await expect(page.getByTestId("run-analysis-status")).toHaveCount(0);

    expect(errors.list()).toEqual([]);
  });

  test("running progress file: status text and disabled button", async ({ page }) => {
    fs.writeFileSync(
      RUN_PROGRESS_FIXTURE,
      JSON.stringify({
        song: FIXTURES.full,
        status: "running",
        stage: "segment-sections",
        requested_at: "2026-01-01T00:00:00Z",
        started_at: "2026-01-01T00:00:01Z",
        finished_at: null,
        error: null,
      }),
    );

    const errors = assertNoRuntimeErrors(page);
    await gotoSong(page, FIXTURES.full);

    await expect(page.getByTestId("run-analysis-status")).toHaveText(
      "running · segment-sections",
    );
    await expect(page.getByTestId("run-analysis-button")).toBeDisabled();

    expect(errors.list()).toEqual([]);
  });
});
