import { defineConfig, devices } from "@playwright/test";

// Deterministic visual regression over the running `ui` container. Baselines are
// OS/arch-specific and MUST be generated/verified inside the pinned Playwright
// container image (see ../../docs/reference/ui-regression.md §7).
export default defineConfig({
  testDir: "./specs",
  snapshotDir: "./__screenshots__",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Single worker, unconditionally: `hint-drag.spec.ts`, `captured-from.spec.ts`
  // and `promote-hint.spec.ts` all mutate the one writable fixture file
  // (`RegFull - Fixture/reference/human/human_hints.json`) through the real
  // `PUT /api/human-hints`. On separate workers they race on that file and leave
  // it dirty. The suite is ~30 tests / ~15s — determinism outranks the seconds.
  // (plan v1.5 D15.)
  workers: 1,
  reporter: [["html", { outputFolder: "report", open: "never" }], ["list"]],
  use: {
    baseURL: process.env.UI_BASE_URL ?? "http://localhost:9090",
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
    trace: "on-first-retry",
  },
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
      animations: "disabled",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
