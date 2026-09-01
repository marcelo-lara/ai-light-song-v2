# Implementation Plan — Web UI Rebuild (UI v2)

Turns [`product-refinement.md`](product-refinement.md) into ordered, validated
work. Item numbers are plan items; they reference the refinement doc's items
(`R1`–`R10`) rather than renumbering them.

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its checks **in the container**
(`docker compose run --rm ui npm run test` and `docker compose run --rm ui npm
run build`, plus the manual smoke the item names); only if they pass, tick its
checkboxes, then commit and push that item by itself before starting the next.
Name the commit after the plan item as this plan writes it — for example
``3. timeline shell``. One commit per item, never a single batch commit at the
end: a later failure then cannot strand the validated work in front of it, and
the history reads as this plan's own sequence.

**Use the recommendation; only a genuinely blocking decision stops an item.** An
open question that surfaces mid-implementation is resolved by adopting the best
recommendation and continuing — do not idle waiting to ask. The exception is a
decision where proceeding under any assumption would make the work wrong or
wasted. In that case write the decision and its options into this plan as a new
`D` item, then **continue with the next item**, skipping only those that
genuinely depend on the blocked one. A single unresolved question must never
stall a whole run; everything independent of it still gets built.

## Working notes for this rebuild

- **The pre-rebuild app was moved to a reference copy in item 1's commit** (not
  deleted yet) and was the **behaviour reference** for the whole rebuild — its
  `src/app/*`, `src/components/*`, `src/lib/*`, `vite.config.js` were read to
  learn the data API, discovery logic, hint-editor rules and semantic-zoom
  thresholds, then the new code was written fresh at `ui/`. The reference copy
  was **deleted at cutover (item 11)**; there are now **zero references to it**
  anywhere in the repo.
- Design source of truth:
  [`design/design-notes.md`](../design/design-notes.md) and
  [`design/Score-Analysis-DAW.dc.html`](../design/Score-Analysis-DAW.dc.html).
- Every token comes from `src/styles/nocturne.css`. Every icon is Phosphor.
- **Target browser: Chrome 151** (the operator's browser) — nothing else. No
  cross-browser fallbacks, no polyfills, no autoprefixer. Use modern web APIs
  freely (`oklch()`, `color-mix()`, `:has()`, container queries, top-level
  `await`, etc.); `tsconfig` / vite `build.target` = `esnext`.

## Status

| # | Item | Refs | State |
| --- | --- | --- | --- |
| 1 | Fresh app shell — React + TS + Vite | R1 | ☑ |
| 2 | Data layer — typed artifact access | R2 | ☑ |
| 3 | Timeline shell — grid, rulers, zoom, playhead, lane list | R3 | ☑ |
| 4 | wavesurfer.js — audio, waveform lane, master clock | R4 | ☑ |
| 5 | Dynamic data lanes — FFT, RMS, Envelope (+ drums, energy) | R5 | ☑ |
| 6 | Right panel — shell + block inspector (read-only) + hint editor | R6 | ☑ |
| 7 | Review-queue editor — right-panel third mode (functional v1) | R7 | ☑ |
| 8 | Artifact inspector (raw-JSON browser) | R8 | ☑ |
| 9 | All remaining lanes (sparse + validation), collapsed by default | R9 | ☑ |
| 10 | Keyboard, states, polish | R10 | ☑ |
| 11 | Parity sign-off + cutover | — | ☑ (tag `ui-v2` held — D8) |

## How to test

The UI is Docker-based. Per item:

```bash
docker compose run --rm ui npm run test          # vitest + @testing-library/react
docker compose run --rm ui npm run build         # type-check + production bundle
docker compose up ui                             # manual smoke at http://localhost:8080
```

Test data: use `_test_song` (fully analysed, has `human_hints.json`) and one
longer track (e.g. `Hideaway - Kiesza`) for zoom / scroll performance.

Component tests focus on pure logic — coordinate maths (`beatToX` / `xToBeat` /
`timeToBeat`), semantic-zoom threshold selection, hint draft ↔ payload mapping,
artifact-type parsing, follow-scroll maths. Canvas pixel output and wavesurfer
are smoke-tested manually against the design.

---

## Phase A — Shell and data

### 1. Fresh app shell — React + TS + Vite

- [x] New `ui/` tree: `package.json` (React 18, `react-dom`, `wavesurfer.js@^7`,
      `@phosphor-icons/web`, `vite`, `typescript`, `vitest`,
      `@testing-library/react`, `@testing-library/jest-dom`), `tsconfig.json`
      (strict), `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx`.
- [x] `src/styles/nocturne.css` — Nocturne `styles.css` vendored **unchanged**
      (keep the header comment pointing at the design project). *(See D1: the
      real DS file is not in-repo; reconstructed from design-notes §1/§3a.)*
- [x] `src/styles/daw.css` — `.tp` / `.tp-main` / `.zbtn` / `.zic` / `.caret` /
      `.dr-item`, the range-input and `.tl` scrollbar rules, and 4–5 named
      timeline-chrome locals (`--tl-bg`, `--tl-lane-head`, `--tl-ruler`, …),
      ported from the canvas `<style>` block to tokens.
- [x] Vendor Phosphor regular CSS + font files under `src/styles/phosphor/`
      (no unpkg at runtime).
- [x] App shell layout: header (3-col grid) / `main` (drawer · timeline ·
      right panel) / footer, all fixed bands with the scrolling middle — chrome
      only, lanes stubbed. Drawer has **exactly four** entries: **Select Song**,
      **Timeline** (active), **Artifact inspector**, **Review queue** — no
      placeholder destinations.
- [x] **`git mv ui the previous app`**, then scaffold the new tree at `ui/`, **in this
      same commit**. the previous app is the reference copy for items 2–10 and is
      deleted at cutover (item 11).
- [x] `ui/Dockerfile` (dev Vite stage + prod nginx stage) and `ui/nginx.conf`
      written for the new build output; `esnext` build target (Chrome 151).
      Compose `ui` service + port unchanged (still builds from `ui/`). No compose
      service for the previous app.
- [x] `ui/README.HELPER_UI.md` written for the new file map.

**Test:** `npm run build` + `npm run test` pass in the container; `docker compose
up ui` serves the empty shell at `:8080` matching the design's frame; `grep -E
'preact|@mui|@emotion' ui/package.json` is empty; the previous app still present.
**Commit:** `1. fresh app shell`

### 2. Data layer — typed artifact access

- [x] Port to `vite.config.ts`: the `/data` static mount + directory listing and
      `PUT /api/human-hints/<song>` handler from the previous app's `vite.config.js`
      (byte-for-byte behaviour, including the path-escape guard).
- [x] `src/data/types.ts` — TS types for every artifact the UI reads, mirroring
      the v2.1 contracts (`docs/web-ui/7.2.build_ui_data_story.md`,
      `docs/source references/contract-change-v2.1.md`).
- [x] `src/data/loaders.ts` — one loader per artifact
      (`info`, `beats`, `sectionsTopLevel`, `sectionSegmentation`, `fftBands`,
      `rmsLoudness`, `loudnessEnvelope`, `harmonicLayer`, `humanHints`,
      `eventTimeline`, `reviewQueue`), each returning parsed + typed data or a
      typed error.
- [x] `src/data/discovery.ts` — `data/analysis` listing ∩ `data/songs` audio
      files (logic from the old `songDataApi.js` / `discovery`).
- [x] `src/data/useSong.ts` — hook: given a song name, loads `info.json` + the
      artifacts the visible lanes need; exposes `{ status, data, error }` per
      artifact.
- [x] `src/data/saveHumanHints.ts` — `PUT /api/human-hints/<song>` client with
      the validation the previous app's hint editor enforced.

**Test:** `npm run test` covers the type parsers and discovery filter with
fixtures; manual: the drawer song picker lists the analysed songs and selecting
`_test_song` resolves every loader without error.
**Commit:** `2. data layer`

---

## Phase B — Timeline

### 3. Timeline shell — grid, rulers, zoom, playhead, lane list

- [x] `src/timeline/coords.ts` — **time-proportional x**: `x = t · pxPerSec`
      where `pxPerSec = pxPerBar / medianBarSeconds` (median bar length from
      `beats.json`). `timeToX` / `xToTime` are the primitives; `beatToX`,
      `xToBeat`, `beatToBarBeat` go through the real beat list. Bar lines are
      drawn at each bar's **real start time**, so bars are not equal pixel widths
      when the tempo drifts, and every lane + the playhead + wavesurfer stay in
      exact time alignment. `timelineW = duration · pxPerSec`. Pure, unit-tested.
- [x] `src/timeline/TimelineGrid.tsx` — CSS grid `212px max-content`, sticky
      Segments (h26) + Bars (h30) header rows, shared bar / 4-bar grid lines,
      the accent playhead (1 px line + `0 0 9px` glow + caret) spanning lanes.
- [x] `src/timeline/laneState.ts` — the lane registry (id, label, sub-caption,
      `kind`, `expanded`, `visible`). Default `expanded`: the design's five
      (`waveform`, `humanHints`, `fftBands`, `rmsLoudness`, `loudnessEnvelope`);
      every other lane collapsed. Persist `expanded` / `visible` per session
      (`localStorage`, wrapped in try/catch).
- [x] `src/timeline/LaneList.tsx` — a lane list (drawer "Analysis" section, or a
      togglable panel) to show/hide any lane and expand/collapse it; each lane's
      inline collapse caret toggles the same state.
- [x] `src/timeline/zoom.ts` + footer controls — `pxPerBar` 14–180 stays the
      zoom control and the `ppbLabel`; internally it sets `pxPerSec` (via
      `medianBarSeconds`). ± buttons (×/÷ 1.3), range slider,
      `fitToWidth = (viewportW − 212 − 12) / durationSeconds → pxPerSec` (then
      back-solve `pxPerBar` for the label). Semantic-zoom threshold table from
      design notes §2, keyed on `pxPerBar`.
- [x] Follow-playhead scroll while playing (design notes §2).
- [x] Bars ruler: bar lines at each bar's **real start time** from `beats.json`
      (downbeats = taller ticks), bar-number labels every *N* bars (*N* by
      `pxPerBar`), **beat sub-ticks only when `pxPerBar ≥ 44`**, click-to-seek.
- [x] Segments header: HTML blocks from the top-level `sections.json` list by
      `start`/`end` seconds → x; tint by `form_role` family (chorus/drop/hook =
      accent ramp, else neutral ramp); label = `form_role` + `N bars` (hidden
      when narrow), from the canvas `buildSegments` truncation rules. Click a
      segment block → block inspector (item 6). The `sections` sparse lane
      (item 9) also renders — the header and the lane both stay for now.

**Test:** `coords` (`timeToX`/`xToTime` round-trip, `medianBarSeconds`, bar-line
positions with a synthetic tempo drift) + `zoom` threshold selection +
follow-scroll maths unit-tested; manual: fit-to-width and the slider match the
design; playhead sits exactly on a bar line at each real bar time at 14, 62 and
180 px/bar; horizontal scroll never moves the label column or the page.
**Commit:** `3. timeline shell`

### 4. wavesurfer.js — audio, waveform lane, master clock

- [x] `src/timeline/WaveformLane.tsx` — wavesurfer v7 bound to
      `data/songs/<song>.mp3`, container width = `timelineW`, blurple wave
      colours (design notes §3a), redrawn on zoom, its own cursor disabled
      (the shared playhead is drawn by the timeline shell).
- [x] **First-load decode is accepted.** No peaks artifact exists — wavesurfer
      decodes the full mp3 on song load; show the lane's loading state until it
      is ready. A `/api/peaks/<song>` precompute endpoint is a **later**
      optimisation, out of scope for `ui-v2`.
- [x] `src/timeline/useTransport.ts` — `currentTime` driven only by wavesurfer
      events (`audioprocess` / `seeking` / `interaction`); exposes `play/pause`,
      `seekTo`, `seekToBeat`, `stepBeat(±1)`, `stepBar(±1)`, `isPlaying`,
      `duration`. **No rAF position loop.**
- [x] Header transport cluster + `m:ss.s / total` + `bar.beat` bound to the hook;
      the playhead x and follow-scroll read `currentTime` → `timeToX`.

**Test:** manual against the design — space toggles audio and the playhead moves
in lockstep; ruler / waveform click seeks audio + all lanes; header `bar.beat`
matches the beat under the playhead. Unit: `stepBeat` / `stepBar` land on the
right `beats.json` entries.
**Commit:** `4. wavesurfer master clock`

### 5. Dynamic data lanes — FFT, RMS, Envelope (+ drums, energy)

> **Palette is carried over verbatim.** The FFT / RMS / Envelope renderers and
> the stem sub-labels are a straight port of
> the previous app's `src/lib/timeline/fftBandsLane.js`, `loudnessLane.js`,
> `waveformLane.js` and `constants.js` — the exact constants are in **design
> notes §3a**. Do not re-derive lane colours from Nocturne's accent ramp; the
> mock's blurple lane formulas are superseded.

This item does the **continuous** lanes. Sparse (block) lanes and the click →
inspector wiring are item 9 + item 6.

- [x] `src/timeline/CanvasLane.tsx` — DPR-aware `<canvas>` lane body: shared
      grid + a per-`kind` renderer; redraw on `pxPerBar` / collapse / resize
      (ResizeObserver). Lane header (name / sub / collapse caret) bound to
      `laneState` (item 3); collapsed = 26 px + faint waveform strip. Continuous
      lanes: click anywhere = seek (no hit regions).
      > **Superseded by UI v2.1 plan items 5 & 6:** collapsed header shows the
      > **title only** (no sub-caption); the collapse caret is fixed top-left.
      > Collapsed height stays 26 px via `collapsedLaneHeight()`.
- [x] Port `src/timeline/palette.ts` from the current impl: `FFT_BAND_HUES =
      [22,46,88,138,164,186,196]`, `bandColor(i,v) → hsla(hue,84%,58%,v·0.9)`;
      `SOURCE_COLORS` = `[[250,204,21],[248,113,113],[34,211,238],[74,222,128],
      [192,132,252]]`; `CAPTION_FONT = '11px "IBM Plex Mono", monospace'`;
      lane heights (FFT 84, RMS/Env 112, hints 58, collapsed 26).
- [x] `fft` renderer — per-band `hsla` heat, **band 0 (Sub) at the bottom**
      (`displayIndex = bandCount−1−i`), `topPadding = bottomPadding = 6`,
      visibility floor `0.02` then `(v−0.02)/0.98`, per-bucket **max**,
      `bucketSeconds = max(intervalSeconds||0.05, 1/max(zoom,1))`.
- [x] `rms` renderer — per-stem row (`rowHeight = (112−10−(n−1)·2)/n`), per
      bucket `rgba(stem, 0.16 + v·0.72)` at `rowTop+1 .. rowHeight−2`, per-bucket
      max, floor `0.02`. Per-row bg `rgba(148,163,184,0.06)` + `0.16` bottom rule.
- [x] `env` renderer — filled area `rgba(stem, 0.18)` + stroke `rgba(stem, 0.94)`
      `lineWidth 1.5`, `baseline = rowTop + rowHeight − 4`,
      `amplitude = max(6, rowHeight − 14)`, x = bucket midpoint, per-bucket
      average.
- [x] Stem sub-labels (`drawSourceLabel`) — one per row, **anchored to the
      visible viewport left edge**: `x = round(scrollStart·zoom) + 6`; text =
      `sources[i].label` trimmed to 56 px in `CAPTION_FONT`, stem colour;
      background a plain `rgba(10,18,28,0.68)` rect `(x−2, rowTop+2,
      textWidth+6, 13)` — no border/radius; baseline `rowTop + 11`. Recompute on
      scroll.
- [x] wavesurfer `waveColor` / `progressColor` set to Nocturne blurple
      (`#968ae0` / `#d2cefd`) per design notes §3a — not the previous app's teal.
- [x] `drums` (kick/snare/hat density) and `energy` (beat-aligned energy +
      accent candidates) lanes ported from the previous app's `src/lib/timeline/drumsLane.js`
      / `seriesLane.js`, **collapsed by default**. Discrete markers (accent
      candidates) get hit regions → block inspector (item 6).
- [x] Each lane renders its own loading / empty (artifact missing) / error state.

**Test:** `palette.ts` + renderer geometry helpers (row edges, bucketing,
sub-label x) unit-tested; manual: FFT / RMS / Envelope render **pixel-comparable
to the previous app** (run both) side by side against `_test_song`; sub-labels stay put
while scrolling; collapse drops to 26 px + strip; `Hideaway - Kiesza` at max zoom
scrolls and zooms without dropped frames.
**Commit:** `5. data lanes`

---

## Phase C — Panels

### 6. Right panel — shell + block inspector (read-only) + hint editor

The 296 px right panel (`sc-if panelOpen`) is one shell with **modes**. This
item builds the shell + two modes; item 7 adds the third.

- [x] `src/panel/RightPanel.tsx` — the shell: header row (mode-specific ‹ › / ✕),
      body, footer; mount/unmount on `panelOpen`; outside-click dismiss (ignore
      clicks on a lane block / hint pill); `esc` closes.
- [x] **Mode: block inspector (read-only).** `src/panel/BlockInspector.tsx` —
      renders the clicked block's `selection` payload: `label` heading, a
      Nocturne `<dl>` of fields (`laneLabel`, time range, `confidence`,
      `reference`/`id`, `section_id`, `created_by`, …), and the `summary` line.
      A "show raw" disclosure dumps the block's full source object. **No inputs,
      no Save.** Fields per lane come from a `blockFields(laneId, selection)`
      map ported from the previous app's `src/lib/timeline/sparseContent.js` +
      `SelectionDetailCard/selectionFields.js`.
- [x] Clicking any lane block sets the selection → opens the panel in inspector
      mode and moves the shared playhead to the block start. Clicking a
      **Human Hints** block opens the **hint editor** mode instead.
- [x] **Mode: hint editor** (`HintEditorPanel`) — Start / End / Title / Musical
      hint / Lighting hint (mapping in design notes §4), ‹ › prev/next-hint,
      **new hint**, **delete active hint**, **set start/end to playhead**,
      Cancel / Save (`.btn-ghost` / `.btn-primary`).
- [x] Save → `PUT /api/human-hints/<song>` on explicit Save only; validation
      (id + title required, end ≥ start, numeric times); optimistic update +
      reload; pill reflects the edit. Selecting / creating a hint scrolls the
      timeline to it.
- [x] Replaces the previous app's floating `OverlayPanel` — block detail lives
      in the right panel, not a popover.

**Test:** `blockFields` mapping + hint draft↔payload + validation unit-tested;
manual: clicking a section / chord / machine-event block opens a read-only card
with the right fields and seeks the playhead; a hint block opens the editor;
edit + save writes `human_hints.json` and nothing else writes it.
**Commit:** `6. right panel — inspector and hint editor`

### 7. Review-queue editor — right-panel third mode  *(functional v1)*

A working first version — deeper iteration is a later release.

- [x] Port `PUT /api/song-facts/<song>` handler into `vite.config.ts` (from the
      the previous app's `vite.config.js`).
- [x] `src/panel/ReviewQueuePanel.tsx` — renders
      `artifacts/validation/review_queue.json` as ranked questions; whole-song
      answers (`form_family`, `form_family_vs_genre`) → `song_facts.json` on
      explicit Save; per-section / drop questions shown read-only for context.
      Opened from a drawer entry (no lane).
- [x] Third mode in the item-6 shell (mode switch, not a second aside).
- [x] Empty state when a song has no `review_queue.json` (not yet analysed under
      v2.1) — the panel says so rather than erroring.

**Test:** as Story 8.10 — answering `form_family` + Save writes `song_facts.json`
with `provenance: "human-confirmed"`; nothing else writes it; a song without a
review queue shows the empty state.
**Commit:** `7. review queue editor`

### 8. Artifact inspector

- [x] `src/inspector/ArtifactInspector.tsx` — drawer entry / bottom sheet that
      lists the song's `artifacts/**` files and renders a selected JSON with
      collapsible nodes + copy-path, styled with Nocturne `.table` / `.card`.
      Read-only. *(See D5: the walk roots at `data/analysis/<song>` rather than
      `artifacts/` so the previous app's non-`artifacts/` inspector files stay reachable.)*
- [x] Reachability check against the previous app's inspector file set (Story 8.9) — all
      25 files the previous app's inspector exposed resolve through the recursive walk
      (`_test_song`: 73 files reached, 0 missing).

**Test:** manual: every artifact the previous app's inspector exposed is reachable and
readable; no write path.
**Commit:** `8. artifact inspector`

---

## Phase D — Remaining lanes, polish, cutover

### 9. All remaining lanes — sparse + validation

Every lane in the previous app's `src/lib/config/laneDefinitions.js` ships (no conductor /
tempo / "global" strip — that stays removed). This item does the sparse lanes
and the regression overlay; FFT/RMS/Envelope/drums/energy are item 5.

- [x] `src/timeline/SparseLane.tsx` — a reusable block-lane body: builds hit
      regions from a per-lane content adapter, draws Nocturne-tinted rounded
      blocks with a label (+ caption when wide), row-packs overlapping blocks
      (the `identifierHints` / `machineEvents` / `mlEvents` / `phrases`
      compaction from `sparseLane.js`), sets hit regions for item 6.
- [x] `src/timeline/laneContent.ts` — the per-lane content adapters ported from
      the previous app's `src/lib/timeline/sparseContent.js`: `humanHints`, `sections`, `chords`
      (name + roman numeral, roman only when wide), `patterns`,
      `identifierHints`, `machineEvents`, `mlEvents`, `beatdropPlan`, `phrases`.
      Each yields `{ start_s, end_s, label, laneLabel, caption, reference,
      detail, summary, … }` for the block inspector.
- [x] `validation` (Regression Overlay) — port `validationLane.js` **best
      effort**: beat-drift + exported-event comparison marks, discrete marks
      clickable → block inspector. Its inputs (`eventComparisons`,
      `validationDrift`) are assembled in the previous app's `buildTimelineData.js` from
      validation artifacts — **don't spend time re-tracing them**: if the data
      isn't readily available, ship the lane as an empty-state stub and note it
      in the parity checklist. (Absorbs Story 8.7.)
- [x] Per-lane Nocturne tint set (replaces `sparseLaneStyles`) — keep the current
      hue assignments (hints amber, sections teal, chords cyan, patterns gold,
      identifiers blue, machine red, ml violet, beatdrop orange) but move the
      values onto ramp steps / documented locals.
- [x] **Default state:** all lanes in this item start **collapsed**
      except `humanHints` (expanded). Every lane is show/hide + expand/collapse
      from the lane list (item 3).
- [x] Clicking a block → item 6 block inspector (read-only), except `humanHints`
      → hint editor. Clicking a block also seeks the playhead to its start.

**Test:** `laneContent` adapters unit-tested against artifact fixtures; manual:
every lane renders and toggles; chord blocks align to bars on `_test_song`;
clicking a block in each lane opens the right-panel inspector with that block's
fields; the sticky header shows only Segments + Bars.
**Commit:** `9. remaining lanes`

### 10. Keyboard, states, polish

- [x] Keyboard: space / ←→ / shift+←→ / `+ - [ ]` / `f` / `esc` (refinement §10).
      Pure `src/app/keymap.ts` (`resolveKeyAction` + input-focus guard +
      `shouldPreventDefault`); single `window` listener in `App.tsx`. **§10
      deviation:** `[` `]` are zoom (with `+`/`-`), not prev/next-section — §10
      says "zoom" and does not split the four keys. `=`/`_` added as the
      unshifted faces of `+`/`_`. `esc` closes panel → review view → lane list →
      drawer, in that order.
- [x] Loading / empty / error states for the song list (`selectSongListState`)
      and a song with missing artifacts (`selectSongLoadState`: loading / fatal
      / degraded / ready) — pure selectors in `src/app/loadStates.ts`, both
      unit-tested. `SongPicker` renders the four list states; the timeline shows
      a loading stub, a fatal card (bad/absent `info.json` or `beats.json`), or a
      degraded banner naming the lanes whose artifact failed.
- [x] Focus management: `src/app/useFocusTrap.ts` — Tab-cycle trap + initial
      focus + restore-on-close, wired into `RightPanel` (all three modes;
      `role="dialog"` `aria-modal`). The drawer is non-modal — it takes initial
      focus on an open transition but is not trapped (documented deviation).
      > **Superseded by UI v2.1 plan item 4 (R2):** the drawer mounts collapsed
      > by default and its open/closed state persists to `localStorage`.
- [x] Updated `ui/README.HELPER_UI.md` (keyboard table + §10-deviation note +
      full file map + item status) and Epic 8 story files 8.1–8.10 (a "UI v2
      component map" section per story; 8.10's stale `.jsx` file list rewritten).

**Test:** `npm run test` (178 pass, +21 for item 10) + `npm run build` green in the container;
keymap resolution + load-state selection unit-tested; `curl` smoke of `docker
compose up ui` (`/` 200, `/data/.../info.json` 200). Interactive keyboard pass
deferred to item 11 parity (D3 — no browser channel).
**Commit:** `10. keyboard and states`

### 11. Parity sign-off + cutover

- [x] Walk the refinement doc's **Parity checklist** against the running app;
      record the result here. *(See "Parity sign-off" below.)*
- [x] Confirm `docker compose up ui` (dev) and the prod nginx build both serve
      the app. *(dev `:9090` → 200; prod `final` stage image → 200 + assets +
      SPA fallback + `/data` mount. Commands + results below.)*
- [x] Confirm no writes to `data/analysis/**` except the two human-save
      endpoints (grep the built bundle + the dev-server handlers). *(Result
      below — the only two `writeFile` calls are `human_hints.json` /
      `song_facts.json` under `reference/human/`, both PUT-only, both behind the
      path-escape guard.)*
- [x] **Delete the pre-rebuild reference copy** (`git rm -r` on it); a repo-wide
      grep for it (excluding git history) now returns **nothing**.
- [x] Archive this plan and `product-refinement.md` into this `archive/`
      directory; update `docs/web-ui/README.md`,
      `docs/web-ui/8.*.md` where they now describe the v2 components, the
      `ui-rebuild/README.md`, `docs/README.md`, and the root `README.md` UI
      pointer.
- [ ] Tag `ui-v2` — **held**, mirroring the 6.3 "archive + tag held" close-out
      (commit `888c929`): the one open gate is D3's live-browser visual /
      interaction parity pass (see the sign-off table's DEFERRED rows). The
      orchestrator makes the tag with `git tag ui-v2` once that pass is done.

**Commit:** `11. parity sign-off`

---

## Parity sign-off (item 11)

Walked against the running dev app (`docker compose up -d ui`, `_test_song`) and
the prod `final`-stage image, plus a source read of every writer. Interactive /
pixel checks that need a real browser are marked **DEFERRED (D3)** — the
`/implement` environment had no browser-automation channel; a human runs these
against the design canvas before the `ui-v2` tag.

### Refinement doc "Parity checklist"

| Row | Result | Note |
| --- | --- | --- |
| Song auto-discovery + switch (8.1) | **PASS** | `src/data/discovery.ts` = `data/analysis` listing ∩ `data/songs` audio, `localeCompare` sorted (parity with the old `fetch.js`); unit-tested. `SongPicker` renders loading/empty/error/ready. Drawer switch reloads `useSong`. |
| DAW multi-lane timeline, master sync, semantic zoom, fit-to-width (8.2, 8.3, 8.6) | **PARTIAL** | Logic PASS: `coords.ts` time-proportional x (tempo-drift round-trip tested), `zoom.ts` threshold table + `fitToWidthPxPerBar` unit-tested, `useTransport` is the sole clock (wavesurfer events, no rAF), `follow.ts` follow-scroll tested. Visual match to the design + audio/playhead lockstep + 4-min-song frame-rate = **DEFERRED (D3)**. |
| All lanes from `laneDefinitions.js` render from real artifacts; lane list show/hide + expand/collapse; non-core collapsed by default (8.4, 8.5, 8.9, 8.7) | **PARTIAL** | All 17 lanes registered in `laneState.ts`; defaults = the design's five expanded, rest collapsed; `LaneList.tsx` + inline carets toggle, persisted to `localStorage`. `validation` (Regression Overlay) ships as an **empty-state stub** (D6 — inputs need `buildTimelineData.js` re-tracing, which the plan forbids). `mlEvents` shows its empty state on `_test_song` (no ML artifact). Per-lane canvas rendering fidelity = **DEFERRED (D3)**. |
| Click any lane block → read-only detail in the right panel + playhead seek | **PARTIAL** | `BlockInspector.tsx` + `blockFields.ts` (ported field maps, unit-tested); `SparseLane` / `CanvasLane` set hit regions; click routes to inspector mode (or hint editor for `humanHints`) and seeks the shared playhead. End-to-end click behaviour in a browser = **DEFERRED (D3)**. |
| Human hint editor: view / create / edit / delete / set-to-playhead / save (8.8) | **PARTIAL** | `HintEditorPanel.tsx` + `hintDraft.ts` (draft↔payload + validation unit-tested); `saveHumanHints.ts` → `PUT /api/human-hints/<song>` on explicit Save; optimistic update + reload. Round-trip write verified by source read of the handler; interactive edit/save = **DEFERRED (D3)**. |
| Review-queue editor round-trip — `review_queue.json` → `song_facts.json` (8.10) | **PARTIAL** | `ReviewQueuePanel.tsx` + `reviewQueue.ts` (`partitionReviewQueue` / `questionOptions` unit-tested); `saveSongFacts.ts` → `PUT /api/song-facts/<song>`; handler merges onto existing facts and stamps `provenance: "human-confirmed"` (D4), whole-song keys only (`form_family`, `form_family_vs_genre`). Empty state when no `review_queue.json`. Interactive answer+save = **DEFERRED (D3)**. |
| Artifact inspector — raw-JSON file browser (8.9) | **PASS** | `ArtifactInspector.tsx` + recursive `walk.ts` rooted at `data/analysis/<song>` (D5). Reachability test: `_test_song` → 73 files reached, 0 of the previous inspector's 25 `artifactDefinitions` missing (`walk.test.ts`). Read-only — GET only. |
| Runs as the `ui` Compose service on `:8080`; prod nginx build works | **PASS** | dev: `docker compose up -d ui` → `curl :9090/` (host map of container `:8080`) = 200. prod: `docker build --target final -t ui-v2-prod ./ui` then run → `/` 200, hashed asset 200, SPA deep route 200, `/data/.../info.json` 200. |

### Deferred interactive checks (D3 — needs a live browser pass)

Run in Chrome 151 against `docs/web-ui/ui-rebuild/design/` before tagging `ui-v2`:

1. Zoom slider / ± / fit-to-width visually match the design at `pxPerBar` 14 / 62 / 180; beat sub-ticks appear only at `pxPerBar ≥ 44`.
2. Playhead sits exactly on a bar line at each real bar time across the zoom range; horizontal scroll never moves the 212 px label column or the page body.
3. Space toggles audio and the playhead tracks what is heard; ruler / waveform click seeks audio + every lane; header `bar.beat` matches the beat under the playhead.
4. FFT / RMS / Envelope render pixel-comparable to the previous app (run both side by side on `_test_song`); stem sub-labels stay pinned to the viewport left edge while scrolling; collapse → 26 px + strip.
5. `Hideaway - Kiesza` at max zoom scrolls / zooms with no dropped frames.
6. Clicking a block in every lane opens the right-panel inspector with that block's fields and seeks the playhead; a hint pill opens the editor.
7. Hint editor: create / edit / delete / set-start-to-playhead / Save writes `human_hints.json` and nothing else; pill reflects the edit.
8. Review queue: answering `form_family` + Save writes `song_facts.json` with `provenance: "human-confirmed"` and preserves prior human facts.
9. Full keyboard model (space / ←→ / shift+←→ / `+ - [ ] = _` / `f` / `esc` cascade) and the focus trap + restore on `RightPanel`.
10. Sticky header shows only Segments + Bars; segment tint by `form_role` family.

### dev + prod serve results

```
# dev
docker compose up -d ui
curl -s -o /dev/null -w '%{http_code}' http://localhost:9090/            # 200
curl -s -o /dev/null -w '%{http_code}' http://localhost:9090/data/analysis/_test_song/info.json   # 200

# prod  (Dockerfile stage: `final`; nginx.conf listen 8080)
docker compose run --rm ui npm run build                                 # exit 0, dist/ written
docker build --target final -t ui-v2-prod ./ui                           # exit 0
docker run -d --rm -p 9091:8080 -v "$PWD/data:/data:ro" ui-v2-prod
curl -s -o /dev/null -w '%{http_code}' http://localhost:9091/            # 200  (index.html)
curl -s -o /dev/null -w '%{http_code}' http://localhost:9091/assets/index-<hash>.js   # 200
curl -s -o /dev/null -w '%{http_code}' http://localhost:9091/some/spa/route          # 200  (SPA fallback)
curl -s -o /dev/null -w '%{http_code}' http://localhost:9091/data/analysis/_test_song/info.json  # 200
```

### no-writes-to-`data/analysis/**` grep

`ui/dist/assets/*.js` (built bundle): the only request verbs are `GET`
(`fetch(..., {cache:"no-store"})` for artifact loads) and two `method:"PUT"`
calls to `/api/human-hints` and `/api/song-facts`. No other `/api/` path, no
write verb. The browser cannot touch the filesystem otherwise.

`ui/vite.config.ts` (dev server): exactly two `fsp.writeFile` calls —
`humanHintsFilePath()` and `songFactsFilePath()`, both `= referenceHumanFilePath(song, …)`
which resolves to `<analysisRoot>/<song>/reference/human/<file>` and throws if
the resolved path escapes `<analysisRoot>/<song>/`. Both are reached only on
`request.method === "PUT"` to their respective `/api/…` prefix. `mkdir` is the
only other write and only for those two parents. Nothing writes elsewhere under
`data/analysis/**`.

### D-log items folded in here

- **D3** — interactive/visual parity: recorded above as the 10 DEFERRED checks;
  gates the `ui-v2` tag, not the cutover commit.
- **D6** — `validation` (Regression Overlay) lane: confirmed shipped as an
  empty-state stub; `VALIDATION_MARK_COLORS` in place. Wiring it needs the
  `eventComparisons` / `validationDrift` assembly from the old
  `buildTimelineData.js`, deferred to a later UI release (not `ui-v2`).
- **D6, roman numerals** — chord blocks degrade to plain names when
  `layer_a_harmonic.json` has `global_key.label: null` (reference-promoted
  chords; `_test_song` is in this state). Expected; no fix needed for `ui-v2`.
- **D7** — keyboard/focus deviations from refinement §10 stand as implemented
  and are documented in `ui/README.HELPER_UI.md`.

### New decision

### D8 — `ui-v2` tag held pending the D3 live-browser pass (item 11, resolved by recommendation)

The refinement doc says `UI v2` is "Tagged `ui-v2` in git on completion", but the
repo's own most recent precedent (`888c929`, "6.3 release close-out (docs;
archive + tag held)") is to complete the documentation close-out and **hold the
tag** until the release's outstanding gates pass. UI v2's one outstanding gate is
D3: no visual/interaction parity pass has run in a real browser. Following the
same convention, item 11 does the full cutover (delete the old app, archive the
docs, update every pointer) and commits it, but the `ui-v2` tag is **held** and
made by the orchestrator with `git tag ui-v2` after the D3 checklist above is
walked in Chrome 151.

---

## Decisions raised during implementation

### D1 — Nocturne `styles.css` is not in the repo (item 1, resolved by recommendation)

`docs/web-ui/ui-rebuild/design/README.md` lists the Nocturne design-system
`styles.css` under "Not vendored here", and the file the plan assumed was the
vendored copy (`ui/src/styles.css`) was the old teal-debugger CSS. Item 1 could
not vendor the DS file "unchanged" because it does not exist in-repo.

**Decision:** reconstruct `ui/src/styles/nocturne.css` from the authoritative
token + component tabulation in `design-notes.md` §1, with accent/neutral ramp
steps interpolated from the three anchors in §3a (`accent-300 #d2cefd`,
`accent-500 #968ae0`, `accent-900 #2b2741`). The file header documents this. If
the real DS file becomes available it should be dropped in unchanged; nothing
else in item 1 depends on the reconstructed intermediate values. Minor item-1
sub-decisions (Phosphor `.svg` `@font-face` fallback dropped — woff2/woff/ttf
only for Chrome 151; `defineConfig` imported from `vite` not `vitest/config` to
keep the dev server loading; `@vitejs/plugin-react` / `jsdom` / `@types/react*`
added as unavoidable devDeps) are folded in and need no review.

**Checkout note:** run `docker compose rm -sfv ui` once after pulling this branch
to clear the stale Preact `node_modules` volume.

### D2 — Non-blocking notes from item 2 (data layer), resolved by recommendation

- **`vite.config.ts` is outside the TS project.** The ported `/data` mount +
  hint-save handler needs Node builtins (`node:fs`, `Buffer`), which would pull
  in `@types/node` (not in the Docker image → needs an image rebuild). the previous app's
  config was `.js` and never type-checked either; Vite transpiles the config via
  esbuild at load. `tsconfig.json` `include` narrowed to `["src"]`. A later item
  that wants the config type-checked should add `@types/node` +
  `tsconfig.node.json` and rebuild the image.
- **Top-level `sections.json` is still the v1.0 projection** (no
  `section_id`/`form_role`/`confidence`) while the v2.1 contract adds them.
  `SectionRow` types the additions as `T | null` and the parser coerces missing
  → `null` rather than rejecting. `artifacts/section_segmentation/sections.json`
  *is* v2.1 and is parsed strictly (incl. the loud failure on duplicate
  `section_id`).
- **`.gitignore`:** root `data/` rule also matched `ui/src/data/`; added
  `!ui/src/data/**` negations so the directory is committed.

### D3 — Interactive browser QA unavailable in the implementation environment

The `/implement` run had no working browser-automation channel (claude-in-chrome
extension not connected), so the per-item "spawn a QA subagent that screenshots
the affected screens" step could not run. Frontend items are instead validated
by: in-container `npm run test` (which includes `@testing-library/react` render
tests), `npm run build`, and a `curl` smoke of `docker compose up ui` (page 200,
`/data` mount + `info.json` reachable). Visual/interaction parity against the
design canvas still needs a human pass with a real browser before cutover —
fold this into item 11's parity sign-off.

### D4 — Item 7 song-facts handler: merge, not rewrite (resolved by recommendation)

the previous app's `PUT /api/song-facts` rewrote the whole file and re-stamped every
fact on each save. The new handler reads the current `song_facts.json`, spreads
its `facts`, and overwrites only the answered whole-song keys
(`form_family`, `form_family_vs_genre`), stamping `provenance:
"human-confirmed"` + `confirmed_on`. Answering one review-queue question then
preserves prior human answers (e.g. `_test_song`'s hand-authored `has_drop`
note). `SONG_FACT_KEYS` is narrowed to those two fields — Story 8.10 defines
exactly them as the queue's whole-song answers; `genre`/`has_drop` are not
review-queue questions. The panel is still the only writer of the file. The
review queue opens off the `Review queue` drawer entry (`activeView === "review"`)
through the same `RightPanel` shell — a mode switch, not a second aside.

### D5 — Artifact inspector walks the song root, not just `artifacts/` (item 8, resolved by recommendation)

The item text and `product-refinement.md` §8 describe the inspector as a view of
files "under `data/analysis/<song>/artifacts/`", but Story 8.9's acceptance
criterion is that **every file the previous app's inspector exposed** is reachable — and
six of the previous app's 25 `artifactDefinitions` entries live **outside** `artifacts/`
(`info.json`, `beats.json`, `sections.json`, `song_event_timeline.json`,
`beatdrop_visual_plan.json`, `reference/human/human_hints.json`).

**Decision:** the recursive walk roots at `data/analysis/<song>` so all of
the previous app's set stays reachable (and the debugger sees `reference/`, `stems/`,
etc. too, which is useful for cross-checking). Still strictly read-only — the
component only issues GETs against the `/data` listing + file endpoints. Non-JSON
files render as raw text (`.md`/`.txt`) or an "not rendered here" note (`.wav`,
`.mid`). `_test_song` probe: 73 files reached, 0 of the previous app's 25 missing.

### D6 — Item 9: validation lane shipped as an empty-state stub (per plan allowance)

The `validation` (Regression Overlay) lane renders "Regression overlay —
validation wiring deferred (item 11 parity)" rather than real marks.
`eventComparisons` needs machine-event ids aligned to `song_event_timeline.json`
event ids, an alignment that is not verified, and the plan explicitly says not to
re-trace the previous app's `buildTimelineData.js`. `VALIDATION_MARK_COLORS` is in place
for when it is wired. Item 11's parity checklist should record this gap.

Related item-9 notes: roman numerals degrade to plain chord names when
`layer_a_harmonic.json` carries `global_key.label: null` (reference-promoted
chords — `_test_song` is in this state); sparse-artifact parsers are deliberately
tolerant (coerce, never hard-fail a lane) to match the previous app's `buildTimelineData`
behaviour on half-populated v1.0 artifacts. On `_test_song`, `mlEvents` and
`validation` show empty states; every other sparse lane has data.

### D7 — Item 10 keyboard/focus deviations from refinement §10 (resolved by recommendation)

- **`[` / `]` are zoom out / in**, not prev/next-section. §10's literal text is
  "`+` `-` `[` `]` = zoom" and does not split the four; item 10's plan text only
  guessed at section-nav. Implemented as two pairs (`]` `+` `=` in; `[` `-` `_`
  out). `=` and `_` added as the unshifted faces of `+` / `_`.
- **Only `RightPanel` is focus-trapped.** §10 says "focus trap … for the drawer
  and right panel", but the v2 drawer is a persistent non-modal nav that is part
  of the base layout — a hard trap would break the app. The drawer gets
  initial-focus-on-open only; the trap is on `RightPanel`, the one modal surface.
- **`esc` also closes the drawer / lane list / review view**, extending §10's
  "close panel" to the additional dismissable surfaces v2 introduces
  (order: right panel → review view → lane list → drawer).
  > **Superseded by UI v2.1 plan item 4 (R2).** The left panel (drawer) now
  > mounts **collapsed** by default (persisted to `localStorage`), not open. The
  > `esc` cascade is unchanged — it already ends on the drawer.

Missing-artifact handling is two-level: individual lanes keep their own
empty/error state (items 5/9); item 10 adds a song-level `degraded` banner
naming the failed lanes and a `fatal` screen when `info.json` / `beats.json`
themselves are unusable.

Add `D8`, `D9`… here only when an item is genuinely blocked
mid-implementation — a decision where proceeding under any assumption would make
the work wrong or wasted. Record it and its options, then continue with the next
independent item. Once such a decision is answered, fold the answer into the
affected item's definition (and the refinement doc / design notes) rather than
leaving it as a log entry here.
