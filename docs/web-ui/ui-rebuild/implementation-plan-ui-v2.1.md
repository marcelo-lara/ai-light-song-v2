# Implementation Plan — Web UI v2.1

Turns [`product-refinement-ui-v2.1.md`](product-refinement-ui-v2.1.md) into
ordered, validated work. Item numbers are plan items; the refinement doc's items
(`1`–`5`, `B1`, `B2`) are referenced, not renumbered.

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its checks **in the container**
(`docker compose run --rm ui npm run test` and `docker compose run --rm ui npm
run build`, plus the item's **Visual QA** block against the running app); only if
they pass, tick its checkboxes, then commit and push that item by itself before
starting the next. Name the commit after the plan item as this plan writes it —
for example ``2. waveform lane renders on a real song``. One commit per item,
never a single batch commit at the end: a later failure then cannot strand the
validated work in front of it, and the history reads as this plan's own sequence.

**Use the recommendation; only a genuinely blocking decision stops an item.** An
open question that surfaces mid-implementation is resolved by adopting the best
recommendation and continuing — do not idle waiting to ask. The exception is a
decision where proceeding under any assumption would make the work wrong or
wasted. In that case write the decision and its options into this plan as a new
`D` item, then **continue with the next item**, skipping only those that
genuinely depend on the blocked one. A single unresolved question must never
stall a whole run; everything independent of it still gets built.

## Working notes for this pass

- Scope is confined to `ui/` and the visual-regression harness under
  `tests/ui-visual/`. **No analyzer artifact, `schema_version`, or
  `build_ui_data` contract changes** — so this pass produces **no
  contract-change / handoff note**; the MCP surface is untouched.
- Design source of truth is unchanged:
  [`design/design-notes.md`](design/design-notes.md) and
  [`design/Score-Analysis-DAW.dc.html`](design/Score-Analysis-DAW.dc.html).
  Where an item here contradicts a `UI v2` decision (item 1 vs. the collapsed
  "title + sub-caption" row; item 4 vs. the "left panel open" default), the
  refinement doc for this pass wins and the `UI v2` archived docs are annotated
  in the same commit.
- Every token comes from `ui/src/styles/nocturne.css`. Every icon is Phosphor.
- Target browser: **Chrome 151** only. `esnext` build target. No polyfills.
- Persisted lane/panel state lives in `localStorage` (already wrapped in
  try/catch by `laneState.ts`); new persisted keys follow the same pattern.

## Status

| # | Item | Refs | State |
| --- | --- | --- | --- |
| 1 | Visual-regression harness skeleton | guide §9 | ☑ |
| 2 | Waveform lane renders on a real song | B1 | ☐ |
| 3 | Continuous lanes span the full timeline | B2 | ☐ |
| 4 | Left panel collapsed by default | R2 | ☐ |
| 5 | Collapsed lane shows the title only | R1 | ☐ |
| 6 | Collapse/expand control keeps a fixed position | R5 | ☐ |
| 7 | "Fit to width" is an icon-only control | R3 | ☐ |
| 8 | "Hide all" button on the lane list | R4 | ☐ |

## How to test

The UI is Docker-based. Per item:

```bash
docker compose run --rm ui npm run test          # vitest + @testing-library/react
docker compose run --rm ui npm run build         # type-check + production bundle
docker compose up -d ui                           # serve at http://localhost:9090
# then the item's Visual QA block (Playwright, see the regression guide)
docker compose -f docker-compose.yml -f docker-compose.visual.yml up -d --build ui
cd tests/ui-visual && npx playwright test
```

Component tests cover pure logic (state reducers, geometry, coordinate maths).
Canvas pixel output, wavesurfer, and layout are covered by the Playwright visual
suite built in item 1, not by vitest.

---

## Phase A — Harness

### 1. Visual-regression harness skeleton

Builds the deterministic Playwright suite the later items validate against —
[`../ui-regression_guide.md`](../ui-regression_guide.md) §9's outstanding list.
Until this lands, no frontend item in this plan is considered validatable.

- [x] **Readiness marker.** `App.tsx` sets
      `document.documentElement.dataset.uiReady = "1"` once the selected song's
      visible lanes have drawn at least once, and clears it (`= "0"`) at the
      start of every song load / full re-layout. A `data-ui-loading` attribute
      carries the in-flight artifact count for debugging.
- [x] **Stable selectors.** Add the `data-testid`s from the guide §5.5 that this
      plan needs: `burger-toggle`, `left-panel`, `lane-list`, `lane-list-hide-all`,
      `fit-to-width`, `zoom-in`, `zoom-out`, `timeline-viewport`, and on every
      lane row `data-lane="<laneId>"` plus `data-lane-collapsed="true|false"` and
      a `data-testid="lane-collapse-<laneId>"` on the caret. Prefer `getByRole` /
      `getByLabel` where an accessible name already exists.
- [x] **Fixtures** under `tests/ui-visual/fixtures/analysis/` — three frozen song
      folders (guide §3.1):
      - `RegFull - Fixture/` — **the primary baseline**: a real, fully-populated
        song. Copy a real analysed song that has a rendered `data/songs/*.mp3`,
        `essentia/fft_bands.json`, `essentia/rms_loudness.json`,
        `essentia/loudness_envelope.json`, all sparse artifacts, and
        `reference/human/human_hints.json`. Trim dense arrays to ~60 frames but
        keep the **full song duration** in `info.json` / `beats.json` so the
        full-extent checks (§5 of the guide) are meaningful. Include the matching
        `.mp3` (a short real clip re-timed to the fixture duration, or a
        pre-decoded peaks JSON — decide in item 2).
      - `RegPartial - Fixture/` — missing one core artifact so the degraded
        banner renders.
      - `_test_song/` — copy of the synthetic fixture (no audio); the
        waveform-fallback baseline.
- [x] **Compose override** `docker-compose.visual.yml` bind-mounting the fixture
      dir over the data root and a matching (possibly empty) `data/songs`, per
      guide §3.2 "static mount".
- [x] **Playwright project** at `tests/ui-visual/`: `package.json`
      (`@playwright/test` pinned exact), `playwright.config.ts` (viewport
      `1280x720`, DPR 1, `baseURL http://localhost:9090`, HTML reporter,
      `toHaveScreenshot` `maxDiffPixelRatio: 0.01` / `threshold: 0.2` /
      `animations: "disabled"`), `helpers.ts` with:
      - `gotoSong(page, name)` — navigates, waits for `html[data-ui-ready="1"]`
        then `document.fonts.ready`.
      - `assertNoRuntimeErrors(page)` — collects `console.error` /
        `console.warn` / `pageerror` / unhandled rejection / any failed response
        for a URL under `/data/analysis/`; a helper `.list()` returns them.
        `/data/songs/*.mp3` 404 is allowed only for the `_test_song` spec.
      - `injectDeterminism(page)` — init script pinning `Date.now` / `new Date()`
        to a constant and stubbing `Math.random`; global stylesheet killing all
        `transition` / `animation`.
      - `fullExtentOfLane(page, laneId)` — returns the rightmost non-empty pixel
        column of a lane's canvas relative to the timeline content width, for the
        §5 full-extent assertions.
- [x] **Baseline captures** for the surfaces this plan touches, committed under
      `tests/ui-visual/__screenshots__/` in the CI Playwright container image:
      `song-full` (RegFull), `song-no-audio` (`_test_song`), `left-panel-open`,
      `lane-collapsed`, `timeline-scrolled-50`, `timeline-zoom-max`,
      `timeline-zoom-min`. Waveform canvas masked on `song-full`.
- [x] **Update the regression guide** in the same commit:
      `tests/ui-visual/` replaces the `ui/test/visual/` paths throughout §3, §5,
      §6, §7; the §9 checklist items done here are ticked; the readiness-marker
      and testid sections reflect what was actually added.
- [x] **CI job** (guide §7): triggers on `ui/**` and `tests/ui-visual/**`, runs
      Playwright in the pinned container, uploads the report + diffs on failure,
      never auto-updates baselines.

**Test:** `docker compose -f docker-compose.yml -f docker-compose.visual.yml up
-d --build ui` serves the fixtures; `cd tests/ui-visual && npx playwright test`
passes against the freshly-captured baselines; `assertNoRuntimeErrors` returns
empty for `song-full` and `left-panel-open`; deliberately hiding a lane and
re-running fails the `lane-collapsed` snapshot (proves the threshold is tight
enough).
**Commit:** `1. visual-regression harness skeleton`

**Notes — item 1 (resolved during implementation).**
- **RegFull source = "Armin - Revolution"** — the only fully-analysed song with
  `reference/human/human_hints.json` *and* a rendered mp3 *and* all three essentia
  dense artifacts. Duration 194.01 s preserved; `fft_bands` / `rms_loudness` /
  `loudness_envelope` decimated to ~60 evenly-spaced frames (first+last kept,
  `metadata.total_frames_original` recorded); `layer_b_symbolic.json` `note_events`
  truncated to 40 (lane only reads `phrase_windows`).
- **Fixture audio:** RegFull + RegPartial ship the real mp3 (exercises the real
  decode path — item 2's own recommendation); `_test_song` ships none. Item 2 may
  still swap RegFull to a pre-decoded peaks JSON.
- **Baselines target the `.app-timeline__grid` element, not `fullPage`** — lanes
  live in an inner `overflow:auto` scroller `fullPage` does not expand, so viewport
  shots were too insensitive (a whole collapsed lane diffed < 1 %). Element shots
  make the tightness sanity fail correctly (0.06).
- **Playwright pinned to exact `1.56.0`; the suite only runs inside
  `mcr.microsoft.com/playwright:v1.56.0-noble`** — the host OS (Ubuntu 26.04) has
  no supported Playwright browser build, so local runs and CI both use
  `docker run --network host` against that image, exactly as guide §7 specifies.
- Incidental `ui/` robustness fixes folded in: `parsers.ts` `stringRecord` now
  tolerates `null`/`undefined` values (real `info.json` carries `null` artifact
  paths, which threw a fatal `ShapeError`); `App.tsx` gained `?song=` deep-link +
  URL mirroring (the app had no URL handling and `gotoSong` needs it);
  `laneState.ts` gained `hideAll()` (item 8 adds its unit test).

---

## Phase B — Bugs

### 2. Waveform lane renders on a real song

Refinement `B1`. On a song with a real `data/songs/<song>.mp3`, the Waveform
Anchor lane is blank.

- [ ] Reproduce against `RegFull - Fixture` (has a real mp3): confirm the
      wavesurfer instance in `WaveformLane.tsx` receives the audio, finishes
      decoding, and that its container has non-zero width at mount.
- [ ] Root-cause and fix. Candidates to check in order: the wavesurfer container
      width is set from `timelineW` before `pxPerSec` is known (0-width canvas);
      the instance is created before the `<audio>` / URL is ready and never
      re-loads; the shell's playhead layer or a lane background is painted over
      the wavesurfer canvas (z-order / opacity); `waveColor` resolves to a
      transparent token. Adopt the fix the reproduction points to; if it is the
      decode cost, wire the loading state through and decode on an effect keyed
      to the resolved URL + width.
- [ ] Decide and record (as a `D` item if it changes fixture shape) whether
      `RegFull - Fixture` ships a real short mp3 or a pre-computed peaks JSON
      consumed via wavesurfer's `peaks` option. Recommendation: ship a short real
      mp3 re-timed to the fixture duration — it exercises the real decode path
      the operator hits.
- [ ] The lane still falls back to the beat-pulse rendering when no mp3 exists
      (`_test_song`), unchanged.

**Test:** unit — a `WaveformLane` render test asserts the wavesurfer container
receives a positive width and a resolved non-transparent `waveColor`. Visual QA
below.

**Visual QA (item 2).**
- Surface: `/?song=RegFull%20-%20Fixture`, default zoom, left panel closed.
  Wait for `html[data-ui-ready="1"]`.
- Checks (all binary):
  - The `data-lane="waveform"` canvas has ≥ 1 non-transparent pixel column in
    each 100px-wide band across its full width (no blank lane).
  - `fullExtentOfLane(page, "waveform")` is within 4px of the timeline content
    width (waveform reaches the same right edge as the Bars ruler).
  - Diff `song-full.png` (waveform region **unmasked** for this item's dedicated
    snapshot `song-full-waveform.png`) at `maxDiffPixelRatio: 0.01`.
  - `assertNoRuntimeErrors` list is empty.
- Surface: `/?song=_test_song`.
  - The `data-lane="waveform"` lane shows the beat-pulse fallback (diff
    `song-no-audio.png`); the only allowed failed response is
    `/data/songs/_test_song.mp3`.
**Commit:** `2. waveform lane renders on a real song`

### 3. Continuous lanes span the full timeline

Refinement `B2`. FFT Bands, RMS Loudness, and Loudness Envelope draw their data
only across the opening span of the timeline instead of the whole song.

- [ ] Reproduce against `RegFull - Fixture` at min zoom (whole song visible):
      confirm each lane's drawn content stops short of the timeline's right edge.
- [ ] Root-cause. Candidates: `CanvasLane.tsx` sizes its backing canvas from the
      viewport width rather than `timelineW`; the per-kind renderer iterates a
      truncated frame window; `bucketSeconds` / x-mapping caps at the first
      screen; the ResizeObserver redraw path does not pass the full content
      width. Fix so the canvas backing store and every renderer's x-domain run
      `0 .. timelineW` (`timeToX(duration)`), matching the ruler.
- [ ] Confirm the fix holds for `drums` and `energy` (same `CanvasLane` base) and
      after zoom changes and horizontal scroll (redraw covers the full extent,
      not just the current viewport).
- [ ] Define, in the item, the intended behaviour where an artifact's data ends
      before the song does (short `fft_bands.json`): the lane renders data to the
      last frame and leaves the remainder empty **without** clipping the canvas —
      i.e. "data ran out", not "lane is short".

**Test:** unit — a renderer-geometry test asserts the last drawn x for a
full-length fixture equals `timeToX(duration)` within 1px; a short-data fixture
draws to its last frame and no further.

**Visual QA (item 3).**
- Surface: `/?song=RegFull%20-%20Fixture` at **min zoom** (`fit-to-width`), left
  panel closed, all three lanes expanded.
- Checks:
  - For each of `data-lane="fftBands"`, `"rmsLoudness"`, `"loudnessEnvelope"`:
    `fullExtentOfLane` is within 4px of the timeline content width.
  - At ~50% `scrollLeft` and at max `scrollLeft`, each lane has non-empty content
    aligned to the Bars gridlines within 2px (diff `timeline-scrolled-50.png`).
  - At max zoom, the same three lanes still reach the content right edge (diff
    `timeline-zoom-max.png`).
  - `assertNoRuntimeErrors` empty across the scroll and zoom steps.
**Commit:** `3. continuous lanes span the full timeline`

---

## Phase C — Refinements

### 4. Left panel collapsed by default

Refinement item `R2`.

- [ ] The left panel (`data-testid="left-panel"`) mounts collapsed on first
      load. Persist the open/closed state to `localStorage` (try/catch); absent
      or unreadable value → collapsed.
- [ ] The burger control (`data-testid="burger-toggle"`) toggles it open/closed;
      `esc` closes it (extend the existing `esc` cascade — panel → review → lane
      list → left panel → drawer).
- [ ] With the panel collapsed the timeline occupies the full width between the
      212px label column and the right edge; opening the panel reflows the
      timeline, it does not overlay.
- [ ] Annotate the `UI v2` archived refinement/plan "left panel open by default"
      note as superseded by this item, in the same commit.

**Test:** unit — the panel-state reducer defaults to collapsed and round-trips
through the persistence helper.

**Visual QA (item 4).**
- Surface: `/?song=RegFull%20-%20Fixture`, fresh `localStorage`.
- Checks:
  - On load, `left-panel` has `data-open="false"` (or is absent from the
    layout); `timeline-viewport` left edge is within 2px of the label column's
    right edge. Diff `song-full.png`.
  - Click `burger-toggle`: `left-panel` `data-open="true"`, its width > 0, and
    `timeline-viewport` left edge shifts right by the panel width (not covered).
    Diff `left-panel-open.png`.
  - Press `esc`: panel returns to `data-open="false"`.
  - Reload: panel still `data-open="false"` after it was left open? No — closed
    state persisted; assert it reflects the last toggle (open→reload→open).
  - `assertNoRuntimeErrors` empty.
**Commit:** `4. left panel collapsed by default`

### 5. Collapsed lane shows the title only

Refinement item `R1`.

- [ ] When a lane's `expanded` is false, the label column renders only the lane
      title — the sub-caption line is not rendered in the collapsed state. It
      returns when the lane is expanded.
- [ ] The faint mini data-strip summary in the collapsed lane body is
      **unchanged** and still renders.
- [ ] The collapsed row height may shrink to fit the single-line label + strip;
      update any hard-coded `26px` collapsed-lane constant and the canvas
      geometry that depends on it so the strip is not clipped.
- [ ] Annotate the `UI v2` archived spec's "collapsed = title + sub-caption"
      wording as superseded.

**Test:** unit — the lane-header component renders the sub-caption node only when
`expanded`; the collapsed-lane height helper returns a value ≥ the strip height.

**Visual QA (item 5).**
- Surface: `/?song=RegFull%20-%20Fixture`, left panel closed. Collapse the
  `rmsLoudness` lane via `lane-collapse-rmsLoudness`.
- Checks:
  - The `data-lane="rmsLoudness"` row's label column contains exactly one text
    line (the title); the sub-caption element is absent.
  - The lane body still contains a non-empty data strip (≥ 1 non-transparent
    pixel column per 100px band).
  - Expand it again: the sub-caption element is present.
  - Diff `lane-collapsed.png`.
  - `assertNoRuntimeErrors` empty.
**Commit:** `5. collapsed lane shows the title only`

### 6. Collapse/expand control keeps a fixed position

Refinement item `R5`.

- [ ] The collapse/expand caret is anchored at the top of the lane label,
      immediately beside the title, at the **same x/y** in both the expanded and
      collapsed states. Toggling a lane must not move the caret's bounding box.
- [ ] Applies to every lane kind (canvas and sparse) and to the collapsed
      single-line row from item 5.

**Test:** unit — snapshot the lane-header layout classes for both states and
assert the caret's container is the same fl/ grid slot.

**Visual QA (item 6).**
- Surface: `/?song=RegFull%20-%20Fixture`, left panel closed.
- Checks:
  - Record `lane-collapse-fftBands` bounding box. Click it (collapse), wait for
    `data-lane-collapsed="true"`, record the box again: `x` and `y` differ by
    ≤ 1px.
  - Click again (expand), wait for `data-lane-collapsed="false"`, record: `x`/`y`
    within ≤ 1px of the original.
  - Repeat for a sparse lane (`sections`).
  - `assertNoRuntimeErrors` empty.
**Commit:** `6. collapse/expand control keeps a fixed position`

### 7. "Fit to width" is an icon-only control

Refinement item `R3`.

- [ ] `fit-to-width` renders a single Phosphor icon — no text label, no border.
- [ ] On hover it changes background colour, matching the `zoom-in` / `zoom-out`
      icon-button hover treatment (same token, same transition-less swap).
- [ ] Its action (`fitToWidthPxPerBar`) and keyboard binding (`f`) are unchanged;
      it keeps an accessible name (`aria-label="Fit to width"`).

**Test:** unit — the control renders no text node and has `aria-label`; a
render-with-hover test asserts the hover class toggles the background token.

**Visual QA (item 7).**
- Surface: `/?song=RegFull%20-%20Fixture`, footer visible.
- Checks:
  - `fit-to-width` contains no visible text; its computed `border-width` is 0.
  - Its default background matches `zoom-in`'s default background (same computed
    value).
  - Hover it: computed background changes to the shared hover token; unhover:
    reverts.
  - Click it: `pxPerBar` becomes the fit value (timeline content width within 4px
    of the viewport inner width). Diff `timeline-zoom-min.png`.
  - `assertNoRuntimeErrors` empty.
**Commit:** `7. fit-to-width is an icon-only control`

### 8. "Hide all" button on the lane list

Refinement item `R4`.

- [ ] Add a `lane-list-hide-all` control to `tl-lanelist` (`LaneList.tsx`) that
      sets `visible = false` for every lane in one action, persisted like the
      per-lane toggles.
- [ ] Individual lanes can still be re-shown from the list afterward; a
      companion "show all" is **out of scope** unless it already exists.
- [ ] With every lane hidden the timeline shows the sticky Segments + Bars header
      and an empty lane area (no crash, no error).

**Test:** unit — the lane-visibility reducer's "hide all" action zeroes every
`visible` flag and the result round-trips through persistence.

**Visual QA (item 8).**
- Surface: `/?song=RegFull%20-%20Fixture`, open the lane list.
- Checks:
  - Click `lane-list-hide-all`: every `data-lane="*"` row is removed from the
    timeline (0 lane rows); the Segments and Bars header rows remain.
  - `assertNoRuntimeErrors` list is empty (no `.map`-of-undefined class error
    from an empty lane set).
  - Re-show one lane from the list: that `data-lane` row reappears and renders.
  - Diff a new baseline `lanes-hidden-all.png`.
**Commit:** `8. hide all button on the lane list`

---

## When something fails after an item is committed

Route by *which component* and *does the fix need planning*:

- **One-off UI fix, no design decision** → a finding in
  [`../ui-issues.md`](../ui-issues.md) (finding / severity / location / root
  cause / fix applied), with failing screenshots + the Playwright diff under
  `tests/ui-visual/`.
- **Needs a design decision, or must be sequenced with other work** → a `BUG`
  entry in [`product-refinement-ui-v2.1.md`](product-refinement-ui-v2.1.md)
  **Bugs — Open**, annotated "Addressed by item N", adding a plan item if none
  fits.
- **Found mid-run against an earlier item** → log it to the right place above and
  keep going; halt only if it blocks the item currently being worked. Never
  silently fix across item boundaries — the history stays one commit per item.

## Decisions raised during implementation

Add `D1`, `D2`… here only when an item is genuinely blocked mid-implementation —
a decision where proceeding under any assumption would make the work wrong or
wasted. Record it and its options, then continue with the next independent item.
Once answered, fold the answer into the affected item's definition (and the
refinement / design docs) rather than leaving it as a log entry.
