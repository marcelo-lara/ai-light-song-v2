import { defineConfig, devices } from "@playwright/test";

// Deterministic visual regression over the running `ui` container. Baselines are
// OS/arch-specific and MUST be generated/verified inside the pinned Playwright
// container image (see ../../docs/web-ui/ui-regression_guide.md §7).
export default defineConfig({
  testDir: "./specs",
  snapshotDir: "./__screenshots__",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
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
