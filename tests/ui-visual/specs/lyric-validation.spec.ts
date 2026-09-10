import fs from "node:fs";
import path from "node:path";

import { test, expect } from "@playwright/test";

import { assertNoRuntimeErrors, FIXTURES, gotoSong, waitReady } from "../helpers";

// v3.4 item 5 / D6: each Moises Lyrics word-token card gains a ✔ button. A
// click marks the token human-validated; the lane then shows it at confidence
// `1` with the distinct `moisesLyricsValidated` tint (never the ≥ 0.7 "High"
// bucket). Validation is an overlay — `reference/human/lyric_validations.json`
// (`{ schema_version, song_name, validated_ids: [int] }`) — never an edit to
// `reference/moises/lyrics.json`.
//
// The write is PER-CLICK (no Save button — D5.1). It writes the (writable,
// under the visual compose) fixture file, so snapshot-and-restore it exactly as
// `promote-hint.spec.ts` / `block-energy-rating.spec.ts` do.
const LYRIC_VALIDATIONS_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/human/lyric_validations.json",
);
const MOISES_FIXTURE = path.join(
  process.cwd(),
  "fixtures/analysis/RegFull - Fixture/reference/moises/lyrics.json",
);
let backup = "";
let moisesBackup = "";

const bg = (el: Element) => getComputedStyle(el).backgroundColor;

test.describe("v3.4 item 5 — lyric-token human-validation overlay", () => {
  test.describe.configure({ mode: "serial" });

  test.beforeAll(() => {
    backup = fs.readFileSync(LYRIC_VALIDATIONS_FIXTURE, "utf-8");
    moisesBackup = fs.readFileSync(MOISES_FIXTURE, "utf-8");
  });
  test.afterAll(() => {
    if (backup) fs.writeFileSync(LYRIC_VALIDATIONS_FIXTURE, backup);
  });
  test.afterEach(() => {
    if (backup) fs.writeFileSync(LYRIC_VALIDATIONS_FIXTURE, backup);
    // the source Moises file must never be touched by any of this.
    expect(fs.readFileSync(MOISES_FIXTURE, "utf-8")).toBe(moisesBackup);
  });
  test.beforeEach(async ({ page }) => {
    fs.writeFileSync(LYRIC_VALIDATIONS_FIXTURE, backup);
    await gotoSong(page, FIXTURES.full);
    await waitReady(page);
    await page.getByTestId("lane-events-moisesLyrics").click();
    await expect(page.getByTestId("lane-events-panel")).toHaveCount(1);
  });

  test("tints validated tokens distinctly, toggles per-click, never seeks", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);

    // 1. the fixture pre-validates ids 2 and 3; their card tint differs from
    //    both a < 0.7 token (id 4) and a >= 0.7 token (id 3 would be High).
    const validated = await page
      .locator('.lane-events__card[data-block-id="2"]')
      .evaluate(bg);
    const low = await page
      .locator('.lane-events__card[data-block-id="4"]')
      .evaluate(bg);
    expect(validated).not.toBe(low);
    // id 3's raw Moises confidence is >= 0.7, so without the overlay it would be
    // the green "High" tint; with it, it matches id 2's validated tint.
    const validated3 = await page
      .locator('.lane-events__card[data-block-id="3"]')
      .evaluate(bg);
    expect(validated3).toBe(validated);

    // 2. every word-token card has exactly one ✔; the <SOL> marker (id 1) none.
    await expect(
      page.locator('.lane-events__card[data-block-id="1"] .lane-events__validate'),
    ).toHaveCount(0);
    await expect(
      page.locator('.lane-events__card[data-block-id="2"] .lane-events__validate'),
    ).toHaveCount(1);

    // 3. clicking an unvalidated token's ✔ issues exactly one PUT (200) and
    //    does NOT move the playhead.
    const clockBefore = await page.locator(".app-header__time").textContent();
    let puts = 0;
    page.on("request", (r) => {
      if (r.method() === "PUT" && r.url().includes("/api/lyric-validations/")) {
        puts += 1;
      }
    });
    const put = page.waitForResponse(
      (r) =>
        r.request().method() === "PUT" &&
        r.url().includes("/api/lyric-validations/RegFull%20-%20Fixture"),
      { timeout: 10_000 },
    );
    await page.getByTestId("lyric-validate-4").click();
    expect((await put).status()).toBe(200);
    await waitReady(page);
    expect(await page.locator(".app-header__time").textContent()).toBe(clockBefore);
    expect(puts).toBe(1);

    // 4. the file now carries id 4; the source Moises file is untouched.
    const afterAdd = JSON.parse(
      fs.readFileSync(LYRIC_VALIDATIONS_FIXTURE, "utf-8"),
    ) as { validated_ids: number[] };
    expect(afterAdd.validated_ids).toEqual([2, 3, 4]);

    // 5. clicking a validated token's ✔ again writes a body that omits that id.
    const put2 = page.waitForResponse(
      (r) =>
        r.request().method() === "PUT" &&
        r.url().includes("/api/lyric-validations/"),
      { timeout: 10_000 },
    );
    await page.getByTestId("lyric-validate-2").click();
    await put2;
    await waitReady(page);
    const afterRemove = JSON.parse(
      fs.readFileSync(LYRIC_VALIDATIONS_FIXTURE, "utf-8"),
    ) as { validated_ids: number[] };
    expect(afterRemove.validated_ids).not.toContain(2);
    expect(afterRemove.validated_ids).toEqual([3, 4]);

    expect(errors.list()).toEqual([]);
  });

  test("the validated tint reaches the timeline lane, not just the panel", async ({
    page,
  }) => {
    const errors = assertNoRuntimeErrors(page);
    // The moisesLyrics lane is expanded by default. Sample its canvas for the
    // validated tint's hue (hsl ~265 -> a blue-violet: B channel clearly the
    // largest, R and G lower), which none of the green/amber/red Moises
    // confidence tints produce.
    const hasViolet = await page.evaluate(() => {
      const container = document.querySelector(
        '.tl-lane-body[data-lane="moisesLyrics"] .tl-canvas-lane',
      ) as HTMLElement | null;
      const canvas = container?.querySelector("canvas");
      if (!canvas) return false;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) return false;
      const { width: w, height: h } = canvas;
      const d = ctx.getImageData(0, 0, w, h).data;
      for (let i = 0; i < d.length; i += 4) {
        const [r, g, b, a] = [d[i], d[i + 1], d[i + 2], d[i + 3]];
        if (a !== 0 && b > r + 12 && b > g + 12 && r > 20) return true;
      }
      return false;
    });
    expect(hasViolet).toBe(true);
    expect(errors.list()).toEqual([]);
  });

  test("baseline — panel with validated + unvalidated tokens", async ({ page }) => {
    const errors = assertNoRuntimeErrors(page);
    await page.getByRole("button", { name: "To start" }).click();
    await waitReady(page);
    await expect(page.locator(".app-rightpanel")).toHaveScreenshot(
      "lyric-validation-panel.png",
    );
    expect(errors.list()).toEqual([]);
  });
});
