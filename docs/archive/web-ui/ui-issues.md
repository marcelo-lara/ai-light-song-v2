> **ARCHIVED — historical record, not a specification.**
> This document describes how something was *planned or built at the time*. It
> is **not** a description of current behaviour and may contradict the code.
> Do not treat it as a contract and do not implement from it: verify against
> `src/` first. For what the system does today, read `CLAUDE.md` at the repo
> root.

# UI Visual Regression Report

Date: 2026-08-30
Last updated: 2026-09-01 (added findings 6–7 — "Next beat" bar-boundary stall;
view resets after hint edit — then marked both FIXED)

Scope: Visual regression and manual inspection of the internal Artifact Debugger UI
(`ui/`, the Compose `ui` service) with `_test_song` loaded.

Host: http://localhost:9090 (container port `8080` published as `9090`)

Song under test: `?song=_test_song`

Screenshots:

- `screenshots/ui_homepage_1.png`
- `screenshots/ui_timeline_test_song.png`

Console log: `ui-issues_console.log`

## Findings

### 1) Console TypeError on load — sparse lane with no timeline data (FIXED)

- Severity: High (breaks timeline render for every song).
- Location: `ui/src/lib/timeline/sparseContent.js:13`, reached from
  `ui/src/lib/timeline/sparseLane.js` → `drawSparseLane` → `buildSparseLaneContent`.
- Console: `TypeError: Cannot read properties of undefined (reading 'map') at
  buildSparseLaneContent (src/lib/timeline/sparseContent.js:13:55)`, logged once per
  redraw (zoom, scroll, playback tick), so it repeats rapidly.
- Root cause: the `beatdropPlan` lane is declared in
  `ui/src/lib/config/laneDefinitions.js` and is visible by default
  (`createInitialLaneVisibility` in `ui/src/app/laneState.js` sets every lane to
  `true`), but `buildTimelineData` (`ui/src/lib/data/buildTimelineData.js`) never
  emits a `timeline.beatdropPlan` array and no artifact loader supplies one. The
  `case "beatdropPlan"` branch then calls `.map` on `undefined`. Any future
  lane-definition entry without a matching `buildTimelineData` field would fail the
  same way. `humanHints` is *not* affected because `App.jsx` always injects that
  array into the timeline model.
- Impact: the sparse-lane draw loop throws before later lanes are drawn, so lanes
  below the failing one can render blank or stale; overlays and hovercards for those
  lanes are unavailable.
- Fix applied:
  - `sparseContent.js` now coerces any missing lane array to `[]` via a local
    `rows(key)` helper, so an undeclared or not-yet-loaded lane renders empty
    instead of throwing.
  - `buildTimelineData` now returns `beatdropPlan: asArray(data?.beatdropPlan?.windows)`
    so the timeline model shape matches the lane definitions.
- Verification still required: load `?song=_test_song` in a browser and confirm the
  console is clean and the BeatDrop Plan lane shows as an empty lane row. (No
  headless browser is available in this environment; the fix is syntax-checked and
  the container rebuilds and serves.)

### 2) Missing audio file for `_test_song` (NOT A BUG — fixture gap)

- Severity: Low (expected for the synthetic test song).
- Location: network — `GET /data/songs/_test_song.mp3` → `net::ERR_ABORTED`.
- Cause: `_test_song` is a synthetic analysis fixture; there is no rendered MP3 at
  the mounted `data/songs` path. `useSongData` always points the `<audio>` element
  at `data/songs/<song>.mp3`.
- Impact: the Waveform Anchor lane falls back to the beat-pulse rendering and the
  transport/playback controls are effectively disabled for this song. All artifact
  lanes still load and render.
- Recommendation: either add a short silent/synthetic `data/songs/_test_song.mp3`
  fixture, or treat "no audio → waveform fallback + disabled transport" as an
  expected, asserted state in the regression baseline for `_test_song`. Do not treat
  the `ERR_ABORTED` line as a regression on its own.

### 3) Automated click intercepted by stacked canvas lanes (test-infra guidance)

- Severity: Low (affects test authoring, not users).
- Symptom: headless click attempts on controls near the timeline are intermittently
  intercepted by overlapping lane canvases. Manual clicking works.
- Impact: E2E scripts must target stable selectors and may need to scroll a control
  into view or dismiss an open overlay/hovercard first.
- Recommendation: drive controls through role/label selectors or add explicit
  `data-testid` attributes to the sidebar controls, transport buttons, song menu,
  and lane toggles. Prefer Playwright's auto-waiting `getByRole` over coordinate
  clicks. See the regression guide for the selector list.

### 4) Timeline / ruler labels truncate at narrow viewport widths (Minor)

- Severity: Minor (readability only).
- Symptom: bar/section labels in the ruler and sparse lanes overlap or clip when the
  window is narrow or the sidebar is expanded.
- Impact: reduced readability in small windows; no data loss (hovercards still show
  full detail).
- Recommendation: add responsive text trimming with an ellipsis and expose the full
  label on hover. Until fixed, pin the regression viewport to a fixed width (see
  guide) so this does not cause baseline noise.

### 5) "No validation report loaded." in Validation Snapshot (could not reproduce; hardening recommended)

- Severity: Low.
- Status: not reproducible with `_test_song`, which has a valid
  `artifacts/validation/phase_1_report.json` that loads into `data.validation`.
- Likely original cause: observed on a song folder missing that file, or on a
  transient fetch failure. `loadArtifactRecords` swallows per-file fetch/parse
  errors (`ok: false`, `data: null`) and the panel only distinguishes
  "report is falsy" from "report present" — it cannot tell "file absent" from
  "file failed to parse".
- Recommendation: in `ValidationSnapshotPanel` / the file-status list, surface the
  captured `record.error` string and show a distinct "failed to load / parse"
  state with the path, separate from "not present". A per-file reload action is a
  nice-to-have.

### 6) "Next beat" transport button stalls on the last beat of a bar (reported 2026-09-01)

- Severity: Minor (navigation correctness in the hint editor / transport).
- Status: FIXED. `nextBeatTime` in `ui/src/timeline/useTransport.ts` now walks
  the flat, time-ordered beat list (first beat past `currentTime ± 1e-3` in the
  step direction, clamped to the ends) instead of stepping a bar-local beat
  index, so the last beat of a bar advances to beat 1 of the next bar and a
  playhead a rounding-hair short of a beat line no longer stalls. Covered by a
  new bar-boundary unit test.
- Symptom: the "Next beat" button does not advance when the playhead is on the
  final beat of a bar. Expected: from `bar.beat` 10.4 (last beat of bar 10),
  clicking "Next beat" moves to 11.1 (first beat of bar 11). Observed: the
  position does not move to the next bar's first beat.
- Likely area: the beat-stepping logic behind the transport's next-beat control
  appears to search within the current bar's beat list and has no fall-through to
  the first beat of the following bar when already at the last beat of the current
  one.
- Recommendation: when the current beat is the last in its bar, "Next beat"
  should advance to beat 1 of the next bar (and symmetrically, "Previous beat"
  from `x.1` should step back to the last beat of the previous bar). Confirm the
  same wrap behaviour at the first/last bar of the song (clamp, no wrap-around).

### 7) Timeline view jumps to song start after editing a human hint (reported 2026-09-01)

- Severity: Minor (loses the user's place during hint editing).
- Status: FIXED. `handleSaveHints` in `ui/src/App.tsx` no longer calls
  `reloadSong()` — the server-normalised file already flows into `hintsOverride`
  and updates the Human Hints lane in place. The full reload had reseeded every
  artifact to loading/null, collapsing `beats → coords → timelineW` and
  resetting the scroller's zoom/scroll on every hint drag-commit and panel Save.
- Symptom: after dragging a human hint — moving it, or dragging its start or end
  handle — the timeline scroll position and zoom reset to the beginning of the
  song. Expected: the view stays at the same scroll position and zoom level it
  had before the edit, with only the hint's geometry changed.
- Likely area: the hint-edit commit path appears to rebuild the timeline model or
  remount the timeline component, dropping the transient view state (scroll
  offset / zoom) instead of preserving it across the re-render.
- Recommendation: treat scroll offset and zoom as view state that survives a data
  update. On hint mutation, update only the affected hint in the timeline model
  and re-draw in place, keeping the current viewport. Applies to all three hint
  drag operations (move, resize-start, resize-end) and should also hold for hint
  create and delete.

## Handoff summary

- Developers: finding 1 is fixed in `sparseContent.js` and `buildTimelineData.js`;
  needs a browser verification pass. Findings 4 and 5 are open and owned by the UI
  team.
- QA: stand up the visual regression job described in
  `ui-regression_guide.md`. Treat findings 2 and 4 as known/expected states in
  the initial baseline rather than diffs to chase.
- Ops / fixtures: decide whether `_test_song` gets a real `data/songs/_test_song.mp3`
  or whether the audio-absent state is the asserted baseline.
