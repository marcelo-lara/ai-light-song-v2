# Product Refinement — Web UI Rebuild (UI v2)

Active worklist for a **from-scratch rebuild** of the internal artifact debugger
in `ui/`. Items here are scoped and ready to be turned into
[`implementation-plan.md`](implementation-plan.md).

## Version convention

`UI v2` is the version of the **debugger web app** — a separate component from
the analyzer module (whose current release is `v1.1`). It has no bearing on the
analyzer's version or on any artifact `schema_version`. The rebuild consumes the
analyzer's published contracts as they stand after `v1.1`; it does not change
them.

| Carrier | Rule |
| --- | --- |
| App release | `UI vN`. This work produces `UI v2`. Tagged `ui-v2` in git on completion. |
| Refinement doc | this file. |
| Implementation plan | [`implementation-plan.md`](implementation-plan.md), archived when the rebuild ships. |
| Story specs | the Epic 8 story files in `docs/web-ui/8.*.md` are updated in the item that changes their behaviour; new panels get new story files. |

## Release goal

Replace the current Preact + MUI debugger with a **React + TypeScript** app that
**is** the "Score Analysis DAW" design
([`design/design-notes.md`](../design/design-notes.md)) — same layout, the Nocturne
visual language, a canvas multi-lane timeline, and **wavesurfer.js** as the audio
player and master clock — while keeping **every** working capability at parity:
song discovery, **all current lanes** (the design's five expanded, the rest
collapsed by default), semantic zoom, click-any-block → read-only detail in the
right panel, the artifact inspector, and the human-hint editor.

The rebuild starts in a **fresh `ui/` tree**. The current app is not migrated
file-by-file; its behaviour is the parity reference and its dev-server data API
(`/data` mount + `PUT` endpoints) is kept.

### Constraints that do not change

- **Internal debugger only.** The constitution's rule stands: this UI must not
  become a production-facing consumer experience. Read-only against
  `data/analysis/**` except the two explicit human-save paths
  (`reference/human/human_hints.json` and `reference/human/song_facts.json`).
- Its own Compose `ui` service, port `8080`, not folded into the analyzer
  container.
- Every colour / font / space / radius / shadow comes from Nocturne's
  `styles.css` tokens. Phosphor icons throughout.
- **Target browser: Chrome 151** (the operator's browser) — no cross-browser
  support, polyfills or autoprefixer; modern CSS/JS used freely.
- The current app was moved to a reference copy in item 1 and kept as the behaviour
  reference until cutover (item 11), then deleted — with **no lingering
  references** anywhere in the repo.
- Timeline x is **time-proportional** (`x = t · pxPerSec`), so lanes, the
  playhead and wavesurfer share one time→x mapping and bars may be unequal width
  when the tempo drifts.

---

## 1. Fresh app shell — React + TS + Vite

**Intent.** One predictable stack. The current app mixes Preact, MUI, `@emotion`,
and a hand-rolled imperative timeline; the rebuild is plain React 18 with
TypeScript and Vite, Nocturne CSS, and a small number of focused components.

**Change.**

- New `ui/` tree: `package.json` (React 18, `react-dom`, `wavesurfer.js` v7,
  `@phosphor-icons/web`, `vite`, `typescript`, `vitest`, `@testing-library/react`),
  `tsconfig.json`, `vite.config.ts`, `index.html`, `src/`.
- `src/styles/nocturne.css` — Nocturne's stylesheet vendored **unchanged**;
  `src/styles/daw.css` — the interface-local classes from the canvas
  (`.tp`, `.zbtn`, `.caret`, `.dr-item`, range/scrollbar), ported to tokens.
- Vendor Phosphor's regular-weight CSS + font locally (no unpkg at runtime).
- The current app was moved to a reference copy in item 1's commit and removed at cutover (item 11); there are now **no references to it** anywhere.
- `ui/Dockerfile` (dev Vite stage + prod nginx build stage) and
  `ui/nginx.conf` updated for the new build output; the Compose `ui` service and
  port are unchanged.

**Acceptance.** `docker compose up ui` serves the shell at `:8080`; `npm run
build` and `npm run test` pass in the container; no Preact/MUI/@emotion left in
`package.json`.

## 2. Data layer — typed artifact access over the existing API

**Intent.** Every lane reads a real artifact. The access layer is typed and
central so a lane component never fetches ad-hoc.

**Change.**

- Keep the dev-server middleware pattern in `vite.config.ts`: static `/data`
  mount + directory listing, `PUT /api/human-hints/<song>`, and
  `PUT /api/song-facts/<song>` (added by item 7). Port the existing handlers to
  the new config.
- `src/data/` — one typed loader per artifact the UI reads (`info.json`,
  `beats.json`, `sections.json` top-level + `section_segmentation/sections.json`,
  `essentia/fft_bands.json`, `essentia/rms_loudness.json`,
  `essentia/loudness_envelope.json`, `layer_a_harmonic.json`,
  `reference/human/human_hints.json`, `song_event_timeline.json`,
  `artifacts/validation/review_queue.json`). TypeScript types mirror the v1.1
  contracts (`docs/web-ui/7.2.build_ui_data_story.md`,
  `docs/source references/contract-change-v1.1.md`).
- A `useSong(songName)` hook: loads `info.json` + the artifacts the visible lanes
  need, exposes `{ status, data, error }` per artifact so lanes render their own
  loading / missing / error state.
- Song discovery: `data/analysis` listing ∩ `data/songs` audio files, as today.

**Acceptance.** Switching songs in the drawer reloads all lanes; a song with a
missing artifact shows that lane's empty state, not a crash.

## 3. Timeline shell — grid, rulers, zoom, playhead, lane list

**Intent.** The scrolling DAW surface from the design: a sticky 212 px lane-label
column, sticky Segments + Bars header rows, `pxPerBar` zoom (14–180), fit-to-width,
one playhead across all lanes, and a lane list to show/hide and expand/collapse
each lane.

**Change.**

- `src/timeline/TimelineGrid.tsx` — the CSS grid (`212px max-content`), sticky
  headers, the shared bar/4-bar grid lines, the accent playhead (1 px line +
  glow + caret).
- `src/timeline/laneState.ts` — the lane registry (id, label, sub-caption,
  `kind`, `expanded`, `visible`). Default `expanded`: the design's five
  (`waveform`, `humanHints`, `fftBands`, `rmsLoudness`, `loudnessEnvelope`);
  every other lane collapsed. Persist `expanded` / `visible` per session
  (`localStorage`, try/catch).
- `src/timeline/LaneList.tsx` — show/hide + expand/collapse any lane; each lane's
  inline caret toggles the same state.
- Coordinate helpers (`beatToX`, `xToBeat`, `timeToBeat` via the real beat grid).
- `pxPerBar` state + footer zoom slider / ± buttons / fit-to-width; the
  semantic-zoom thresholds from the design notes §2.
- Follow-playhead scroll while playing (scroll so the playhead sits at 55% once
  it passes `viewport − 120 px`).
- Bars ruler from `beats.json`: **always** a per-bar minor tick + a taller tick
  and number label every *N* bars (*N* by zoom); **beat sub-ticks only when not
  crowded** (`pxPerBar ≥ 44`). Click-to-seek → wavesurfer. Sticky header area is
  **only Segments + Bars** — no conductor/tempo strip.
- `coords.ts` — **time-proportional**: `x = t · pxPerSec`,
  `pxPerSec = pxPerBar / medianBarSeconds`; bar lines at each bar's real start
  time; `timelineW = duration · pxPerSec`. `pxPerBar` (14–180) stays the zoom
  control and label.
- Segments header: HTML blocks from the top-level `sections.json` list,
  positioned by `start`/`end` seconds, tinted by `form_role` family
  (chorus/drop/hook = accent, else neutral), `form_role` + `N bars` label with
  the width-based truncation from the design (bar count hidden when narrow). The
  `sections` sparse lane (item 9) **also** renders — header and lane both stay
  for now.

**Acceptance.** Zoom and fit-to-width match the design; the playhead sits on a
bar line at every real bar time across the zoom range (verified with a
tempo-drift fixture); beat sub-ticks appear/disappear at the zoom threshold;
horizontal scroll never moves the sticky label column or the page body.

## 4. wavesurfer.js — audio, waveform lane, master clock

**Intent.** wavesurfer owns audio playback and the Waveform Anchor lane, and its
`currentTime` is the **only** clock; every other lane and the playhead follow it.

**Change.**

- `src/timeline/WaveformLane.tsx` wraps a wavesurfer v7 instance bound to
  `data/songs/<song>.mp3`, container width `timelineW`, blurple wave colours
  (design notes §3a), its own cursor disabled (the shell draws the playhead).
- A `useTransport` hook: `currentTime` state fed by `wavesurfer.on('audioprocess')`
  / `'seeking')` / `'interaction'`; exposes `play/pause`, `seekTo(time)`,
  `seekToBeat`, `stepBeat(±1)`, `stepBar(±1)`, `isPlaying`, `duration`.
- Header transport cluster + centre readout (`m:ss.s / total`, `bar.beat`) bind
  to this hook. No `requestAnimationFrame` position loop of our own.
- **First-load decode accepted:** no peaks artifact exists, so wavesurfer decodes
  the full mp3 on song load behind a loading state. A `/api/peaks` precompute
  endpoint is a later optimisation, out of scope for `ui-v2`.

**Acceptance.** Pressing space toggles audio and the playhead moves in lockstep
with what is heard; clicking the Bars ruler or a waveform position seeks the
audio and every lane; `bar.beat` in the header matches the beat under the
playhead.

## 5. Dynamic data lanes — FFT, RMS, Envelope (+ drums, energy)

**Intent.** The **continuous** lanes (the sparse/block lanes and click→inspector
wiring are items 9 and 6). Each backed by its real artifact, each with
collapse-to-strip. The FFT / RMS / Envelope **fill palette and stem sub-labels
are carried over verbatim from the previous app** (design notes §3a) —
the user has confirmed that rendering is good and wants it kept; only the
surrounding chrome changes to Nocturne. `drums` and `energy` are ported here and
**collapsed by default**.

**Change.**

- `src/timeline/CanvasLane.tsx` — a reusable devicePixelRatio-aware `<canvas>`
  lane body: draws the shared grid, then delegates to a per-kind renderer.
  Redraws on `pxPerBar` / collapse / resize (ResizeObserver).
- Renderers — **ported from the previous app's `src/lib/timeline/`,
  not the canvas mock**, per design notes §3a (the mock's blurple lane colours
  are not used):
  - `wave` — handled by wavesurfer (item 4); tint its `waveColor` /
    `progressColor` to the current lane's teal (`rgba(15,118,110,·)`).
  - `fft` — per-band `hsla(hue, 84%, 58%, v·0.9)` heat with
    `FFT_BAND_HUES = [22, 46, 88, 138, 164, 186, 196]` (Sub→Brilliance, band 0
    at the bottom), `TRACK_HEIGHT` 84, visibility floor 0.02, per-bucket max.
  - `rms` — per-stem heat, `SOURCE_COLORS` = Mix `#FACC15` / Bass `#F87171` /
    Drums `#22D3EE` / Harmonic `#4ADE80` / Vocals `#C084FC`; alpha
    `0.16 + v·0.72`; `LANE_HEIGHT` 112.
  - `env` — per-stem filled area `rgba(stem, 0.18)` + stroke line
    `rgba(stem, 0.94)` `lineWidth 1.5`.
  - per-row background `rgba(148,163,184,0.06)` + `0.16` bottom rule.
- Stem sublabel chips (RMS / Envelope) — one per row, **anchored to the visible
  viewport's left edge** (`x = round(scrollStart·zoom) + 6`), `11px IBM Plex
  Mono`, text = stem colour, plain `rgba(10,18,28,0.68)` rect behind it (no
  border), label trimmed to 56 px. Exactly as design notes §3a.
- Human Hints lane: HTML pills from `human_hints.json` at `start_time`/`end_time`;
  width-based label/time/note truncation; selected pill accent-700/400; click →
  right panel (item 6).
- Lane header: name + sub-caption + collapse caret; collapsed lane = 26 px with
  the faint waveform strip summary.
  > **Superseded by UI v2.1 plan items 5 & 6.** Item 5 (R1): a *collapsed* lane
  > header renders the **title only** — the sub-caption line is not rendered
  > until the lane is expanded (the faint mini strip is unchanged). Item 6 (R5):
  > the collapse caret is anchored top-left at a fixed x/y so toggling
  > expand/collapse never moves it. Collapsed row height stays 26 px, now via
  > `collapsedLaneHeight()` (guaranteed ≥ the mini-strip height).

**Acceptance.** Each lane renders from its artifact; FFT / RMS / Envelope match
the previous app's palette and the scroll-following stem sub-labels
(design notes §3a) side by side with the previous app; collapsing a lane drops it to
26 px and redraws the strip; a 4-minute song at max zoom stays interactive (no
dropped frames on scroll/zoom on a mid-range laptop).

## 6. Right panel — shell + block inspector + hint editor

**Intent.** The design's 296 px right panel is one shell with **three modes**
(design notes §4). This item builds the shell, the read-only **block inspector**,
and the **hint editor**; item 7 adds the review-queue mode. It replaces the
the previous app's floating overlay — all block detail lives in the panel.

**Change.**

- `src/panel/RightPanel.tsx` — the mode-switching shell (header / body / footer),
  mount on `panelOpen`, outside-click + `esc` dismiss.
- **Block inspector (read-only).** Clicking any lane content block shows its
  `selection` payload: `label` heading, a Nocturne `<dl>` of fields
  (`laneLabel`, time range, `confidence`, `reference`/`id`, `section_id`,
  `created_by`, lane-specific fields), the `summary` line, and a "show raw"
  disclosure. **No inputs.** Also seeks the playhead to the block start.
  Field lists per lane ported from `sparseContent.js` / `selectionFields.js`.
- **Hint editor.** Clicking a Human Hints pill (or "new hint") opens this mode:
  Start / End / Title / Musical hint / Lighting hint (mapping in design notes
  §4b), ‹ › prev/next-hint, **new hint**, **delete active hint**, **set
  start/end to playhead**, Cancel / Save.
- Save issues `PUT /api/human-hints/<song>` (existing contract) on explicit Save
  only; optimistic update + reload; validation (id + title required, end ≥
  start, numeric times). Selecting / creating a hint scrolls the timeline to it.

**Acceptance.** Clicking a section / chord / machine-event / etc. block opens a
read-only card with that block's fields and seeks the playhead; a Human Hints
pill opens the editor; editing + saving writes `human_hints.json` and no other
path writes it; the panel matches the design.

## 7. Review-queue editor — right-panel third mode

**Intent.** The v1.1 human loop (Story 8.10) rebuilt into the new shell so
`review_queue.json` stays consumable and `song_facts.json` stays editable. A
**functional first version** — deeper iteration (richer question types, inline
evidence playback, bulk answering) is a following release.

**Change.**

- A third right-panel mode rendering `artifacts/validation/review_queue.json`
  as ranked answerable questions; whole-song answers (`form_family`,
  `form_family_vs_genre`) save to `song_facts.json` via
  `PUT /api/song-facts/<song>` on explicit Save. Opened from a drawer entry.
- Per-section / drop questions shown for context (answered via the hint editor).
- Port the `PUT /api/song-facts/<song>` dev-server handler from the current
  `vite.config.js`.

**Acceptance.** Same as Story 8.10: answering `form_family` and saving writes
`song_facts.json` with `provenance: "human-confirmed"`; nothing else writes it.

## 8. Artifact inspector

**Intent.** Parity with Story 8.9 — a raw view of the artifacts under
`data/analysis/<song>/artifacts/` for cross-checking what the lanes show.

**Change.**

- `src/inspector/ArtifactInspector.tsx` — a drawer entry (or bottom sheet) that
  lists the song's artifact files and renders a selected JSON with collapsible
  nodes and a copy-path action, styled with Nocturne `.table` / `.card`.
- Read-only. No editing.

**Acceptance.** Every artifact file the previous app's inspector exposed is reachable
and readable in the rebuild.

## 9. All remaining lanes — sparse + validation

**Intent.** Every lane in `laneDefinitions.js` ships. This item does the sparse
(block) lanes and the regression overlay; FFT / RMS / Envelope / drums / energy
are item 5. **No conductor / tempo / "global" strip** — removed, not rebuilt;
the sticky header is only Segments + Bars.

**Change.**

- `src/timeline/SparseLane.tsx` + `src/timeline/laneContent.ts` — a reusable
  block-lane body (Nocturne-tinted rounded blocks, label + caption, overlap
  row-packing) with per-lane content adapters ported from
  the previous app's `src/lib/timeline/sparseContent.js`: `humanHints`, `sections`, `chords`
  (name + roman numeral), `patterns`, `identifierHints`, `machineEvents`,
  `mlEvents`, `beatdropPlan`, `phrases`.
- `validation` (Regression Overlay) — beat-drift + exported-event comparison
  marks, clickable → block inspector. Absorbs Story 8.7. **Best effort:** if the
  inputs (`eventComparisons` / `validationDrift`, assembled in the previous app's
  `buildTimelineData.js`) aren't readily available, ship an empty-state stub and
  note it in the parity checklist — don't re-trace the pipeline for it.
- Per-lane Nocturne tint set replacing `sparseLaneStyles`, keeping the current
  hue assignments.
- **Default state:** every lane here starts **collapsed** except `humanHints`
  (expanded). All are show/hide + expand/collapse from the lane list (item 3).
- Clicking a block → item 6 block inspector (read-only) + playhead seek, except
  `humanHints` → hint editor.

**Acceptance.** Every lane renders and toggles; chords align to bars; clicking a
block in each lane opens the right-panel inspector with that block's fields; the
sticky header shows only Segments + Bars.

## 10. Keyboard, states, polish

**Intent.** The design has no keyboard model and no non-happy-path states.

**Change.**

- Keyboard: space = play/pause, ←/→ = step beat, shift+←/→ = step bar,
  `+`/`-`/`[`/`]` = zoom, `f` = fit, `esc` = close panel.
- Loading / empty / error states for the song list, each lane, and a song with
  missing artifacts.
- Focus management for the drawer and right panel; `:focus-visible` everywhere
  (Nocturne already themes it).
- `README.HELPER_UI.md` and the Epic 8 story files updated to the new file map
  and component names.

**Acceptance.** The app is fully operable from the keyboard; a fresh checkout
with no analysed songs shows a helpful empty state, not an error.

---

## Parity checklist (must hold before the pre-rebuild app is deleted)

> **Signed off in item 11.** The walk, results and the DEFERRED (D3) interactive
> checks are in `implementation-plan.md` → *Parity sign-off (item 11)*. Summary:
> discovery / artifact inspector / Compose+prod serve = **PASS**; the timeline,
> lanes, block inspector, hint editor and review-queue rows = **PARTIAL** (logic
> unit-tested and wired; a live-browser visual/interaction pass is the held gate
> for the `ui-v2` tag). `validation` (Regression Overlay) shipped as an
> empty-state stub (D6).

- [x] Song auto-discovery + switch (Story 8.1) — PASS
- [~] DAW multi-lane timeline, master sync, semantic zoom, fit-to-width (8.2, 8.3, 8.6) — PARTIAL (logic tested; visual pass DEFERRED)
- [ ] **All lanes** from `laneDefinitions.js` render from real artifacts, with a
      lane list to show/hide + expand/collapse; non-core lanes collapsed by
      default (8.4, 8.5, 8.9's lanes, 8.7). *(Record here if `validation` shipped
      as an empty stub.)* — PARTIAL; `validation` shipped as an empty-state stub (D6)
- [~] Click any lane block → read-only detail in the right panel + playhead seek — PARTIAL (wired + field maps tested; click-through DEFERRED)
- [~] Human hint editor: view / create / edit / delete / set-to-playhead / save (8.8) — PARTIAL (draft/validation tested; interactive save DEFERRED)
- [~] Review-queue editor round-trip — `review_queue.json` → `song_facts.json` (8.10) — PARTIAL (partition/merge tested; interactive save DEFERRED)
- [x] Artifact inspector — raw-JSON file browser (8.9) — PASS (73 files reached, 0 missing)
- [x] Runs as the `ui` Compose service on `:8080`; prod nginx build works — PASS (dev :9090 → 200; prod `final` image → 200)

## Decisions taken by recommendation

| Decision | Rationale |
| --- | --- |
| React 18 + TypeScript + Vite, no component library | User-chosen. Nocturne CSS covers the visual system; a kit would fight it. |
| wavesurfer.js v7 is the audio player **and** the master clock | User-chosen player; making it the single clock removes the design's rAF position loop and keeps audio and playhead exactly in sync. |
| Fresh `ui/` tree, old app deleted in the same change | User-chosen ("start from scratch"); the parity checklist is the safety net, not a file-by-file migration. |
| Keep the vite-dev-server `/data` + PUT API | Proven, matches the constitution's "own service, enforced by the API" rule; no reason to re-architect the backend during a frontend rebuild. |
| Nocturne `styles.css` vendored unchanged | It is the design's source of truth; retuning happens in the design project, not here. |
| Timeline x is time-proportional, not uniform px-per-bar | The analyzer's tempo can drift within a song; a shared time→x mapping keeps every lane, the playhead and wavesurfer in exact alignment. `pxPerBar` stays the zoom label. |
| Old app kept as a reference copy in item 1; deleted at cutover | Keeps a runnable reference to diff against during the rebuild without a bisect landing on an empty `ui/`. |
| Target Chrome 151 only | Single-operator internal tool; Nocturne's CSS already needs modern features, and cross-browser work has no payoff here. |

## Out of scope for UI v2

- Any change to analyzer artifacts, `schema_version`s, or the `build_ui_data`
  contract.
- Turning the debugger into a production consumer UI, auth, multi-user, or
  hosting beyond the local Compose service.
- The offline beatdrop visualizer export (Story 7.5) — separate track, untouched.
- Rebuilding lanes for artifacts the current app does not already show.
- A conductor / tempo / meter / key "global" track — removed, not rebuilt.
- Retuning Nocturne itself.
