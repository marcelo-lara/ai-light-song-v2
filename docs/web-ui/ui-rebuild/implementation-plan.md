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

- **The old app moves to `ui.old/` in item 1's commit** (not deleted yet) and is
  the **behaviour reference** for the whole rebuild — read
  `ui.old/src/app/*`, `ui.old/src/components/*`, `ui.old/src/lib/*`,
  `ui.old/vite.config.js` to learn the data API, discovery logic, hint-editor
  rules and semantic-zoom thresholds, then write the new code fresh at `ui/`.
  `ui.old/` is **deleted at cutover (item 11)**, and after that there must be
  **zero references to it** anywhere in the repo.
- Design source of truth:
  [`design/design-notes.md`](design/design-notes.md) and
  [`design/Score-Analysis-DAW.dc.html`](design/Score-Analysis-DAW.dc.html).
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
| 9 | All remaining lanes (sparse + validation), collapsed by default | R9 | ☐ |
| 10 | Keyboard, states, polish | R10 | ☐ |
| 11 | Parity sign-off + cutover | — | ☐ |

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
- [x] **`git mv ui ui.old`**, then scaffold the new tree at `ui/`, **in this
      same commit**. `ui.old/` is the reference copy for items 2–10 and is
      deleted at cutover (item 11).
- [x] `ui/Dockerfile` (dev Vite stage + prod nginx stage) and `ui/nginx.conf`
      written for the new build output; `esnext` build target (Chrome 151).
      Compose `ui` service + port unchanged (still builds from `ui/`). No compose
      service for `ui.old/`.
- [x] `ui/README.HELPER_UI.md` written for the new file map.

**Test:** `npm run build` + `npm run test` pass in the container; `docker compose
up ui` serves the empty shell at `:8080` matching the design's frame; `grep -E
'preact|@mui|@emotion' ui/package.json` is empty; `ui.old/` still present.
**Commit:** `1. fresh app shell`

### 2. Data layer — typed artifact access

- [x] Port to `vite.config.ts`: the `/data` static mount + directory listing and
      `PUT /api/human-hints/<song>` handler from `ui.old/vite.config.js`
      (byte-for-byte behaviour, including the path-escape guard).
- [x] `src/data/types.ts` — TS types for every artifact the UI reads, mirroring
      the v1.1 contracts (`docs/web-ui/7.2.build_ui_data_story.md`,
      `docs/source references/contract-change-v1.1.md`).
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
      the validation `ui.old`'s hint editor enforced.

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
> `ui.old/src/lib/timeline/fftBandsLane.js`, `loudnessLane.js`,
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
      (`#968ae0` / `#d2cefd`) per design notes §3a — not `ui.old`'s teal.
- [x] `drums` (kick/snare/hat density) and `energy` (beat-aligned energy +
      accent candidates) lanes ported from `ui.old/src/lib/timeline/drumsLane.js`
      / `seriesLane.js`, **collapsed by default**. Discrete markers (accent
      candidates) get hit regions → block inspector (item 6).
- [x] Each lane renders its own loading / empty (artifact missing) / error state.

**Test:** `palette.ts` + renderer geometry helpers (row edges, bucketing,
sub-label x) unit-tested; manual: FFT / RMS / Envelope render **pixel-comparable
to `ui.old`** (run both) side by side against `_test_song`; sub-labels stay put
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
      map ported from `ui.old/src/lib/timeline/sparseContent.js` +
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
- [x] Replaces `ui.old`'s floating `OverlayPanel` — block detail lives
      in the right panel, not a popover.

**Test:** `blockFields` mapping + hint draft↔payload + validation unit-tested;
manual: clicking a section / chord / machine-event block opens a read-only card
with the right fields and seeks the playhead; a hint block opens the editor;
edit + save writes `human_hints.json` and nothing else writes it.
**Commit:** `6. right panel — inspector and hint editor`

### 7. Review-queue editor — right-panel third mode  *(functional v1)*

A working first version — deeper iteration is a later release.

- [x] Port `PUT /api/song-facts/<song>` handler into `vite.config.ts` (from the
      `ui.old/vite.config.js`).
- [x] `src/panel/ReviewQueuePanel.tsx` — renders
      `artifacts/validation/review_queue.json` as ranked questions; whole-song
      answers (`form_family`, `form_family_vs_genre`) → `song_facts.json` on
      explicit Save; per-section / drop questions shown read-only for context.
      Opened from a drawer entry (no lane).
- [x] Third mode in the item-6 shell (mode switch, not a second aside).
- [x] Empty state when a song has no `review_queue.json` (not yet analysed under
      v1.1) — the panel says so rather than erroring.

**Test:** as Story 8.10 — answering `form_family` + Save writes `song_facts.json`
with `provenance: "human-confirmed"`; nothing else writes it; a song without a
review queue shows the empty state.
**Commit:** `7. review queue editor`

### 8. Artifact inspector

- [x] `src/inspector/ArtifactInspector.tsx` — drawer entry / bottom sheet that
      lists the song's `artifacts/**` files and renders a selected JSON with
      collapsible nodes + copy-path, styled with Nocturne `.table` / `.card`.
      Read-only. *(See D5: the walk roots at `data/analysis/<song>` rather than
      `artifacts/` so ui.old's non-`artifacts/` inspector files stay reachable.)*
- [x] Reachability check against `ui.old`'s inspector file set (Story 8.9) — all
      25 files ui.old's inspector exposed resolve through the recursive walk
      (`_test_song`: 73 files reached, 0 missing).

**Test:** manual: every artifact `ui.old`'s inspector exposed is reachable and
readable; no write path.
**Commit:** `8. artifact inspector`

---

## Phase D — Remaining lanes, polish, cutover

### 9. All remaining lanes — sparse + validation

Every lane in `ui.old/src/lib/config/laneDefinitions.js` ships (no conductor /
tempo / "global" strip — that stays removed). This item does the sparse lanes
and the regression overlay; FFT/RMS/Envelope/drums/energy are item 5.

- [ ] `src/timeline/SparseLane.tsx` — a reusable block-lane body: builds hit
      regions from a per-lane content adapter, draws Nocturne-tinted rounded
      blocks with a label (+ caption when wide), row-packs overlapping blocks
      (the `identifierHints` / `machineEvents` / `mlEvents` / `phrases`
      compaction from `sparseLane.js`), sets hit regions for item 6.
- [ ] `src/timeline/laneContent.ts` — the per-lane content adapters ported from
      `ui.old/src/lib/timeline/sparseContent.js`: `humanHints`, `sections`, `chords`
      (name + roman numeral, roman only when wide), `patterns`,
      `identifierHints`, `machineEvents`, `mlEvents`, `beatdropPlan`, `phrases`.
      Each yields `{ start_s, end_s, label, laneLabel, caption, reference,
      detail, summary, … }` for the block inspector.
- [ ] `validation` (Regression Overlay) — port `validationLane.js` **best
      effort**: beat-drift + exported-event comparison marks, discrete marks
      clickable → block inspector. Its inputs (`eventComparisons`,
      `validationDrift`) are assembled in `ui.old`'s `buildTimelineData.js` from
      validation artifacts — **don't spend time re-tracing them**: if the data
      isn't readily available, ship the lane as an empty-state stub and note it
      in the parity checklist. (Absorbs Story 8.7.)
- [ ] Per-lane Nocturne tint set (replaces `sparseLaneStyles`) — keep the current
      hue assignments (hints amber, sections teal, chords cyan, patterns gold,
      identifiers blue, machine red, ml violet, beatdrop orange) but move the
      values onto ramp steps / documented locals.
- [ ] **Default state:** all lanes in this item start **collapsed**
      except `humanHints` (expanded). Every lane is show/hide + expand/collapse
      from the lane list (item 3).
- [ ] Clicking a block → item 6 block inspector (read-only), except `humanHints`
      → hint editor. Clicking a block also seeks the playhead to its start.

**Test:** `laneContent` adapters unit-tested against artifact fixtures; manual:
every lane renders and toggles; chord blocks align to bars on `_test_song`;
clicking a block in each lane opens the right-panel inspector with that block's
fields; the sticky header shows only Segments + Bars.
**Commit:** `9. remaining lanes`

### 10. Keyboard, states, polish

- [ ] Keyboard: space / ←→ / shift+←→ / `+ - [ ]` / `f` / `esc` (refinement §10).
- [ ] Loading / empty / error states for the song list and a song with missing
      artifacts.
- [ ] Focus management for the drawer and right panel.
- [ ] Update `ui/README.HELPER_UI.md` and the affected Epic 8 story files
      (8.1–8.10) to the new component names and file map.

**Test:** `npm run test` + `npm run build`; manual: full keyboard operation; a
checkout with no analysed songs shows an empty state, not an error.
**Commit:** `10. keyboard and states`

### 11. Parity sign-off + cutover

- [ ] Walk the refinement doc's **Parity checklist** against the running app;
      record the result here.
- [ ] Confirm `docker compose up ui` (dev) and the prod nginx build both serve
      the app.
- [ ] Confirm no writes to `data/analysis/**` except the two human-save
      endpoints (grep the built bundle + the dev-server handlers).
- [ ] **Delete `ui.old/`.** Then `grep -rn 'ui\.old' .` (repo-wide, excluding
      git history) returns **nothing** — no doc, compose file, script or comment
      references it.
- [ ] Archive this plan and `product-refinement.md`; update
      `docs/web-ui/README.md`, `docs/web-ui/8.*.md` where they now describe the
      v2 components, and the root `README.md` UI pointer.
- [ ] Tag `ui-v2`.

**Commit:** `11. parity sign-off`

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
  in `@types/node` (not in the Docker image → needs an image rebuild). `ui.old`'s
  config was `.js` and never type-checked either; Vite transpiles the config via
  esbuild at load. `tsconfig.json` `include` narrowed to `["src"]`. A later item
  that wants the config type-checked should add `@types/node` +
  `tsconfig.node.json` and rebuild the image.
- **Top-level `sections.json` is still the v1.0 projection** (no
  `section_id`/`form_role`/`confidence`) while the v1.1 contract adds them.
  `SectionRow` types the additions as `T | null` and the parser coerces missing
  → `null` rather than rejecting. `artifacts/section_segmentation/sections.json`
  *is* v1.1 and is parsed strictly (incl. the loud failure on duplicate
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

`ui.old`'s `PUT /api/song-facts` rewrote the whole file and re-stamped every
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
criterion is that **every file `ui.old`'s inspector exposed** is reachable — and
six of `ui.old`'s 25 `artifactDefinitions` entries live **outside** `artifacts/`
(`info.json`, `beats.json`, `sections.json`, `song_event_timeline.json`,
`beatdrop_visual_plan.json`, `reference/human/human_hints.json`).

**Decision:** the recursive walk roots at `data/analysis/<song>` so all of
`ui.old`'s set stays reachable (and the debugger sees `reference/`, `stems/`,
etc. too, which is useful for cross-checking). Still strictly read-only — the
component only issues GETs against the `/data` listing + file endpoints. Non-JSON
files render as raw text (`.md`/`.txt`) or an "not rendered here" note (`.wav`,
`.mid`). `_test_song` probe: 73 files reached, 0 of `ui.old`'s 25 missing.

Add `D6`, `D7`… here only when an item is genuinely blocked
mid-implementation — a decision where proceeding under any assumption would make
the work wrong or wasted. Record it and its options, then continue with the next
independent item. Once such a decision is answered, fold the answer into the
affected item's definition (and the refinement doc / design notes) rather than
leaving it as a log entry here.
