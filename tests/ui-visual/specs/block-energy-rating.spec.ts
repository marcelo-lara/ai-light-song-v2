import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.4 item 4 (D4.1): the Human Hints events panel gains two 1-5 segmented
// selectors per card — `energy` and `tension` — pre-filled from
// `reference/human/block_energy.json` and persisted by a panel-level Save
// (`PUT /api/block-energy/<song>`, dev-server only). Closing the panel does not
// write.
//
// The Save writes the (writable, under the visual compose) fixture file, so
// snapshot it in `beforeAll` and restore it in `afterAll` / before each test,
// exactly as `promote-hint.spec.ts` does for `human_hints.json`.
const BLOCK_ENERGY_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/human/block_energy.json",
);
let backup = "";

const seg = (hintId: string, axis: "energy" | "tension", n: number) =>
  `block-energy-${hintId}-${axis}-${n}`;

test.describe("v3.4 item 4 — block energy/tension rating surface", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(() => {
    backup = fs.readFileSync(BLOCK_ENERGY_FIXTURE, "utf-8");
  });
  test.afterAll(() => {
    if (backup) fs.writeFileSync(BLOCK_ENERGY_FIXTURE, backup);
  });
  test.afterEach(() => {
    if (backup) fs.writeFileSync(BLOCK_ENERGY_FIXTURE, backup);
  });
  test.beforeEach(async ({ page }) => {
    fs.writeFileSync(BLOCK_ENERGY_FIXTURE, backup);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);
    await page.getByTestId("lane-events-humanHints").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  });

  test("pre-fills, counts, saves an edit, and never writes on close", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);

    // 1. hint-001 is pre-filled from the fixture: energy 5, tension 4.
    await expect(page.getByTestId(seg("hint-001", "energy", 5))).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(
      page.getByTestId(seg("hint-001", "tension", 4)),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId(seg("hint-001", "energy", 3))).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    // 2. hint-002 is explicitly unrated — no segment pressed on either axis,
    //    not a defaulted 1.
    const hint002 = page.locator('[data-testid="block-energy-hint-002"]');
    await expect(
      hint002.locator('.seg-rating__btn[aria-pressed="true"]'),
    ).toHaveCount(0);

    // 3. the header shows the completion count (fixture has 3 hints, 1 rated).
    await expect(page.getByTestId("block-energy-count")).toHaveText(
      "1 / 3 blocks rated",
    );

    // 4. a Save button exists; closing the panel issues no PUT.
    await expect(page.getByTestId("block-energy-save")).toHaveCount(1);
    let puts = 0;
    page.on("request", (r) => {
      if (
        r.method() === "PUT" &&
        r.url().includes("/api/block-energy/")
      ) {
        puts += 1;
      }
    });
    await page.getByRole("button", { name: "Close panel" }).click();
    await expect(page.getByTestId("lane-events-panel")).toHaveCount(0);
    await page.waitForTimeout(200);
    expect(puts).toBe(0);
    expect(fs.readFileSync(BLOCK_ENERGY_FIXTURE, "utf-8")).toBe(backup);

    // 5. reopen, rate energy 3 on hint-002, Save -> exactly one PUT, 200.
    await page.getByTestId("lane-events-humanHints").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
    await page.getByTestId(seg("hint-002", "energy", 3)).click();
    await expect(page.getByTestId(seg("hint-002", "energy", 3))).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    const put = page.waitForResponse(
      (r) =>
        r.request().method() === "PUT" &&
        r.url().includes("/api/block-energy/RegFull%20-%20Fixture"),
      { timeout: 10_000 },
    );
    await page.getByTestId("block-energy-save").click();
    const response = await put;
    expect(response.status()).toBe(200);
    await waitReady(page);

    // 6. the file now carries hint-002's partial rating; hint-001 is unchanged.
    const written = JSON.parse(
      fs.readFileSync(BLOCK_ENERGY_FIXTURE, "utf-8"),
    ) as { ratings: Array<Record<string, unknown>> };
    expect(written.ratings).toEqual([
      { hint_id: "hint-001", energy: 5, tension: 4 },
      { hint_id: "hint-002", energy: 3 },
    ]);

    expect(errors.list()).toEqual([]);
  });

  test("baseline — one rated + one unrated card", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await page.getByRole("button", { name: "To start" }).click();
    await waitReady(page);
    await expect(page.locator(".app-rightpanel")).toHaveScreenshot(
      "block-energy-rating.png",
    );
    expect(errors.list()).toEqual([]);
  });
});
