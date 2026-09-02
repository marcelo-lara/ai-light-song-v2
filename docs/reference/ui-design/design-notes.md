# Design Notes — Score Analysis DAW

Extracted from the Claude Design canvas **"Score Analysis DAW"**
(`claude.ai/design/p/06705e66-…`, file `Score Analysis DAW.dc.html`, design
system **Nocturne** `7bb68ef7-…`). The canvas markup and its behavioural script
are preserved verbatim in [`Score-Analysis-DAW.dc.html`](Score-Analysis-DAW.dc.html);
this file is the human-readable spec of what that canvas defines and how it maps
onto real analyzer artifacts.

The canvas is a **static mock**: it generates fake waveform / FFT / RMS data with
a seeded RNG and hard-codes segments, chords, tempo marks and hints. The rebuild
keeps its **layout, visual language, lane model and interactions** and replaces
every data source with a real analyzer artifact plus wavesurfer.js for audio.

**One deliberate exception:** for the FFT / RMS / Envelope lane *fill colours and
sub-labels*, the **previous debugger** (its `src/lib/timeline/`) is the
authority, not this mock — see §3a. The mock renders those lanes in muted
Nocturne blurple; the previous debugger used a richer spectral / per-stem palette
the user wants preserved.

---

## 1. Nocturne design system

The rebuild vendors Nocturne's single stylesheet (`styles.css`) into
`ui/src/styles/nocturne.css` unchanged and takes **every** colour, font, space,
radius and shadow from its CSS variables — never a raw hex or px the tokens
already carry. Nocturne's own guidance (`readme.md`) is the styling contract.

### Character

Quiet, compact, dark. Near-neutral blue-grey ground (`#161826`), Inter at weight
500, 8 px radii, a single blurple accent used **as a line and a glow, not a
flood**. Contrast comes from the tonal ramps, not saturation. Density is 0.70×
on purpose — the spacing scale is already compressed.

### Tokens (from `styles.css :root`)

| Group | Tokens | Notes |
| --- | --- | --- |
| Ground / text | `--color-bg` `#161826`, `--color-surface` `#232532`, `--color-text` `#e9e9ed`, `--color-divider` (text @ 16%) | Never pure black/white. |
| Accent | `--color-accent` `#9184d9` + ramp `--color-accent-100…900`. `--color-accent-2-*` is a mono stand-in — treat as the same role. | On dark ground: 700–900 for tinted fills/hovers/borders, 500 base, 100–300 for text on tints and pressed states. Body-size accent text uses `--color-accent-300`, not the accent. |
| Neutrals | `--color-neutral-100…900` | Surfaces, borders, muted text. Keep chroma low outside the accent. |
| Deck-scale fills | `--color-section`, `--color-section-glow`, `--color-section-ghost` | Slide/hero grounds only — **not** used in this interface. |
| Type | `--font-heading` / `--font-body` = Inter; heading weight 500 | h1 42 / h2 32 / h3 25 / h4 20 / h5 16 / h6 13 (h6 uppercase, letter-spacing .08em). Never bolder than 500. |
| Space | `--space-1` 2.8 · `-2` 5.6 · `-3` 8.4 · `-4` 11.2 · `-6` 16.8 · `-8` 22.4 (px) | Use the vars, not the numbers. |
| Radius | `--radius-sm` 4 · `--radius-md` 8 · `--radius-lg` 14 | |
| Elevation | `--shadow-sm` (1px edge) · `--shadow-md` (edge + ambient) · `--shadow-lg` | On dark ground elevation is an edge + ambient darkness; don't stack shadows. |

### Component classes to reuse (don't invent parallels)

`.btn` + `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-icon` /
`.btn-block` (primary is an **accent outline, never filled**) · `.tag` +
`.tag-accent` / `.tag-outline` / `.tag-neutral` · `.field` + `label` / `.input`
(text + `textarea.input`) / `.radio` / `.seg` · `.card` + `.card-kicker` /
`.card-title` / `.card-body` / `.card-meta` · `.nav` · `.table` · `.dialog` ·
`.hr` (present, but prefer whitespace).

### States (built into the stylesheet — do not restyle per component)

Hover = accent-ramp tint; pressed = one ramp step past base (`--color-accent-400`
on this dark ground, or a `color-mix()` tint for outlined/ghost); focus =
`:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px }`;
`::selection` = accent tint; disabled = 45% opacity.

### Icons

**Phosphor** (`@phosphor-icons/web`, regular weight) throughout — the canvas
loads it from unpkg; the rebuild vendors it (CSP / offline). Icon names used in
the canvas: `list, skip-back, rewind, caret-left, play, pause, caret-right,
fast-forward, file-audio, gear, graph, waveform, music-notes, metronome,
chart-bar, squares-four, folder-open, export, sliders-horizontal, flag,
caret-down, magnifying-glass-plus/minus, arrows-out-line-horizontal, x`.

### Interface-local styles (in the canvas `<style>` block, not in Nocturne)

These are small utility classes the interface adds on top of the system — port
them into `ui/src/styles/daw.css` using tokens where the canvas used raw values:

- `.tp` — transport button: 30×30, `--radius-sm`, transparent, `--color-neutral-300`; hover `--color-accent-900` bg / `--color-accent-300` fg. `.tp-main` — 34×34 with an `--color-accent-700` border (the play/pause button).
- `.zbtn` / `.zic` — zoom controls in the footer (26 / 22 px).
- `.caret` — 18×18 lane-collapse chevron.
- `.dr-item` — drawer nav row: flex, `--space-3` gap, `--space-2/-3` padding, `--radius-sm`, `--color-neutral-400`; hover `--color-neutral-900` bg.
- range input (`input[type=range]`) — 3 px track `#2b2e3d`, 11 px `--color-accent-300` thumb with a glow.
- `.tl` scrollbar — 11 px, `#101219` track, `--color-neutral-800` thumb.
- Raw greys the canvas uses for the timeline chrome that should map to tokens or a small local set: header gradient `#1d2030→#181a28`, lane-header `#181a26`, lane body `#101219`, segment header `#1e2130`, bar ruler `#1a1c29`, lane bottom-border `#202331`. Keep these as 4–5 named locals in `daw.css` (`--tl-bg`, `--tl-lane-head`, `--tl-ruler`, …) so the timeline reads as one surface family.

---

## 2. Layout anatomy

Full-viewport, `overflow:hidden`, three fixed bands + a scrolling middle:

```
┌ header  h=54  grid 1fr / auto / 1fr ───────────────────────────────────┐
│ [☰] │ transport (⏮ ⏪ ‹ ▶/⏸ › ⏩)   │  0:17.3 / 1:12.0   1.3 BAR.BEAT  │  Song — take · analysed date   [124 BPM][F♯ minor] │
├───────┬───────────────────────────────────────────────────────┬────────┤
│ nav   │  timeline (.tl, overflow:auto)                         │ right  │
│ 212px │  grid-template-columns: 212px  max-content             │ panel  │
│ (drawer│  ┌ sticky lane-label col ┐┌ sticky Segments row ─────┐│ 296px  │
│  toggle│  │ Segments  (h 26)      ││ segment blocks           ││(when a │
│  only) │  ├──────────────────────┤├──────────────────────────┤│ hint   │
│        │  │ Bars   62 px/bar (h30)││ bar/beat ruler (seek)    ││ is     │
│        │  ├──────────────────────┤├──────────────────────────┤│ open)  │
│        │  │ Waveform Anchor      ││ <canvas> lane body       ││        │
│        │  │ Human Hints          ││ + HTML hint pills        ││        │
│        │  │ FFT Bands            ││ <canvas>                 ││        │
│        │  │ RMS Loudness         ││ <canvas> + stem sublabels││        │
│        │  │ Loudness Envelope    ││ <canvas>                 ││        │
│        │  └──────────────────────┘└──────────────────────────┘│        │
│        │        playhead: 1px accent line + glow + caret, z=8  │        │
├───────┴───────────────────────────────────────────────────────┴────────┤
│ footer  h=38   [zoom −] [range 14–180] [zoom +]   [fit-to-width]        │
└───────────────────────────────────────────────────────────────────────┘
```

- **Header** — 3-column grid. Left: hamburger (toggles the nav drawer) + a 1px divider + the transport cluster. Centre: `curTime / totalTime` (20 px heading, tabular) and `bar.beat` (accent-300, 20 px) with a `BAR.BEAT` caption. Right: song title + `artist · analysed <date>` subtitle, then a stacked `124 BPM` (`.tag-accent`) and `F♯ minor` (`.tag-outline`).
- **Left nav** — 212 px, `#13151f`, appears only when the drawer is toggled (`sc-if drawer`). The mock has many placeholder rows; **`ui-v2`'s drawer has exactly four entries**: **Select Song**, **Timeline** *(active — accent-900 bg)*, **Artifact inspector** (plan item 8), **Review queue** (§4). Nothing else — no "Tempo map" / "Harmony report" / "Process" / "Settings" placeholders. Lane show/hide lives in the lane list, not the drawer.
- **Timeline** — the scroll container. A CSS grid: a **212 px lane-label column** (sticky `left:0`) and a `max-content` body column whose width is `pxPerBar × bars`. Two sticky header rows (Segments h26, Bars ruler h30) sit at `top:0` / `top:26`. Then one row per lane: sticky label cell + a body cell containing a full-width `<canvas>` (+ HTML overlays). The **playhead** is one absolutely-positioned element spanning all lanes.
- **Right panel** — 296 px, `#13151f`, `sc-if panelOpen`. One shell, three modes (see §4): block inspector (read-only), hint editor, review queue. Dismisses on outside-click (not on a lane block / hint pill) or ✕ / `esc`.
- **Footer** — 38 px. Zoom out / range slider (`min 14 max 180 px/bar`) / zoom in, then a fit-to-width button.

### Timeline dimensions & scroll

- The canvas mock is **uniform px-per-bar** (constant tempo). **The rebuild is time-proportional** (bars drift with tempo): `x = t · pxPerSec` where `pxPerSec = pxPerBar / medianBarSeconds`. `pxPerBar` (14–180) stays the zoom control and the "px/bar" label; internally it drives `pxPerSec`. `timelineW = durationSeconds · pxPerSec`. `fitToWidth` solves `pxPerSec = (viewportWidth − 212 − 12) / durationSeconds`.
- Bar lines are drawn at each bar's **real start time** (from `beats.json`), so bar spacing is not uniform when the tempo drifts. Ruler seek: `t = (clientX − rulerLeft) / pxPerSec` → wavesurfer. Every lane, the playhead and wavesurfer therefore share one time→x mapping.
- **Follow-playhead**: while playing, if the playhead x exceeds `scrollLeft + viewportWidth − 120` scroll so it sits at 55% of the viewport; if it goes behind the sticky label column, scroll back.
- Lane heights (rebuild): Waveform 84, Human Hints 58, FFT 84, RMS 112, Envelope 112, other sparse lanes 84 (the previous app `TRACK_HEIGHT`). A **collapsed** lane is 26 px and its body draws a faint waveform "strip" summary.

### Semantic-zoom thresholds (from `renderVals`)

| `pxPerBar` | Bar labels every | Beat sub-ticks | Segment shows "N bars" | Chord shows roman numeral |
| --- | --- | --- | --- | --- |
| ≥ 56 | 1 bar | yes (≥ 44) | width ≥ 92 px | width ≥ 92 px |
| 26–55 | 2 bars | ≥ 44 only | | |
| 16–25 | 4 bars | no | | |
| < 16 | 8 bars | no | | |

Hint pills: show the time range only when the pill is ≥ 70 px wide, the note only ≥ 150 px.

---

## 3. Lanes — canvas mock vs. real artifact

The canvas renders 5 lanes + 2 sticky header rows. **The rebuild renders all
lanes from the previous app's `src/lib/config/laneDefinitions.js`**: the design's five
expanded, every other lane **collapsed by default** (26 px strip), all
show/hide- and expand/collapse-able from a lane list. Column widths, grid lines
(`b%4===0` bright accent @ .16, else @ .06) and the playhead are shared. Each
lane's **body** is a `<canvas>` sized `pxPerBar×bars` wide at devicePixelRatio,
redrawn on zoom / collapse / resize. Sparse (block) lanes additionally build
click hit-regions; clicking a block opens the right-panel block inspector (§4a)
and seeks the playhead.

| Lane (canvas `id` / `kind`) | Canvas mock draws | Real source | Rebuild rendering |
| --- | --- | --- | --- |
| **Segments** header | 10 hard-coded blocks; chorus/bridge tinted accent, others neutral; left-border "mark" | `sections.json` top-level list (v2.1: `section_id`, `form_role`, `energy_character`, `confidence`) | HTML blocks positioned by `start`/`end` → bar. Tint by `form_role` family (chorus/drop/hook = accent, verse/intro/outro/bridge = neutral). Click → block inspector (§4a). |
| **Bars** ruler | **always**: a minor tick per bar + a taller tick + number label at every *N*th bar (*N* by zoom). **Only when not crowded** (`pxPerBar ≥ 44`): beat sub-ticks between the bar ticks. `21 px/bar` example = per-bar minor ticks, labels every 4 bars, no beat sub-ticks. Click-to-seek. | `beats.json` (`time`, `bar`, `beat_in_bar`, `type`) | Real bar/beat grid from the beat list; downbeats = the taller ticks. Beat sub-ticks gated on the §2 zoom table. Click-to-seek drives wavesurfer. |
| **Waveform Anchor** (`wave`) | seeded fake peak waveform, mirror-drawn around a mid-line | the song's decoded audio (`data/songs/<song>.mp3`) | **wavesurfer.js** renders this lane. It owns waveform + audio playback + region-drag; its `currentTime` is the single clock the other lanes and the playhead follow. Peaks pre-decoded and cached where possible. |
| **Human Hints** (`hints`) | canvas draws only the grid; hint **pills** are HTML overlays (`buildHints`) | `reference/human/human_hints.json` | HTML pills at `start_time`/`end_time`. Click opens the right panel. Selected pill = accent-700 bg / accent-400 border. |
| **FFT Bands** (`fft`) | 26-bin spectrogram, per-cell muted-blurple `oklch()` fill | `artifacts/essentia/fft_bands.json` (`frames[].levels[]`, `bands[]` — **7 bands**) | **Use §3a, not the mock's blurple.** Per-band `hsla()` heat, band 0 (Sub) at the bottom. |
| **RMS Loudness** (`rms`) | 5 stem rows, per-px bars, muted-blurple stem colours; stem sublabels | `artifacts/essentia/rms_loudness.json` (`frames[].normalized_values[]`, `sources[]` = Mix/Bass/Drums/Harmonic/Vocals) | **Use §3a `SOURCE_COLORS`** (gold / red / cyan / green / purple), per-bucket heat, alpha by value. |
| **Loudness Envelope** (`env`) | 5 stem rows, smoothed line per stem | `artifacts/essentia/loudness_envelope.json` | **Use §3a** — filled area + stroke line per stem in the same 5 colours. |

> **the previous app's lane rendering is the palette authority,
> not the canvas mock.** The mock keeps everything in Nocturne blurple; the
> shipped debugger already renders FFT / RMS / Envelope with a richer, more
> legible palette that the user wants kept. §3a captures it verbatim from
> the previous app's `src/lib/timeline/`. The mock stays authoritative for *layout* and *chrome*;
> §3a is authoritative for FFT / RMS / Envelope *fill colour and sub-labels*.

### No conductor / "global" track

`renderVals` also builds `chords` and `tempoMarks` (`4/4`, `♩ 124`, key-change
pins) and reads a `showChordTrack` prop — scaffolding for a global/conductor
strip — but **nothing places it in the template**. That strip was deliberately
removed and **is not rebuilt**. The sticky header area is **only Segments +
Bars** (user-confirmed). Chords are shown as an *ordinary sparse lane* (it
already existed in the previous debugger as "Chord Regions" from
`layer_a_harmonic.json`), not as a header strip; there is no tempo/meter/key
lane at all.

---

## 3a. Lane palette & sub-labels — carried over verbatim from the previous app's `src/lib/timeline/`

the previous app's FFT / RMS / Envelope rendering is kept as-is in the
rebuild. Values below are lifted exactly from the previous app's `src/lib/timeline/fftBandsLane.js`,
`loudnessLane.js`, `waveformLane.js` and `constants.js`. Reuse the same
constants in the React `CanvasLane` renderers; do **not** re-derive them from
Nocturne's accent ramp.

### FFT Bands (`fftBandsLane.js`)

- The real `fft_bands.json` has **7 bands**: `Sub, Bass, Low Mid, Mid, Upper
  Mid, Presence, Brilliance`.
- Per-band hue, indexed by band order (fallback `196` for any index ≥ 7):

  ```js
  const FFT_BAND_HUES = [22, 46, 88, 138, 164, 186, 196]; // Sub … Brilliance
  const bandColor = (bandIndex, intensity) =>
    `hsla(${FFT_BAND_HUES[bandIndex] ?? 196}, 84%, 58%, ${clamp(intensity, 0, 1) * 0.9})`;
  ```

  So bottom → top the lane runs **orange-red (Sub, 22°) → orange (Bass, 46°) →
  yellow-green (Low Mid, 88°) → green (Mid, 138°) → teal (Upper Mid, 164°) →
  cyan (Presence, 186°) → cyan-blue (Brilliance, 196°)**, all at `84% 58%`
  HSL, alpha = value × 0.9.
- **Band 0 is drawn at the bottom row, the last band at the top**
  (`displayIndex = bandCount − 1 − bandIndex`). Row edges are integer-rounded
  across `TRACK_HEIGHT − topPadding − bottomPadding`, `topPadding =
  bottomPadding = 6`, lane height `TRACK_HEIGHT` = **84**.
- Visibility floor: skip a cell when raw `intensity ≤ 0.02`; otherwise draw with
  `visibleIntensity = (intensity − 0.02) / 0.98`.
- Time bucketing: `bucketSeconds = max(intervalSeconds || 0.05, 1 / max(zoom, 1))`;
  per bucket, per band, take the **max** level across the frames in it.

### RMS Loudness + Loudness Envelope (`loudnessLane.js`)

Lane height `LANE_HEIGHT` = **112**. `topPadding = bottomPadding = 5`, `rowGap =
2`, `rowHeight = (112 − 10 − (n − 1)·2) / n` — for the 5 essentia stems ≈ 18.8 px
per row. `sources[]` order from the artifact **is** the colour index:

| # | Stem | `fill` / `stroke` rgb | hex | (Tailwind) |
| --- | --- | --- | --- | --- |
| 0 | **Mix** | `250, 204, 21` | `#FACC15` | yellow-400 |
| 1 | **Bass** | `248, 113, 113` | `#F87171` | red-400 |
| 2 | **Drums** | `34, 211, 238` | `#22D3EE` | cyan-400 |
| 3 | **Harmonic** | `74, 222, 128` | `#4ADE80` | green-400 |
| 4 | **Vocals** | `192, 132, 252` | `#C084FC` | purple-400 |

```js
const SOURCE_COLORS = [
  { rgb: [250, 204, 21] }, { rgb: [248, 113, 113] }, { rgb: [34, 211, 238] },
  { rgb: [74, 222, 128] }, { rgb: [192, 132, 252] },   // fallback = last entry
];
const colorAt = (i, a) => `rgba(${(SOURCE_COLORS[i] ?? SOURCE_COLORS.at(-1)).rgb.join(",")}, ${a})`;
```

- **Per-row background** (both modes): fill `rgba(148, 163, 184, 0.06)`, then a
  1 px bottom rule `rgba(148, 163, 184, 0.16)`.
- **RMS** (`drawRmsHeatmap`): per time bucket, `fillStyle = colorAt(i, 0.16 +
  visibleIntensity · 0.72)` (alpha 0.16 → 0.88), drawn `rowTop + 1` for
  `rowHeight − 2`. Skip bucket when bucket-max `≤ 0.02`;
  `visibleIntensity = (max − 0.02) / 0.98`. Bucketing uses the per-source
  **max** in the bucket.
- **Envelope** (`drawEnvelopeTrace`): filled area under the curve at
  `colorAt(i, 0.18)`, then the outline stroke at `rgba(r, g, b, 0.94)`,
  `lineWidth = 1.5`. `baseline = rowTop + rowHeight − 4`,
  `amplitude = max(6, rowHeight − 14)`; x is the bucket **midpoint**; bucketing
  uses the per-source **average**.
- Bucketing: `bucketSeconds = max(windowSeconds || 0.01, 1 / max(zoom, 1))`.

### Stem sub-labels (`drawSourceLabel`) — placement the user wants kept

One chip per stem row, at that row's top, **anchored to the left edge of the
visible viewport** (it scroll-follows — it is not pinned at an absolute
`left:3px`):

- `x = round(visibleRange.start · zoom) + 6` (the `+6` inset from the viewport's
  left edge). On redraw, recompute from the current scroll position.
- Text: `sources[i].label` (`Mix`, `Bass`, …), trimmed to **56 px** with an `…`,
  font `11px "IBM Plex Mono", monospace` (`CAPTION_FONT`).
- Background: a plain rect `rgba(10, 18, 28, 0.68)` at
  `(x − 2, rowTop + 2, textWidth + 6, 13)` — **no radius, no border**. The
  boxed look in the screenshot is only this dark rect behind the coloured text.
- Text fill: the stem's colour at ~0.9 alpha (`SOURCE_COLORS[i]` `fill`),
  baseline at `rowTop + 11`.
- FFT lane has **no** sub-label (single series).

### Waveform Anchor lane — wavesurfer, in Nocturne blurple

The user's reference render shows the **canvas** treatment, not the current
build's teal: a blurple mirror waveform around a centre line. Configure
wavesurfer:

- `waveColor` ≈ `#968ae0` (`--color-accent-500`), `progressColor` ≈ `#d2cefd`
  (`--color-accent-300`) — or draw the played region a touch brighter.
- centre-line ≈ `#2b2741` (`--color-accent-900`).
- container height 84 (`TRACK_HEIGHT`); no per-lane grid tint.
- The playhead is the shared Nocturne-accent line + glow from the mock, drawn by
  the timeline shell over all lanes (not wavesurfer's own cursor — disable it).

(The current `waveformLane.js` teal — `rgba(15,118,110,·)` — is **not** carried
over; only FFT / RMS / Envelope keep the previous app palette, per §3a above.)

### Lane heights — current impl vs. mock

| Lane | Canvas mock `h` | Current impl | Use |
| --- | --- | --- | --- |
| Waveform | 66 | 84 | 84 (wavesurfer container height) |
| Human Hints | 58 | — | 58 (mock) |
| FFT Bands | 104 | 84 | 84 |
| RMS Loudness | 100 | 112 | 112 |
| Loudness Envelope | 100 | 112 | 112 |
| Collapsed (any) | 26 | — | 26 |

---

## 4. Right panel — one shell, three modes

296 px, `sc-if panelOpen`, `#13151f`, left border, `overflow-y:auto`, with a
header row, body and footer. It replaces the previous app's floating
`OverlayPanel` — all block detail lives here. Modes:

| Mode | Opened by | Editable? |
| --- | --- | --- |
| **Block inspector** | clicking any lane content block (section, chord, pattern, identifier hint, machine event, ML event, beatdrop window, phrase, accent candidate, regression mark) | **read-only** |
| **Hint editor** | clicking a Human Hints pill, or "new hint" | editable → `human_hints.json` |
| **Review queue** | a drawer entry (no lane) | editable → `song_facts.json` |

Every open also moves the shared playhead to the selection's start.

### 4a. Block inspector (read-only)

`label` as the heading, then a Nocturne `<dl>` of the block's fields —
`laneLabel`, time range (`m:ss.s–m:ss.s`), `confidence`, `reference` / `id`,
`section_id`, `created_by`, and any lane-specific fields — then the `summary`
sentence, then a "show raw" disclosure with the block's full source object.
**No inputs, no Save.** Field lists per lane come from
the previous app's `src/lib/timeline/sparseContent.js` + `SelectionDetailCard/selectionFields.js`
in the previous app.

### 4b. Hint editor

Header: ‹ › prev/next-hint round buttons + `HUMAN HINT` kicker, and a ✕. Body
(all `.field` + `.input`):

| Field | Canvas draft key | Maps to `human_hints.json` |
| --- | --- | --- |
| Start / End (side by side) | `draft.start` / `draft.end` (`m:ss.s`) | `start_time` / `end_time` (seconds) |
| Title | `draft.title` | `title` |
| Musical hint (textarea, 3 rows) | `draft.musical` | `summary` |
| Lighting hint (textarea, 3 rows) | `draft.lighting` | `lighting_hint` |

Footer: `Cancel` (`.btn-ghost`) / `Save` (`.btn-primary`), pushed to the bottom
(`margin-top:auto`). The canvas `savePanel` mutates its in-memory array; the
rebuild issues `PUT /api/human-hints/<song>` (the existing dev-server contract,
Story 8.8) and only on explicit Save.

**Not in the canvas but required at parity:** create a new hint, delete the
active hint, and "set start/end to playhead" — carry these over from the current
`HumanHintsSidebar` (they already exist). The v2.1 review-queue editor (Story
8.10) reuses the same right-panel shell as a second mode.

---

## 5. Transport & clock

Canvas: a `requestAnimationFrame` loop advances `posBeats` by `dt / secondsPerBeat`;
`togglePlay`, `toStart`, `prev/nextBar`, `prev/nextBeat`, ruler click-to-seek.
`bpm`, `beatsPerBar`, `bars` are constants.

Rebuild: **wavesurfer.js is the clock.** `posBeats` is derived from
`wavesurfer.getCurrentTime()` and the real beat grid (`beats.json`) —
`bar/beat` and the playhead x come from mapping time → nearest beat. Transport
buttons call wavesurfer (`playPause`, `seekTo`), and `prev/nextBar|Beat` seek to
the neighbouring entry in the beat list. No rAF position loop of our own — a
`wavesurfer.on('audioprocess'|'seeking')` handler drives a single `currentTime`
state; the playhead and follow-scroll read from it.

---

## 6. What the canvas is missing (rebuild must add)

- **Song discovery** — the canvas has one hard-coded song. The drawer's "Select Song" opens a picker backed by the existing discovery API (`data/analysis` listing + `data/songs` audio files). Parity requirement.
- **All ~16 lanes**, not the mock's 5 — with a lane list to show/hide and expand/collapse, and non-core lanes collapsed by default.
- **Time-proportional x** — the mock assumes constant tempo; the rebuild maps every lane by real time so bars can drift (§2).
- **Block inspector (read-only)** — clicking any lane content block shows its detail in the right panel (§4a); replaces the previous app's floating overlay.
- **Artifact inspector (plan item 8)** — the canvas has no raw-JSON view. Parity with Story 8.9: a drawer entry listing `artifacts/**` with a collapsible JSON view, styled to Nocturne (`.table`, `.card`). A *file* browser, distinct from the per-block inspector.
- **Loading / empty / error states** for every lane and for a song with missing artifacts.
- **Keyboard**: space = play/pause, ←/→ = prev/next beat, shift+←/→ = bar, `[` `]` or `+` `-` = zoom, `f` = fit, `esc` = close panel. (The canvas has none.)

## 7. Build / target facts

- **Target: Chrome 151 only** (the operator's browser). No cross-browser support, no polyfills, no autoprefixer. Modern CSS/JS freely — Nocturne's `styles.css` already relies on `oklch()`, `color-mix()`, `:has()`. Vite / tsconfig `target: esnext`.
- **Previous app** — the pre-rebuild Preact/MUI app was kept as a reference copy from plan item 1 and was the behaviour reference for the whole rebuild. It was removed at cutover (plan item 11); nothing in the repo references it now.
- **No conductor / tempo / "global" strip** — removed, not rebuilt (§3a). Chords is an ordinary sparse lane.
- **First-load audio** — no peaks artifact; wavesurfer decodes the full mp3 on song load (loading state shown). A precompute endpoint is a later optimisation.
