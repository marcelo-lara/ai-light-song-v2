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
| `sidebar-expanded` | `song-full` with sidebar open | click sidebar toggle | Path panel, file-status list, lane toggles. Dismissal (plan v1.5 item 2 / R4, R5): a `mousedown` anywhere outside the drawer and the burger closes it; an inside click never does; picking a song in the song picker closes it too. |
| `lane-toggles-min` | `song-full` with only waveform + sections visible | toggle lanes off | Lane show/hide layout reflow |
| `lane-events-panel` | `song-full` with the Human Hints lane's events panel open | click `lane-events-humanHints` | Stacked cards, no inter-card gap; non-modal (survives Play, timeline drag, scroll); `.app-rightpanel` |
| `lane-events-active` | `song-full` lane-events panel with the playhead inside a card | open `lane-events-humanHints`, click the `hint-003` card | Active card carries `data-active="true"` / `aria-current`: raised tint, accent left border, bright label; `.app-rightpanel` |
| `overlay-open` | Hovercard/selection overlay | click a sections-lane region | Overlay anchor + content |
| `detail-inspector` | Raw JSON inspector | select an artifact in the inspector dropdown | Scroll region, formatting |
| `human-hints-editor` | Right-side hint editor open | trigger "add hint" | Editor stays open; compact styling |
| `hint-drag-resized` | `song-full` after a right-edge resize + interior move of two `humanHints` blocks | drag handles on the `humanHints` lane (plan v2.1 item 10) | Blocks at post-drag positions, pre-reload; `.app-timeline__grid`, waveform masked |
| `validation-snapshot` | Validation panel populated | part of `song-full` (assert region) | Status, beat match ratio, comparison counts |
| `header-readout` | `.app-header` with the playhead at `1:04.0` | `/?song=<full-fixture>`, click `hint-003` on the `humanHints` lane | Plan v1.5 item 5 / R9, R10: no `app-header__barbeat-caption`; time / total / bar.beat readouts have reserved widths so nothing shifts as the digit count grows; `.app-header` |
| `footer-follow` | `.app-footer` with the follow toggle off, transport paused | `/?song=<full-fixture>`, clear `localStorage`, click `follow-toggle` once | Plan v1.5 item 6 / R6: the `arrows-in-line-horizontal` follow toggle sits immediately left of the `Lanes` button; `aria-pressed` and the pressed styling track the flag (default on, persisted per session); `.app-footer` |

Component-level (optional, faster feedback): capture individual panels
(`HeroPanel`, `ArtifactSummaryPanel`, `SectionsPreviewPanel`,
`ValidationSnapshotPanel`, `AudioAnchorPanel`) rendered in isolation if a
component harness is added later. Not required for v1.

---

## 3. Fixtures

Determinism depends on fixed input data. Do **not** point the suite at the live
`data/analysis/` tree — it changes as the analyzer runs.

### 3.1 Fixture set

Create `tests/ui-visual/fixtures/analysis/` containing 3 frozen song folders:

- `RegFull - Fixture/` — every artifact the debugger loads
  (`ui/src/lib/config/artifactDefinitions.js` is the authoritative list), including
  `reference/human/human_hints.json`.
  - **`human_hints.json` frozen blocks (plan v2.1 item 10 drag targets).** Three
    non-overlapping blocks with an 4 s gap between each, well inside the 194.01 s
    duration:

    | id | `start_time` | `end_time` |
    |----|-------------:|-----------:|
    | `hint-001` | 40.0 | 48.0 |
    | `hint-002` | 52.0 | 60.0 |
    | `hint-003` | 64.0 | 72.0 |

    (The pre-item-10 file had 5 hints clustered 44–60 s, some adjacent and one
    degenerate — `hint-004` had `start == end`. `hint-004`/`hint-005` were
    dropped so the drag QA has deterministic, clearly-separated edges.)
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
  `-v $(pwd)/tests/ui-visual/fixtures/analysis:/usr/share/nginx/html/data/analysis:ro` and a
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
- Keep the suite in `tests/ui-visual/` — a standalone Playwright project
  (`tests/ui-visual/package.json` with `@playwright/test` pinned exact, plus
  `tests/ui-visual/playwright.config.ts`). It is NOT part of `ui/`'s npm project.

### 5.2 App readiness signal

A test-only readiness marker lives in `ui/src/App.tsx` (added by plan item 1):

- `document.documentElement.dataset.uiReady` is `"0"` during any song load or
  full re-layout (song change, `pxPerBar` / viewport-width change) and flips to
  `"1"` two animation frames after a fully-settled song's visible lanes have had
  a chance to draw. A song is "settled" when `selectSongLoadState` is `ready` or
  `degraded` (not `loading` / `fatal`) and no requested artifact is still
  in-flight.
- `document.documentElement.dataset.uiLoading` carries the in-flight artifact
  count (debugging aid).

Tests wait with `await page.waitForSelector('html[data-ui-ready="1"]')`
(`gotoSong` / `waitReady` in `helpers.ts`). The app also honours a `?song=<name>`
deep link, which is how `gotoSong` selects a song.

Also assert, on every test:

- no `console.error` / `console.warning` (fail the test on any — this is how
  issue #1 would have been caught automatically);
- no `pageerror` (unhandled exceptions);
- no failed responses for URLs under `/data/analysis/` (a `404`/`ERR` for an
  expected artifact is a regression). `/data/songs/*.mp3` `404`s are allowed only
  for `song-no-audio`.

### 5.3 Config sketch

```js
// tests/ui-visual/playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./specs",
  snapshotDir: "./__screenshots__",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
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
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
```

### 5.4 Test sketch

```js
// tests/ui-visual/specs/song-full.spec.ts
import { test, expect } from "@playwright/test";
import { gotoSong, assertNoRuntimeErrors } from "../helpers";

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

E2E stability (issue #3) needs stable hooks. Added in plan item 1 (`ui/src/`):

- header: `burger-toggle` (the menu button);
- left drawer / panel: `left-panel` on `<nav.app-drawer>`, with `data-open`
  `"true" | "false"`;
- footer zoom controls: `zoom-in`, `zoom-out`, `fit-to-width`;
- lane list (`LaneList.tsx`): `lane-list` on the panel, `lane-list-hide-all` on
  the hide-all button;
- timeline: `timeline-viewport` on the scroller; on every lane row (both the
  label cell and the body cell) `data-lane="<laneId>"` and
  `data-lane-collapsed="true" | "false"`; `lane-collapse-<laneId>` on the caret.
- `humanHints` lane body (plan v2.1 item 10): `data-hint-drag-ready="1"` once the
  block drag hit-zones are registered (the executor waits on this, no timeout).
- hint editor (plan v2.1 item 10): `hint-editor` on the editor panel root, with
  `data-hint-id="<id>"` for the hint currently loaded.
- lane events panel (plan v1.5 item 3): `lane-events-<laneId>` on the
  `columns-plus-right` opener in every block lane's head (`aria-pressed`
  tracks the open panel); `lane-events-panel` on the stacked `<ol>` (with
  `data-lane="<laneId>"`); `lane-event-<blockId>` on each card.
- footer (plan v1.5 item 6): `follow-toggle` on the follow-playhead toggle
  button, immediately left of the `Lanes` button; `aria-pressed` tracks the
  persisted flag (default on).
- lane head (plan v1.5 item 7): a lane fed by an unpromoted `experiments/`
  sandbox carries `<i.ph.ph-flask.tl-lane-head__flask>` (`aria-label`
  `"Experimental lane"`) as the first child of `.tl-lane-head__name`, before
  `<span.tl-lane-head__name-text>`. Exactly five lanes — `dropProposals`,
  `allin1Transitions`, `allin1Sections`, `character`, `vocalTranscription`. The
  same badge precedes `.app-rightpanel__kicker` in that lane's events panel
  header. `LaneList.tsx` is not badged.

Still pending (later plan items / not yet needed): `song-select`,
`transport-play` / `transport-pause`, `selection-overlay`. Prefer `getByRole` /
`getByLabel` where the control already has an accessible name (transport buttons,
zoom buttons all have `aria-label`).

---

## 6. Local workflow

Prereqs: Docker. The suite runs in the pinned Playwright container image — the
host does not need Node or browsers (and Playwright does not ship browsers for
every host OS).

```bash
# 1. rebuild the frozen fixtures (only if a source song changed)
python3 tests/ui-visual/fixtures/build-fixtures.py

# 2. build + start the UI against the fixture data
docker compose -f docker-compose.yml -f docker-compose.visual.yml up -d --build ui

# 3. sanity check
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9090/
curl -s "http://localhost:9090/data/analysis/" | head

# 4. run the suite (pinned container, host network → localhost:9090)
docker run --rm --network host -v "$PWD/tests/ui-visual:/work" -w /work \
  mcr.microsoft.com/playwright:v1.56.0-noble \
  sh -c "npm ci && npx playwright test"
# report: tests/ui-visual/report/index.html

# 5. when a change is intentional, re-capture and review the diff before committing
docker run --rm --network host -v "$PWD/tests/ui-visual:/work" -w /work \
  mcr.microsoft.com/playwright:v1.56.0-noble \
  sh -c "npm ci && npx playwright test --update-snapshots"
git add tests/ui-visual/__screenshots__
```

Review rule: a baseline update PR must include the Playwright HTML report (or the
before/after PNGs) and a one-line justification per changed snapshot.

---

## 7. CI integration

Trigger: any PR touching `ui/**` or `tests/ui-visual/**`.

Steps:

1. `docker compose -f docker-compose.yml -f docker-compose.visual.yml up -d --build ui`
2. Wait for `http://localhost:9090/` to return `200` (poll, ~30s timeout).
3. Run Playwright **inside the pinned Playwright container** so the Chromium build
   matches local Linux runs:
   `docker run --rm --network host -v "$PWD/tests/ui-visual:/work" -w /work
   mcr.microsoft.com/playwright:v<pinned> npx playwright test`
4. On failure: upload `tests/ui-visual/report/` and `tests/ui-visual/**/*-diff.png`
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

- [x] Add the `data-ui-ready` readiness marker to the app (§5.2). *(plan item 1)*
- [x] Add `data-testid`s listed in §5.5 — the subset plan v2.1 needs. *(plan item 1)*
- [x] Build the three fixture folders (§3.1) and the compose override for mounting
      them (§3.2) — `tests/ui-visual/fixtures/` + `docker-compose.visual.yml`. *(plan item 1)*
- [x] Add the standalone `tests/ui-visual/` Playwright project
      (`package.json` + `playwright.config.ts` + `specs/`). *(plan item 1)*
- [x] Capture initial baselines in the pinned container image and commit them
      — `song-full`, `song-no-audio`, `left-panel-open`, `lane-collapsed`,
      `timeline-scrolled-50`, `timeline-zoom-max`, `timeline-zoom-min`. *(plan item 1)*
- [x] Add the CI job (§7) — `.github/workflows/ui-visual.yml`. *(plan item 1)*
- [ ] Decide the `_test_song` audio question with Ops (see `ui-issues.md` §2).
      Interim: `RegFull`/`RegPartial` ship the real mp3; `_test_song` has none
      (its baseline is the beat-pulse fallback). Plan item 2 finalizes whether
      `RegFull` keeps the mp3 or moves to a pre-decoded peaks JSON.
- [ ] Fold the "smoke check" list from `ui/README.HELPER_UI.md` into explicit
      assertions so the README checklist and the suite cannot drift apart.
- [ ] *(plan item 9)* Corner-pixel checks on `humanHints` / `sections` blocks;
      re-diff `song-full` after squaring the block corners.
- [x] *(plan item 10)* `data-hint-drag-ready` marker + `hint-editor`
      `data-hint-id` selector wired; `RegFull`'s frozen `human_hints.json` block
      ids + start/end times recorded in §3.1 (3 non-overlapping blocks).
- [x] *(plan item 10)* `hint-drag-resized.png` baseline captured in the pinned
      container; `tests/ui-visual/specs/hint-drag.spec.ts` drag / resize / move /
      snap / persist / min-gap checks all green (full suite 18/18). The spec
      drives `page.mouse` in page coordinates, so its `lanePoint` helper first
      scrolls `.app-timeline` to bring the (far off-screen) fixture blocks into
      the viewport — `page.mouse` never auto-scrolls.
- [x] *(plan item 10)* The drop commits through the real `PUT /api/human-hints`,
      so `docker-compose.visual.yml` mounts `fixtures/analysis` **writable** (no
      `:ro`). `hint-drag.spec.ts` snapshots the one fixture file it mutates and
      restores it in `afterAll` / before each test; if a run is hard-killed,
      `git checkout -- "tests/ui-visual/fixtures/analysis"` resets it.
- [x] *(plan v1.5 item 1)* `tests/ui-visual/specs/card-click-seek.spec.ts` — a
      paused card click (human-hint block, segment block) seeks and opens its
      panel; background clicks on the Bars ruler still seek; no baseline pixels
      change. The playing-half of R3 (`seekTimeForCardClick` returns `null` while
      playing) is covered by `ui/src/app/transportRules.test.ts`, since the suite
      cannot press Play.
- [x] *(plan v1.5 item 2)* `tests/ui-visual/specs/left-panel.spec.ts` second
      `test(...)` block — R4/R5: an outside `mousedown` closes the left panel, an
      inside click never does, the burger's mousedown/click pair does not
      re-open it, `esc` still closes, and picking a song closes it. The pure
      rule is `shouldDismissLeftPanel` in `ui/src/app/panelState.ts`
      (`panelState.test.ts` truth table).
- [x] *(plan v1.5 item 3)* `tests/ui-visual/specs/lane-events.spec.ts` — the
      `columns-plus-right` opener sits right-aligned in every block lane's head
      and does not move the collapse caret; clicking it stacks that lane's
      events in the right panel (`lane-events-panel.png` baseline), the panel is
      non-modal (survives a viewport click, a caret click and a zoom), a second
      opener click toggles it off, opening another lane's replaces it (never two
      panels), and `esc` closes it.
- [x] *(plan v1.5 item 3)* Re-capture every `.app-timeline__grid` baseline —
      `song-full`, `song-full-waveform`, `song-no-audio`, `left-panel-open`,
      `lane-collapsed`, `lanes-hidden-all`, `timeline-scrolled-50`,
      `timeline-zoom-min` (both the `timeline-zoom` and `fit-to-width` snapshot
      dirs), `timeline-zoom-max`, `hint-drag-resized`. Justification: "lane
      heads gain the `columns-plus-right` events opener (plan v1.5 item 3)" — an
      18px glyph added to thirteen lane heads, under `maxDiffPixelRatio` on a
      full-grid capture, so the old baselines may pass while being wrong.
      `waveform-no-audio.png` (locator `.tl-lane-body[data-lane="waveform"]`,
      which has no lane head) must **not** change.
- [x] *(plan v1.5 item 4)* `tests/ui-visual/specs/lane-events.spec.ts` second
      `test(...)` block — R1's highlight: nothing active at `0:00.0`, a paused
      card click marks exactly that card `data-active="true"`, the highlight
      clears when a "Previous beat" step lands in the gap between two hints
      (`lane-events-active.png` baseline). The pure rule is `activeBlockIndex`
      in `ui/src/panel/laneEvents.ts` (`laneEvents.test.ts`); the
      `scrollIntoView` follow is playback-only and not visually asserted.
- [x] *(plan v1.5 item 5)* `tests/ui-visual/specs/header-readout.spec.ts` — R9/R10:
      the `app-header__barbeat-caption` span is gone and `.app-header` no longer
      contains the string "bar.beat"; the `.app-header__center`,
      `.app-header__time` and `.app-header__barbeat` bounding boxes do not shift
      (within 0.5 px) when the clock goes from `0:00.0` / bar `1.1` to `1:04.0`
      and the bar number gains digits; the reserved widths are real
      (`.app-header__time` ≥ 48 px, `.app-header__barbeat` ≥ 40 px at the short
      strings). Baseline `header-readout.png` (`.app-header`) — the first header
      baseline; no existing `.app-timeline__grid` baseline changes.
- [x] *(plan v1.5 item 6)* `tests/ui-visual/specs/follow-playhead.spec.ts` — R6:
      the `follow-toggle` sits left of the `Lanes` button, defaults to
      `aria-pressed="true"`, toggles and persists across a reload, and its
      pressed `color` differs between states; paused, nothing follows a card
      click. Baseline `footer-follow.png` (`.app-footer`), follow off. The
      behavioural half (follow moves the timeline while playing; a user scroll
      during playback turns the toggle off) is covered by `followScrollLeft` and
      `isUserScroll` in `ui/src/timeline/follow.test.ts` — the suite cannot
      press Play. No `.app-timeline__grid` baseline changes.
- [x] *(plan v1.5 item 7)* `tests/ui-visual/specs/experiment-badge.spec.ts` —
      R7: exactly five lane heads (`dropProposals`, `allin1Transitions`,
      `allin1Sections`, `character`, `vocalTranscription`) carry
      `.tl-lane-head__flask`; every production lane and the whole-document count
      confirm five total; the badge sits left of `.tl-lane-head__name-text` and
      no badged label is pushed into an ellipsis (`scrollWidth - clientWidth` ≤ 0
      at 1280 px); the collapse caret does not move; opening
      `lane-events-character` shows exactly one `.app-rightpanel .tl-lane-head__flask`
      in the panel header. `caret-fixed-position.spec.ts` still passes.
- [x] *(plan v1.5 item 7)* Re-capture the same eleven `.app-timeline__grid`
      baselines listed for item 3 — `song-full`, `song-full-waveform`,
      `song-no-audio`, `left-panel-open`, `lane-collapsed`, `lanes-hidden-all`,
      `timeline-scrolled-50`, `timeline-zoom-min` (both the `timeline-zoom` and
      `fit-to-width` snapshot dirs), `timeline-zoom-max`, `hint-drag-resized`.
      Justification: "experiment lanes gain the flask badge (plan v1.5 item 7)".
      `waveform-no-audio.png` must again be unchanged.
