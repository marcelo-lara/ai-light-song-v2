# UI definition — the artifact debugger

`ui/` is an **internal engineering tool**, played against the song. It is not a
product surface, and it must not redefine the stable contract under
`data/analysis/{song}/`.

Runbook for the visual regression suite:
[`reference/ui-regression.md`](reference/ui-regression.md).

## The two purposes

Everything the debugger does serves one of these. A proposed feature that serves
neither does not belong here.

### 1. Debug and review findings

Inspect what the pipeline claimed, against the audio, at the instant it claims
it. Timing, confidence and provenance inspection; artifact-to-artifact
comparison; raw JSON; auditioning unpromoted experiment proposals beside
hand-authored truth.

### 2. Author time-synced human hints

The debugger is where a human hint comes into existence. Three routes in, all
producing the same kind of hint:

| Route | What happens |
| --- | --- |
| **Promoted from an inference** | a block in an inference or experiment lane is turned into a hint — the operator heard it, agrees, and keeps it |
| **Human-reviewed** | an existing hint is corrected — its span dragged, its text rewritten |
| **Created by ear** | a hint marked from scratch against the waveform, backed by nothing the pipeline found |

This is the only place the operator's ground truth is authored, which makes it
the origin of everything downstream that carries `source: "human"`.

Out of scope: authoring or editing lighting output, acting as an end-user
playback product, and redefining the top-level artifact contract.

Debugger browser code lives in `ui/` only — never under `src/`.

## Reads: unrestricted

**The debugger may read anything it wants** — anywhere under `data/`, at any
depth: `artifacts/`, `reference/`, the source audio, intermediates nothing else
consumes. It is a debugger; a file it cannot open is a bug it cannot diagnose.

The exposure rule that confines the `mcp/` server to top-level `*.json` does
**not** apply here, and the lane table below is a description of what it reads
today, never a list of what it is allowed to read.

## Runtime

A separate Compose service named `ui`; the analyzer `app` service stays the only
runtime for inference and GPU work. The `ui` service must not reuse the analyzer
container.

| | |
| --- | --- |
| Dev server | Vite, live reload from `ui/src/` |
| Production | Nginx, `listen 8080` |
| App | Preact under `ui/src/` |
| Port | container `8080` → host `9090` |
| Mount | `./data:/data` |

```bash
docker compose up ui            # dev, live reload
docker compose build ui         # production image
# then open http://localhost:9090
```

## The write rule — load-bearing

**The debugger is read-only against generated data.** No snapshots, no caches,
no derived JSON, no overrides, no helper files into `data/analysis/`.

The only six writable paths:

- `data/analysis/{song}/reference/human/human_hints.json` — explicit `Save`
- `data/analysis/{song}/reference/human/song_facts.json` — explicit `Save`
- `data/analysis/{song}/reference/human/segments.json` — explicit `Save`. The
  operator's own hand-authored section segmentation, edited in the Human
  Sections panel below Human Hints. A bare array of `{start, end, label?,
  description?}`: `label`, when set, is a fixed value from
  `docs/segments-vocabulary.md` (mirrored in `ui/src/data/segmentFunctions.ts`
  and, for server-side validation, `ui/server/humanSections.ts`'s
  `SEGMENT_FUNCTION_NAMES`) — free text is rejected and unset is
  honest-unknown, never defaulted; `description` is unconstrained free text.
  The editor has exactly four controls: Start, End, Label, Description. A row
  read from disk may carry other keys (older files hold `energy`, `tension`,
  `rhythm`, which the analyzer ignores since v3.10): they are not shown, and a
  Save writes them back exactly as read, never adds, edits or removes them.
  Written by `PUT /api/human-sections/<song>` (dev-server only). Nothing in
  `src/` or `mcp/` reads it for those keys.
- `data/analysis/{song}/reference/human/lyric_validations.json` — **per-click**,
  not `Save` (v3.4 item 5 / D6). `{ schema_version, song_name, validated_ids:
  [int] }`: the ids of the Moises word tokens whose timing the operator has
  hand-verified with the ✔ button in the Moises Lyrics events panel. An
  **overlay** on `reference/moises/lyrics.json` — the lane shows a listed token
  at confidence `1` (a value Moises never emits) with a distinct tint; the
  Moises file itself is never edited and stays inference-only. Written by
  `PUT /api/lyric-validations/<song>` (dev-server only), which sends the full
  `validated_ids` array on each toggle and replaces the file. The per-click
  cadence is a deliberate divergence from the explicit-`Save` pattern the other
  writers use — a rapid token-by-token pass should not need a Save button.
  Nothing in `src/` or `mcp/` reads it.
- `data/analysis/{song}/artifacts/_run_request.json` — v3.8 item 2. The only
  writable path outside `reference/human/`: `{song, requested_at}`, written by
  the **Run analysis** button beside the song title in the header
  (`RunAnalysisControl.tsx`) via `PUT /api/run-request/<song>` (dev-server
  only), one PUT per click — no explicit-Save step. `song` may not contain
  `/`, `\` or `..` (400). The host-side `./analysis-watcher` (outside every
  container) reads and deletes this file to start `./analyze` for the song,
  and writes progress to the sibling `artifacts/_run_progress.json`, which the
  control polls read-only (a 404 is the expected idle state, not an error).
  This is the same request file `mcp/runs.py`'s `request_analysis` tool
  writes over stdio — one mechanism, two callers. Neither `_run_*` file is
  `reference/human/` material or a delivery artifact.
- `data/analysis/{song}/reference/pre-analysis/verdict.json` — v3.11 item 24.
  The only writable path under `reference/pre-analysis/`, and **narrower than
  the file**: the one value the UI may set is
  `second_pass.fields.<field>.operator = {answer: "confirmed"|"rejected",
  reason: string|null, check_id}`, the operator's answer to a queued
  `verdict_check`. Nothing else in the file is touched: an entry the second
  pass wrote keeps its `verdict` / `wrong` / `evidence` / `first_pass_verdict`;
  a field with no entry yet gets those four as `null`. `confirmed` = the hint's
  claim holds; `rejected` = it does not (a reason is required). The answer is
  final: a different answer for an answered field, a field with no first-pass
  verdict row and a missing file are all 400s that write nothing. It is not a
  new endpoint: `PUT /api/proposal-decision/<song>` (below) writes it, inside
  the same per-song lock, before flipping the queue row, on **either** decision
  (`structure.json` and the rest of `reference/pre-analysis/` stay unwritable
  here). `mcp/` never writes `operator` (`write_verdict_pass` preserves it).

`reference/proposals/pending.json` is not a seventh path: its only UI write is the `status` / `rejection_reason` flip of one row by `PUT /api/proposal-decision/<song>` (the MCP server alone appends rows).

`Cancel` / closing a panel must never update the three explicit-`Save` files.
The dev-server
API enforces this at the mount level. A future workflow needing persisted
review data must be documented as a new contract, not added implicitly.

### A promoted hint is indistinguishable from a hand-marked one

`human_hints.json` is the operator's own hand-authored ground truth and must keep
reading that way, whichever of the three routes produced an entry.

- **Prefer no field at all** — a hint's content is the hint.
- Where something genuinely must be recorded, it is **one human-readable string
  aimed at the person who opens the file**, not a structured object aimed at a
  script. `captured_from` (e.g. `"allin1 Sections · experiments/allin1"`) is that
  field.
- `type` (`"hint"` | `"review"`) names which of the two the entry is: `"hint"`
  for one authored from scratch, `"review"` for one seeded from an
  experiment/event block to review or annotate a finding. It is editable in
  the hint editor's Type dropdown — not a hard link to the origin, just a
  reviewer-facing label — and tints the Human Hints lane block so a review
  entry reads apart from a hand-authored one on the timeline.
- Both keys are **omitted entirely** on a hand-authored hint with no note, so
  its shape is unchanged.
- No analyzer code reads either field. Do not design a field here around a
  machine consumer.

**The `field_sources` / `source` attribution on the generated delivery surface
stops at these files.** That convention exists so a *fused, machine-written*
value can say which producer won. `reference/human/` has exactly one producer —
the operator — and adding provenance machinery to it (to `human_hints.json`,
`song_facts.json`, `segments.json` or `lyric_validations.json`) would answer
a question nobody is asking while making the file harder to read by hand.

### A hint's id is a stable identifier, not a display position

`hint-NNN` ids are assigned once, when a hint is created (the next unused
number), and never reassigned afterwards. On `Save`, the editor sorts
`human_hints.json` ascending by `start_time` so the file reads front-to-back
along the timeline — but that sort reorders the array only, never the ids. An
existing hint keeps its id even if editing, inserting, or deleting other
hints changes its position in the file. This matters because other documents
(`docs/experiments.md`, `experiments/*/README.md`) cite specific hint ids
against specific songs as measured evidence — a save-time renumbering would
silently invalidate those references.

## Lanes

Lanes are the review surface, and any time-bearing experiment output gets one.
**Every experiment artifact has its own lane, and a lane shows only its source
artifact** — never a merged, fused or synthesized view, not even a draft
fallback: the UI exists to debug artifacts, and a blend hides which producer
said what. (Known exception: the fused Sections lane.) The segment editor likewise
builds its drafts from `segments.json` only.
This table is **current state, not a permitted-reads list** — see "Reads:
unrestricted" above.

| Lane | Reads | Notes |
| --- | --- | --- |
| Sections | `sections.json` + `artifacts/section_segmentation/sections.json` | `function_status` is `known` or `unknown` only; the inspector card prints `function`, `function_confidence`, `function_status` and `same_label_as` |
| Gestures | `song_event_timeline.json` | |
| Arrangement State | `arrangement_state.json` | top-level published (v3.2); who is playing, per-stem RMS state changes |
| Vocal Cadence | `vocal_cadence.json` | top-level published (v3.9 item 1, promoted from `experiments/vocal_cadence`); per-line bar-relative timing + separate call events from the operator's lyric alignment (`lyrics.json`) + `beats.json`; timing only, no lyric text. Lines render as blocks, calls as zero-length point markers. `source: null` + a `reason` (D1.1) when the song has no lyrics tier |
| Human Hints | `reference/human/human_hints.json` | writable |
| LLM Pending Proposals | `reference/proposals/pending.json` (the `propose_hint` queue, `docs/mcp-definition.md`) | read-only here, no experiment badge, directly below Human Hints, indigo tint (hue 245). One block per entry with `type: "hint"` **and** `status: "pending"`, sorted by `hint.start`; approved/rejected ones get no block. Block label = `hint.title`, detail = `evidence`, summary = `hint.summary`, reference = the proposal `id`. Hover (this lane only) sets a native tooltip: `<range> · <title>` / `<summary>` / `evidence: <evidence>`. Clicking a block (on the lane or in its events panel) seeks to `hint.start` and opens the **Pending proposals** drawer view (`PendingProposalsPanel.tsx`) scrolled to that proposal's card, highlighted (`review-queue__q--focused`). On each pending card the heading is `hint.title` (`(untitled)` when empty), then the `title · start–end` line, then `hint.summary`, then `evidence: …`. Clicking the card body seeks to `hint.start`, except clicks inside `.hint-editor__actions`, the reject-confirm row, or any button/input/textarea. The reject reason is a 2-row `<textarea class="input">`. Every approve/reject reloads the queue and hands it back to `App` (`onQueueChange`), so the lane drops the decided block without a song reload. **`verdict_check` rows (v3.11 item 24)** are a second card type in the same panel (`VerdictCheckCard.tsx`), never a block on this lane: heading = the claim, then `verdict check · <field>`, five evidence rows (`stems`, `drum_density`, `dropouts`, `loudness`, `web_search`, each `read:` / `showed:`), `cannot settle: …`, the question, and **Confirm** / **Reject** (Reject opens the reason textarea; `Confirm reject` stays disabled until the reason is non-blank). Confirm = approve (operator `confirmed`), Reject = reject with reason (operator `rejected`); both write `verdict.json`'s `operator` (see the write rule) and the queue row's `status` / `rejection_reason`. A decided check shows as `confirmed` / `rejected` in the Decided list. No re-run reminder, no drag, no card-click seek |
| Verdict Checks | `reference/pre-analysis/verdict.json` (+ the queue for pending / decided checks, + the published `sections.json` to resolve ids) | read-only (v3.11 item 24), no badge, directly below LLM Pending Proposals. **Absent unless the song's `verdict.json` has at least one verdict row** — no data, no lane, no empty header (a lane with rows but no block is the ordinary ready-empty lane). One block per verdict row whose first-pass evidence names sections (every `*_section_ids` key): it spans the first to the last of those sections; rows with none (`bpm`, `vocals`) get no block. Tint = outcome, one colour each: `confirmed` green, `refuted` red, `unresolved` amber; the outcome shown is the operator's answer (`confirmed` → confirmed, `rejected` → refuted) if any, else a settled second pass, else the first pass. Hover tooltip: `<range> · <field> · <outcome>`, `<field>: first pass <verdict>`, `second pass: <verdict> (wrong: hint\|analysis)` when settled, `operator: <answer> — <reason>` when decided, `verdict_check pending` when queued. Clicking a block seeks to its start and, when the verdict has a pending `verdict_check`, opens the Pending proposals view on that card; otherwise it only seeks (no panel) |
| Human Sections | `reference/human/segments.json` | writable. The operator's own hand-authored section segmentation, below Human Hints; `label` (fixed vocabulary or unset), `description` (free text). The segment editor and this lane read `segments.json` only. Inspecting a block on allin1 Segmentation or Moises Sections offers "Create human section", which seeds an unsaved editor draft from the block (see `docs/reference/ui-regression.md`, `inspector-promote`) |
| Moises Sections | `reference/moises/segments.json` | read-only. Moises.ai's reference segmentation — same bare `{start, end, label}` shape as Human Sections but never edited; one fusion tier below it in `sections.json` (`docs/reference/analysis.segments.md`) |
| allin1 Segmentation | `artifacts/section_segmentation/sections.json` | read-only. The raw, pre-fusion analyzer output — lets the operator see what our own segmentation produced even on a song where the fused Sections lane shows a human or Moises override instead |
| Moises Lyrics | `reference/moises/lyrics.json` (+ `reference/human/lyric_validations.json` overlay) | read-only ground truth; blocks tinted by per-word confidence. Each word-token card in its events panel has a ✔ button (v3.4 item 5); a validated token shows at confidence `1` with the distinct `moisesLyricsValidated` tint in both the panel and the lane. `lyric_validations.json` is writable (per-click); `reference/moises/lyrics.json` is never edited |
| Drop Proposals | `reference/proposals/drop_impacts.json` | experiment |
| Character, Shadow | `reference/proposals/character.json` | experiment |
| 2. Texture Novelty | `reference/proposals/texture_novelty.json` | experiment (v3.4 item 6 — failed its kill condition, kept for one review pass) |
| 3. Phrase Periodicity | `reference/proposals/phrase_periodicity.json` | experiment (v3.4 item 7 — passed its kill condition) |
| 4. Structural vs Micro | `reference/proposals/structural_vs_micro.json` | experiment (v3.4 item 8 — failed its kill condition, kept for one review pass) |
| Vocal Phrases, Vocal Transcription | `reference/proposals/vocal_*.json` | experiment |
| allin1 Posterior | `reference/proposals/allin1_posterior.json` | experiment — shadow-label spans the published 8-bar argmax discards; the entropy-confidence half of this entry shipped independently as `sections.json`'s `function_confidence`, so only shadow labels ride this lane. Loses to an even-grid baseline on boundary recall on 3/4 gold songs (`docs/experiments.md`) — not a promotion candidate as scoped |
| Stem Presence Sections | `reference/proposals/stem_presence_sections.json` | experiment — bass on/off + drums full/sparse/off state machine, hysteresis-merged, boundaries moved to the nearest physical stem onset; vocals annotate but never cut a boundary. Not yet scored corpus-wide (`docs/experiments.md`) |
| Clap Events | `reference/proposals/clap_events.json` | experiment (v3.9 item 2) — claps detected from the drums stem by per-hit spectral shape, never omnizart's label. Point events |
| Kick Check | `reference/proposals/kick_check.json` | experiment (v3.9 item 2, kick-check sibling) — every omnizart `kick` kept/rejected by spectral shape + a percussive-attack gate; keep/reject tinted distinctly |
| Crash Check | `reference/proposals/crash_check.json` | experiment (the "`crash` over-fires on bright hats/rides" bug) — every omnizart `crash` kept/rejected by regular-stream-period rejection + a brilliance-band decay-shape gate; keep/reject tinted distinctly |
| Filter Sweeps | `reference/proposals/filter_sweep.json` | experiment (v3.10 item 14) — a harmonic or bass stem opening (brighter) or closing (darker) over 2–16 bars while its loudness stays level; spectral centroid from the published per-stem FFT bands; opening/closing tinted distinctly. Spans |
| Bar Features | `reference/proposals/bar_features.json` | experiment (v3.12 item 1) — one block per bar (label = bar number) tinted by the bar's brightness tercile within the song; grey when the bar is not 4 beats long (grid slip, flagged not repaired); caption carries per-stem RMS, brightness, transients, drum counts. A feature table, not a claim. Spans |
| Light Changes | `reference/proposals/light_changes.json` | experiment (v3.12 item 2) — one block per light-change point (the bar it starts) labelled with its role (groove_in / build / break / drop / gap / fill, else unknown) and tinted per role; detected on the per-bar feature table, never a bar-count grid; no confidence (score not calibrated). Spans |
| Kick Attacks | `reference/proposals/kick_attacks.json` | experiment (v3.12 item 29) — kick attacks detected on the mix (steep 40-120 Hz rise with a coincident 2-5 kHz click, pitch drop as tie-break), never omnizart's label; label `kick` or `echo` (a weaker, duller repeat at a recurring offset, with its parent); attacks beyond 1/4 beat from the grid tinted apart at low confidence. Point events |
| Phrases | `reference/proposals/phrases.json` | experiment (v3.10 item 15) — the song cut where stems enter/leave, impacts, pre-drop gaps and riser/snare-roll ends land, each edge at the nearest trusted beat (never bar-counted); per-phrase kick/bass/vocal presence, riser and snare-roll density, filter sweeps, noise sweep, kick drop-out, ends-on-gap, repeat-of, confidence. `resolved: false` blocks (edge evidence disagrees) tinted grey. Spans tiling the song |
| Section Names | `reference/proposals/section_names.json` | experiment (v3.10 item 17) — every phrase named in the typical EDM sequence of `segments-vocabulary.md` (Intro, Pre-Build, Build-Up, Fill, Pre-Drop, Drop, Drop Break, Breakdown, Outro ...) from kick/bass entries and hits; boundaries on the Phrases edges (a Fill / Pre-Drop / Build-Up start may sit on its own evidence time); a heuristic confidence on every row. A song with no build→drop unit shows its current `sections.json` labels, tinted grey and attributed. Spans tiling the song |
| Dense lanes | `essentia/fft_bands.json`, `essentia/fft_bands.bass.json`, `essentia/fft_bands.drums.json`, `essentia/fft_bands.harmonic.json`, `essentia/fft_bands.vocals.json`, `essentia/rms_loudness.json`, `essentia/loudness_envelope.json`, `symbolic_transcription/drum_events.json` | four per-stem FFT lanes beside the mix lane; each fails loudly on a missing artifact |

**Badging rule.** A lane fed from `reference/proposals/` is unpromoted
experiment output and carries a `ph-flask` badge in its lane head and its
events-panel header. A lane fed from `reference/human/` or `reference/moises/`
is ground truth and carries no badge. A song without the backing file renders an
empty lane (and logs a `404`) rather than failing.

A lane is removed when its experiment is abandoned or promoted.

## Header

Fixed top bar, three groups, left to right:

| Group | Element | Behavior |
| --- | --- | --- |
| Left | burger button | toggles the drawer (`app-drawer`) open/closed |
| Left | transport strip | to-start, previous bar, previous beat, play/pause, next beat, next bar — each seeks or steps `transport`/the bar-beat grid, does not change zoom or scroll |
| Center | `app-header__time` | playhead position as a clock, `M:SS.s` (one decimal), via `formatClock` |
| Center | `app-header__time_s` | the same playhead position as plain seconds with two fixed decimals, e.g. `112.21`, via `formatSecondsFixed` |
| Center | `app-header__barbeat` | current `bar.beat` (e.g. `12.3`), from `coords.timeToBarBeat(transport.currentTime)` against the beat grid |
| Right | song title + subtitle | song name, or "No song selected" / "Select a song from the drawer" when none is loaded |
| Right | BPM tag | `info.bpm` rounded, or `— BPM` when absent |

All three time/bar-beat readouts track `transport.currentTime` live during
playback and seeking; none of them show song duration.

## Footer

Fixed bottom bar, left to right:

| Element | Behavior |
| --- | --- |
| Zoom out / zoom in buttons | multiply/divide `pxPerBar` by `ZOOM_FACTOR` (1.3). The absolute clamp is `PX_PER_BAR_MIN`–`PX_PER_BAR_MAX` (3–360), and the effective minimum is the current fit-to-width value so zoom-out stops at whole-song view |
| Zoom slider | sets `pxPerBar` directly with the same 3–360 absolute span and the same whole-song effective minimum |
| `app-footer__ppb` label | live `"<pxPerBar> px/bar"` string |
| Fit-to-width button | sets `pxPerBar` so the whole song fills the visible scroll width (`fitToWidthPxPerBar`, driven by song duration and the median bar length) |
| Follow-playhead toggle (`follow-toggle`) | on by default, persisted per browser (`localStorage`); while on and playing, auto-scrolls the timeline to keep the playhead onscreen; turns itself off the instant the reviewer scrolls manually during playback |
| Lane-visibility toggle | opens/closes the lane list panel |

## Interaction state

Zoom, playhead position, lane visibility, lane collapse and region selection
are **browser-local only** and not persisted, except the follow-playhead flag
(`localStorage`, per browser). Shared zoom spans 3–360 px/bar, with a
viewport/song-specific floor at fit-to-width so the minimum visible zoom is
the whole song; at maximum
zoom a long song exceeds the ~32k-pixel canvas ceiling, so dense lanes hold
their CSS width and downscale the backing store instead.

When a lane is in the ready-empty state (`"No data in this artifact"`), its
expand control is ignored (both timeline lane head and lane list). Collapse
remains allowed. On song start, ready-empty lanes initialize hidden and
collapsed (unchecked in the lane list).

**Zoom keeps the playhead anchored.** While paused, zooming (the footer
buttons, the slider, or a keyboard shortcut) pins the playhead to the same
screen pixel it occupied before the zoom — the pixel position is captured
before the `pxPerBar` change and the scroll offset is recomputed to restore it
after, rather than leaving the scroll wherever the new scale happens to land.
Fit-to-width does not anchor to a pixel; it only scrolls the playhead back
into view afterward if the resize pushed it off-screen. During playback, zoom
anchoring is skipped entirely — the follow-playhead behavior above already
keeps the playhead onscreen every frame.

**Keyboard shortcuts** (ignored while typing in a text field, except Escape;
ignored with any Ctrl/Meta/Alt chord held):

| Key(s) | Action |
| --- | --- |
| Space | play / pause |
| ← / → | step one beat back / forward |
| Shift+← / Shift+→ | step one bar back / forward |
| `+` `=` `]` | zoom in |
| `-` `_` `[` | zoom out |
| `f` / `F` | fit to width |
| Escape | close the open overlay/panel |
