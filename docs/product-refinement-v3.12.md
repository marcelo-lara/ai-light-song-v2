# Product refinement — v3.12

**Status: open, nothing built.** Theme: find the changes a light show must
follow when loudness stays flat, and get them to the authoring model.

Validation set for every item, positions on the current grid:

| Song | Span | What happens |
| --- | --- | --- |
| *Medicine-MilkInc* | bars 8–23 (13.54–37.96 s) | 8 drum fill; 9–16 groove in + harmonic filter opening, bass out from 10; 16–18 build (kick roll); 19–22 dark break; 23 sub returns. Operator-named: bars 9–17 |
| *Armin - Revolution* | bars 55–60 (≈102.1–111.2 s) | 55–58 upper bands open; 59 near-silent gap; 60 drop. Operator-named: bars 56–59 |
| *ayuni*, *Charli-VonDutch* | whole song | operator-named filter-sweep songs; current `filter_sweep` finds 0 sweeps on them and on *Armin* |

Medicine's mix RMS is flat (≈0.19) across bars 4–15: the change is brightness
(ratio 0.35 → 0.6), transients (×2) and drum hits, not level.

---

## 1. Per-bar feature table — experiment first

**Change.** One row per bar fusing what already exists, nothing new extracted:
mix and per-stem loudness, the 7 bands (mix + stems), brightness ratio,
transient strength and spread, kick/snare/hat counts, `vocals_phrase` cover,
arrangement entries/exits, `filter_sweep` direction, gesture overlap. Also a
half-beat variant for items 4 and 5.

The table is the input to item 2 and to every later detector; detectors stop
reading artifacts one by one, which is how bars 9–17 was seen by four
artifacts and acted on by none.

| | |
| --- | --- |
| Writes | `reference/proposals/bar_features.json` (experiment); lane "Bar Features" |
| Reads changed | new `experiments/bar_features/` |
| Done when | the table for the validation set shows each listed change at its bar by eye in the lane |

---

## 2. Light change points and roles — experiment first

**Change.** Change-point detection on item 1's table (each bar against the
previous 4–8) yields light-change points inside and across sections, each
labelled with a role: `groove_in`, `build`, `break`, `drop`, `gap`, `fill`.
Edges come from feature changes, never from a fixed bar count (`grid_consensus`'s
8-bar grid scored 0/7).

Scored against operator-named light changes, not section boundaries: a light
change inside an intro is a hit here and a false positive for segmentation.
`texture_novelty` was archived negative under the boundary scorer (F1 0.29);
it is re-measured here as one input under this scorer, not revived as a
segmenter.

| | |
| --- | --- |
| Writes | `reference/proposals/light_changes.json` (experiment); lane "Light Changes" |
| Done when | on the validation set: Medicine 8, 9, 16, 19, 23 and Armin 55, 59, 60 found within one beat, roles right; steady bars (Medicine 10–14) carry no point |

---

## 3. Downbeat re-anchoring

**Change.** The beat times stay (trusted); downbeat labels are rebuilt from an
anchor vector: confident downbeats (kick-phase, item 4 attacks, impacts,
stem entries) pin the bar index, and bars between anchors are counted in fours
on the beat times. A bar shorter or longer than 4 beats is never published:
the slip is resolved by relabelling the downbeat index, not by warping time
(a warp cannot fix a phase error). Anchors that disagree mark the span
`resolved: false`.

Medicine bar 16 is one beat long (27.25 → 27.68 s); every bar after it is one
beat off. Incumbent to beat: allin1 (F1 .343 @ ±70 ms on the Moises songs);
`downbeat_anchors` (.301) was negative, so kick-phase is the new input.

| | |
| --- | --- |
| Writes | experiment first; `beats.json` `bar`/`beat`/`type` only on promotion |
| Done when | no bar ≠ 4 beats outside `off_grid_spans` corpus-wide; F1 above allin1 on the Moises songs |

---

## 4. Kick presence from attacks only

**Change.** A kick counts only at an attack: a steep 40–120 Hz rise (≈10–20 ms)
with a coincident 2–5 kHz click, pitch drop as tie-break. A decay or sustained
low end (bass, filtered pad) never counts. Echoes are rejected by signature: a
weaker, duller attack at a fixed offset after a stronger one. Off-grid
survivors get low confidence, not deletion. Runs on the mix, so stem
separation (Medicine's beat leaking into `harmonic`) cannot hide the kick.

| | |
| --- | --- |
| Writes | experiment beside `kick_check`; feeds item 1's kick column |
| Done when | Medicine bars 9–18 read kick-present, 19–22 absent; agrees with `drum_events` kick timing where omnizart is right |

---

## 5. Filter sweeps v2 — design only, not yet an experiment

**Change.** Track the resonant peak on a log-frequency spectrogram of the
harmonic stem every half beat (peak Hz, resonance sharpness, high/low ratio),
then report behaviour, not a verdict: slope and consistency over the last
1/2/4/8 bars. The cue event is the **sweep end** (top reached, cut, gap, drop
landing), placed on the beat grid, plus what the next 1–2 bars do
(`gap` / `drop` / `break` / nothing). A sweep end followed by nothing is a
suspect detection.

The current detector fails by construction: a centroid over 7 per-band-normalised
bands barely moves in a dense mix, so the 1-octave gate rejects real sweeps.

---

## 6. Texture reaches the show

**Change.** The authoring model reads only the 9 top-level files, none of
which carries brightness, transients or sweeps. After items 1–2 pass, publish
per-bar texture (brightness, transient density, sweep state, light-change role)
into a top-level file and project it through `get_detail`.

| | |
| --- | --- |
| Writes | contract change: top-level file + `mcp/serializers.py`; `downstream-contract.md`, `mcp-definition.md` |
| Done when | `get_detail` over Medicine bars 8–20 shows the groove-in, build and break |

---

## 7. Vocal cadence without lyrics

**Change.** `vocal_onsets.json` (word onsets, all 27 songs) drives
`vocal_cadence.json` timing on songs with no human/Moises lyrics (≈21).
Onset times only; word text is never read or published.

---

## 8. Artifact cleanup

**Done 2026-10-03:** the five orphans deleted on all 27 songs (135 files; nothing in `src/`, `mcp/`, `ui/src`, `experiments/` read them). `loudness_envelope.json` stays until the debugger derives it.

**Change.** Delete orphans whose producer v3.10 removed: `artifacts/essentia/hpcp.json`,
`artifacts/layer_a_harmonic.json`, `artifacts/layer_c_energy.json`,
`artifacts/genre.json`, top-level `genre.json` (all 27 songs). Kept by operator
decision: `section_function_contest.json` (frozen, no producer),
`validation/drops_score.json`, `whisperx-vad/vocal_onsets.json`.
`loudness_envelope.json` is redundant with `loudness.json`; the debugger
derives it, then it goes.

Rule for keeping any layer: it changes a light decision (timing, change,
intensity, texture, vocal cadence) or feeds one that does. Pitch, harmony and
word content never qualify.

Proposals by light value — high: `filter_sweep`, `texture_novelty` (item 2
input), `energy_level`, `tension_shape`, `stem_presence_sections`,
`drop_impacts`, `section_names`, `downbeat_anchors`; medium: `kick_check`,
`clap_events`, `crash_check`, `rhythm_*`, `phrase_periodicity`, `phrases`,
`character`; none: `vocal_transcription`, `moises/chords.json`.

Cross-repo: `ai-dmx-light-render`'s `fadeout.load_flagged_tail_window` is
dead and would read `artifacts/` — removed there.

---

## Carried over (operator actions, no build)

- Lane-review verdicts on the v3.10 experiments `filter_sweep`, `phrases`,
  `downbeat_anchors`, `section_names` (entries in `experiments.md`).
- Confirm/reject the queued `verdict_check` on *Hideaway - Kiesza*
  `chorus_is_drop` in the debugger.

---

## Order

8 → 1 → 2 → 4 → 3 → 6 → 7; 5 stays design-only until 1–2 are validated.
