# UI Visual Regression Guide

Handoff plan for a repeatable visual regression suite over the internal Artifact
Debugger UI (`ui/`). This is an engineering/QA runbook: it defines what to capture,
how to capture it deterministically, how to review diffs, and how to wire it into
CI.

- Owner: UI + QA
- Applies to: `ui/` (Compose `ui` service), not the analyzer or any production UI
- Related: `ui/README.HELPER_UI.md` (architecture, validation checklist),
  `ui-issues.md` (current known issues), `../docker_development.md`

---

## 1. Goals and non-goals

### Goals

- Catch unintended visual changes to the debugger: layout, lane rendering, panels,
  overlays, empty/partial states.
- Catch runtime regressions that are invisible in a static screenshot: console
  errors/warnings, failed network loads for expected artifacts, unhandled promise
  rejections.
- Give a reviewer a single artifact (an HTML report with side-by-side image diffs)
  per run.
- Run locally with one command and in CI on every PR that touches `ui/`.

### Non-goals

- Pixel-perfect font rendering parity across machines. Always compare against
  baselines captured in the **same container image** (see §4).
- Testing the analyzer, `data/analysis/` contents, or production consumer UI.
- Functional coverage of the human-hint save flow beyond "the editor opens and
  renders". Write flows belong in a separate integration test.

---

## 2. Test surfaces (what to capture)

Each surface is one screenshot target. Capture full-page unless noted.

| ID | Surface | Route / action | Notes |
|----|---------|----------------|-------|
| `home-empty` | First paint, no song selected | `/` with discovery stubbed to return no songs | Verifies the empty discovery state |
| `home-loaded` | Default song auto-loaded | `/` (discovery returns fixtures, first song auto-loads) | Sidebar collapsed by default |
| `song-full` | Fully-populated song | `/?song=<full-fixture>` | All lanes present; primary baseline |
| `song-partial` | Song missing core artifacts | `/?song=<partial-fixture>` | Core-artifact warning card visible |
| `song-no-audio` | Song with no MP3 | `/?song=_test_song` | Waveform beat-pulse fallback, transport disabled (expected) |
| `timeline-zoomed-in` | `song-full` after zoom-in to max | click zoom-in control N times | Dense-lane semantic zoom |
| `timeline-zoomed-out` | `song-full` at min zoom | click zoom-out control N times | Whole-song overview |
| `timeline-scrolled` | `song-full` scrolled to ~50% | set viewport scrollLeft | Marker + ruler alignment mid-song |
| `sidebar-expanded` | `song-full` with sidebar open | click sidebar toggle | Path panel, file-status list, lane toggles |
| `lane-toggles-min` | `song-full` with only waveform + sections visible | toggle lanes off | Lane show/hide layout reflow |
| `overlay-open` | Hovercard/selection overlay | click a sections-lane region | Overlay anchor + content |
| `detail-inspector` | Raw JSON inspector | select an artifact in the inspector dropdown | Scroll region, formatting |
| `human-hints-editor` | Right-side hint editor open | trigger "add hint" | Editor stays open; compact styling |
| `validation-snapshot` | Validation panel populated | part of `song-full` (assert region) | Status, beat match ratio, comparison counts |

Component-level (optional, faster feedback): capture individual panels
(`HeroPanel`, `ArtifactSummaryPanel`, `SectionsPreviewPanel`,
`ValidationSnapshotPanel`, `AudioAnchorPanel`) rendered in isolation if a
component harness is added later. Not required for v1.

---

## 3. Fixtures

Determinism depends on fixed input data. Do **not** point the suite at the live
`data/analysis/` tree — it changes as the analyzer runs.

### 3.1 Fixture set

Create `ui/test/fixtures/analysis/` containing 3 frozen song folders:

- `RegFull - Fixture/` — every artifact the debugger loads
  (`ui/src/lib/config/artifactDefinitions.js` is the authoritative list), including
  `reference/human/human_hints.json` and a `beatdrop_visual_plan.json`.
- `RegPartial - Fixture/` — missing at least one core key from the gate
  (`harmonic`, `symbolic`, `energy`, `sectionsArtifact`, `eventMachine`,
  `validation`) so the warning card renders.
- `_test_song/` — copy of the current synthetic fixture (no audio).

Keep each JSON small (a handful of beats/sections/events) but schema-valid. Trim
large dense-lane arrays (FFT bands, RMS) to ~30–60 frames — enough to exercise
aggregation, small enough to stay stable and fast.

### 3.2 Wiring fixtures into the app

Two options; pick one and document it in `ui/README.HELPER_UI.md`:

- **Static mount (preferred, closest to prod):** run the `ui` container with the
  fixture dir bind-mounted over the data root, e.g.
  `-v $(pwd)/ui/test/fixtures/analysis:/usr/share/nginx/html/data/analysis:ro` and a
  matching `data/songs` dir (may be empty). Discovery still exercises the real
  Nginx autoindex + `fetchDirectoryListing` path.
- **Route interception:** in the Playwright config, `page.route('**/data/**', ...)`
  to serve fixture files from disk and synthesize the autoindex HTML for
  directory requests. Faster to set up, but bypasses the real discovery HTML
  parser — add one non-intercepted smoke test to keep that path covered.

### 3.3 Fixture stability rules

- Any change to a fixture file is a deliberate act and must land in the same PR as
  the baseline re-capture.
- Never let a fixture reference wall-clock time, random IDs, or absolute host
  paths in a field the UI renders.

---

## 4. Determinism checklist

Visual diffs are only meaningful if everything except the code under test is fixed.

- **Same renderer:** capture baselines and comparisons with the **same browser
  build**. Use the Playwright-bundled Chromium and pin
  `@playwright/test` to an exact version. Baselines are OS/arch-specific — commit
  them under a platform-suffixed dir (Playwright does this automatically:
  `*-chromium-linux.png`) and generate/verify them inside the CI container image
  so local Linux and CI match. Mac/Windows contributors compare against Linux
  baselines via `docker compose run`.
- **Fixed viewport:** `1280x720`, `deviceScaleFactor: 1`. One extra wide run at
  `1680x1050` only for `sidebar-expanded` if label truncation (issue #4) is being
  tracked.
- **Disable animation/caret:** Playwright `toHaveScreenshot` uses
  `animations: 'disabled'` and `caretHidden` by default — keep them. Add a global
  stylesheet injection that sets `*, *::before, *::after { transition: none !important;
  animation: none !important; }` for belt-and-braces.
- **Fonts:** rely only on fonts baked into the container image. Do not load web
  fonts. Add a `page.waitForFunction(() => document.fonts.ready)` gate before
  capture.
- **Freeze time and randomness:** inject an init script that pins `Date.now`/`new
  Date()` to a constant and stubs `Math.random`. Needed because the playhead clock
  and any generated IDs must not drift.
- **Audio:** never rely on real decoding. For `song-no-audio` the fallback is the
  target. For songs that do have audio, stub `HTMLMediaElement` play/duration or
  accept the beat-pulse fallback as the baseline and mask the waveform region.
- **Wait for "ready", not a timeout:** define an explicit readiness signal
  (§5.2) and await it. No bare `waitForTimeout`.
- **Mask known-volatile regions:** use the `mask:` option of `toHaveScreenshot`
  for the waveform canvas and the "Visible mm:ss–mm:ss" viewport readout if it
  proves flaky.
- **Threshold:** start at `maxDiffPixelRatio: 0.01`, `threshold: 0.2`. Tighten
  once stable. Never set it so loose that a lane disappearing passes.

---

## 5. Tooling

### 5.1 Stack

- **Playwright Test** (`@playwright/test`) as runner + assertion + screenshot +
  HTML reporter. It has visual comparison (`toHaveScreenshot`), auto-waiting
  selectors, tracing, and a review UI built in — no separate image-diff service
  needed for v1.
- Target the running `ui` container over HTTP (`baseURL:
  http://localhost:9090`). Do not import app modules directly; test the built,
  served bundle.
- Keep the suite in `ui/test/visual/`. Add `@playwright/test` to `ui/package.json`
  `devDependencies` and a `ui/playwright.config.js`.

### 5.2 App readiness signal

Add a small, test-only readiness marker to the app so tests wait on state, not
guesses. Cheapest option: after `loadSong` finishes and the timeline is drawn, set
`document.documentElement.dataset.uiReady = "1"` (and clear it at the start of
`loadSong`). Tests do
`await page.waitForSelector('html[data-ui-ready="1"]')`.

Also assert, on every test:

- no `console.error` / `console.warning` (fail the test on any — this is how
  issue #1 would have been caught automatically);
- no `pageerror` (unhandled exceptions);
- no failed responses for URLs under `/data/analysis/` (a `404`/`ERR` for an
  expected artifact is a regression). `/data/songs/*.mp3` `404`s are allowed only
  for `song-no-audio`.

### 5.3 Config sketch

```js
// ui/playwright.config.js
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./test/visual",
  snapshotDir: "./test/visual/__screenshots__",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["html", { outputFolder: "test/visual/report", open: "never" }]],
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
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
```

### 5.4 Test sketch

```js
// ui/test/visual/song-full.spec.js
import { test, expect } from "@playwright/test";
import { gotoSong, assertNoRuntimeErrors } from "./helpers.js";

test("song-full timeline", async ({ page }) => {
  const errors = assertNoRuntimeErrors(page); // collects console.error / pageerror / bad /data responses
  await gotoSong(page, "RegFull - Fixture");   // navigates, waits for html[data-ui-ready="1"], document.fonts.ready
  await expect(page).toHaveScreenshot("song-full.png", {
    fullPage: true,
    mask: [page.locator("[data-lane='waveform'] canvas")],
  });
  expect(errors.list()).toEqual([]);
});
```

### 5.5 Selectors to add to the app

E2E stability (issue #3) needs stable hooks. Add `data-testid` to:

- sidebar: `sidebar-toggle`, `song-select`, `song-refresh`, `paths-panel`,
  `file-status-list`, and each `lane-toggle-<laneId>`;
- transport header: `transport-play`, `transport-pause`, `zoom-in`, `zoom-out`,
  `follow-playhead`, `song-menu`;
- timeline: `timeline-viewport`, and `data-lane="<laneId>"` on each lane row;
- overlay: `selection-overlay`;
- hint editor: `human-hints-sidebar`, `hint-save`, `hint-cancel`, `hint-delete`,
  `hint-set-start`, `hint-set-end`.

Prefer `getByRole`/`getByLabel` where the control already has an accessible name;
use `data-testid` only where it does not.

---

## 6. Local workflow

Prereqs: Docker, and `npm install` inside `ui/` (or run Playwright via its Docker
image — see §7).

```bash
# 1. build + start the UI against the fixture data
docker compose up -d --build ui
#    (with the fixture mount from §3.2; add a compose override file
#     docker-compose.visual.yml and use `-f docker-compose.yml -f docker-compose.visual.yml`)

# 2. sanity check
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9090/
curl -s http://localhost:9090/data/analysis/ | head

# 3. run the suite
cd ui
npx playwright test               # compare against committed baselines
npx playwright show-report test/visual/report

# 4. when a change is intentional, re-capture and review the diff before committing
npx playwright test --update-snapshots
git add test/visual/__screenshots__
```

Review rule: a baseline update PR must include the Playwright HTML report (or the
before/after PNGs) and a one-line justification per changed snapshot.

---

## 7. CI integration

Trigger: any PR touching `ui/**` or `ui/test/fixtures/**`.

Steps:

1. `docker compose -f docker-compose.yml -f docker-compose.visual.yml up -d --build ui`
2. Wait for `http://localhost:9090/` to return `200` (poll, ~30s timeout).
3. Run Playwright **inside the pinned Playwright container** so the Chromium build
   matches local Linux runs:
   `docker run --rm --network host -v "$PWD/ui:/work" -w /work
   mcr.microsoft.com/playwright:v<pinned> npx playwright test`
4. On failure: upload `ui/test/visual/report/` and `ui/test/visual/**/*-diff.png`
   as build artifacts; fail the job.
5. On success: no artifacts needed.

Do not auto-update baselines in CI. Baseline changes are always a reviewed commit.

Keep the job under ~3 minutes: ~14 screenshots + error assertions, fully parallel,
should be well under that.

---

## 8. Triage guide for a failing run

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Every snapshot differs slightly, uniform | Font/renderer mismatch, wrong container image | Re-capture baselines in the CI container; verify Playwright version pin |
| One lane region differs | Real lane rendering change | Inspect diff; if intended, update baseline with justification |
| Snapshot differs only in waveform area | Decode fallback nondeterminism | Add/extend `mask:` for the waveform canvas |
| Test fails on `console.error` with no visual diff | Runtime regression (e.g. issue #1 class) | Fix the code; do not mask the assertion |
| `/data/analysis/.../*.json` returned 404 | Fixture missing a file the app now loads, or `artifactDefinitions` changed | Update the fixture set in the same PR |
| Flaky pass/fail on `timeline-scrolled` | Capture ran before layout settled | Strengthen the readiness signal; assert scrollLeft applied before capture |
| Playhead position varies | Time not frozen | Verify the `Date`/`Math.random` init script is injected |

---

## 9. Open items before this suite is "done"

- [ ] Add the `data-ui-ready` readiness marker to the app (§5.2).
- [ ] Add `data-testid`s listed in §5.5.
- [ ] Build the three fixture folders (§3.1) and the compose override for mounting
      them (§3.2).
- [ ] Add `@playwright/test` + `playwright.config.js` + `test/visual/` to `ui/`.
- [ ] Capture initial baselines in the CI container image and commit them.
- [ ] Add the CI job (§7).
- [ ] Decide the `_test_song` audio question with Ops (see `ui-issues.md` §2).
- [ ] Fold the "smoke check" list from `ui/README.HELPER_UI.md` into explicit
      assertions so the README checklist and the suite cannot drift apart.
