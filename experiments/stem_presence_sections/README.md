# Experiment — Stem Presence Sections

*(no external model or repo — classical, numpy)*

## Status

**Measured 2026-09-27: F1 0.27 vs allin1 0.62 on the scoring corpus** (see
Results evidence). Nothing in `src/` reads anything here.

## Why? What for?

`sections.json` (boundary F1 0.67 @ ±1.0 s, `docs/analysis-definition.md`)
misses obvious structure on drops/breakdowns where the *stems that are
playing* change hard but the harmonic/timbral content barely does. On
`Rapture - Nadia Ali` (Avicii remix), a per-bar mean of `loudness.json`'s
normalized stem RMS makes the structure legible by eye: bass+drums both loud
= drop, bass on/drums ~0 = chorus tail, both off = verse/break. allin1 places
the first drop boundary at 48.0 s; the true onset (hand seed,
`reference/human/segments.seed.json`, eyeball-only — built with this same
method, never used to score) is 55.25 s.

Question:

> Does a discrete bass/drums-presence **state machine** — not a continuous
> novelty curve — find section boundaries better than allin1's own raw
> segmentation, an even-bar baseline, and `arrangement_state.json`?

This is not a repeat of `experiments/texture_novelty` (self-similarity
novelty over spectral bands, archived at F1 0.29 — see
`docs/archive/experiments.discarded.texture-novelty.md`). That method fired on
every texture change, including inside a stable section. This one classifies
each bar into one of four coarse states and only cuts where the state changes
**and persists** for `MIN_SECTION_BARS` bars — hysteresis is the mechanism,
not a post-hoc filter.

## Method

1. **Bar grid** — `beats.json` downbeats directly (not a synthetic
   bpm-derived grid): each bar spans one downbeat to the next, so an
   irregular grid (`Rapture` bars 26-30 run ~1.4 s instead of ~1.85 s) is
   respected rather than smoothed over.
2. **Per-bar level** — mean `loudness.json` `normalized_values` for
   bass/drums/vocals over each bar's 20 ms frames (`features.py`).
3. **Per-song thresholds** — every threshold is a **fraction of that song's
   own bar-level p95** for the stem, never an absolute number (stem levels
   are song-relative):
   - bass on/off: `0.35 * p95(bass)`
   - drums full/sparse/off: `0.50 * p95(drums)` / `0.15 * p95(drums)`
   - vocals on/off (label only, never cuts): `0.40 * p95(vocals)`
4. **Coarse label** per bar from bass+drums only:
   `full` / `bass_only` / `drums_only` / `stripped`. Vocals are attached to
   each output block as `vocals_present_fraction` but never enter the label —
   a chorus vocal hook toggling every 2 bars must not fragment the section.
5. **Hysteresis** (`state_machine.py::apply_hysteresis`) — any run shorter
   than `MIN_SECTION_BARS = 4` bars is merged into whichever NEIGHBOUR run
   shares its majority `bass_state` (bass is the more reliable dimension —
   a bassline entry/exit is normally a hard cut, where the drums
   full/sparse tiers flicker near a decay tail or a continuing hi-hat
   layer); if both/neither neighbour matches, merge whichever direction
   produces the longer combined run. This absorbs a short mid-drop dip
   (e.g. a 1-bar drums blip inside a long `full` run) AND correctly keeps
   a real short event (an EDM break) as one run even when its own edge bar
   misreads a tier due to a decay tail — literal same-label-only merging
   got both of these wrong in an earlier version (see git history): it
   swallowed real 4-bar breaks split by a contaminated edge bar, and it
   delayed a clean bass entry/exit by one full bar when the entry bar's
   drums tier misread. Regression tests:
   `test_hysteresis_pins_a_known_step_onset_to_its_bar`,
   `test_hysteresis_keeps_a_real_4_bar_break_inside_a_drop`.
6. **Boundary onset refinement** (`onset.py`) — each surviving state change
   moves from the bar edge to the nearest 20 ms-frame midpoint crossing of
   whichever stem(s) actually changed, searched within one bar of the
   nominal edge. No crossing found in that window ⇒ boundary stays at the
   bar edge, reported `boundary_resolved: false` — never silently snapped.
7. Per-block `confidence` = mean classifier margin (bar level vs. its nearer
   threshold, as a fraction of that stem's p95) over the block's bars.
   `null` is never emitted for confidence — every block has at least one bar.

No verse/chorus vocabulary is invented; `state` is always one of the four
coarse labels above.

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.stem_presence_sections.run compute --song "_test_song"
docker compose run --rm --no-deps app python -m experiments.stem_presence_sections.run export  --song "_test_song"
docker compose run --rm --no-deps app python -m experiments.stem_presence_sections.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.stem_presence_sections.run export  --all-songs
docker compose run --rm --no-deps app python -m experiments.stem_presence_sections.run score
docker compose run --rm test python3 -m pytest experiments/stem_presence_sections/tests -q
```

Runs on any song with `loudness.json` + `beats.json` (`paths.all_songs()`),
not only the four gold songs — `score` is the one subcommand restricted to
`truth_common.structure.SCORING_CORPUS` (needs
`reference/human/segments.json`).

`compute` writes one `cache/<song>.json` (per-bar levels + thresholds);
`export` and `score` read that cache (auto-computing it if missing).

## Experiment Plan / scoring

`score.py` uses `experiments/truth_common/structure.score_structure()` against
the 4-song scoring corpus, ±1.0 s, never against the published `sections.json`
(circularity rule — see `structure.py`'s own docstring). Four methods,
per-song + pooled (`structure.corpus_row`):

1. this experiment,
2. incumbent — allin1's own **raw** boundaries (`artifacts/allin1/raw.json`;
   `sections.json` is fused/re-labelled from this and would be circular to
   score against on these 4 songs),
3. cheap baseline — an evenly spaced 8-bar grid,
4. incumbent — `arrangement_state.json` block starts.

## Results evidence

Scoring corpus (`score`, 2026-09-27), boundary F1 @ ±1.0 s — pooled P 0.43 /
R 0.19 / **F1 0.27** (23 pred / 52 truth) vs allin1 raw 0.62, `arrangement_state`
0.36, even 8-bar grid 0.06. Per song: ayuni 0.19, Cinderella 0.15,
`_test_song` 0.55, What a Feeling 0.35. Per-method tables in `out/`. Recall
is the failure: these songs' boundaries are mostly vocal/harmonic changes
over unchanged bass and drums.

Off-corpus sanity checks (not scores), below. Against the operator's later
14 reviewed Rapture hints: 10/13 boundaries found, F1 0.77 vs allin1 0.42.

- **`Rapture - Nadia Ali`**: boundaries vs the hand seed
  (`reference/human/segments.seed.json`, built by this same eyeballing
  method — sanity only) and `arrangement_state.json`'s own stem
  entries/exits. Drop 1 onset: seed 55.25 s, this experiment 55.38 s
  (allin1: 48.0 s). Drop 1's internal 4-bar break: expected ~70.25-77.5 s,
  this experiment 69.94-77.31 s. Bass entry at bar 18: expected 33.25 s
  (per-bar RMS), this experiment 33.26 s. Bass exit into the post-chorus:
  `arrangement_state.json` reads 150.0 s, this experiment 149.54 s. Drop 2
  onset: seed 169.84 s, this experiment 170.09 s; its internal break:
  expected ~184.75-192.0 s, this experiment 184.41-191.78 s.
- **`Charli-VonDutch`** (Charli xcx — Von Dutch): boundaries vs
  **operator-reviewed** `reference/human/human_hints.json` (`type: "review"`,
  real ground truth, just not in `SCORING_CORPUS`). 5 of 6 hint boundaries
  matched within 0.5 s: 29.78→30.10, 74.09→73.61, 88.40→88.38, 96.26→96.59,
  155.34→154.93. The one miss, 125.34 s ("full vocal peak"), is a vocals-only
  change with bass and drums both already `full` on either side — this
  method correctly does not invent a boundary there, since vocals never cut
  one by design. It also **split the seed's single 73.86-96.46 s "Verse"**
  into `stripped` (73.61-88.38, drums+bass out) then `drums_only` (88.38-96.59,
  build), which is exactly the operator's own hint-3/hint-4 breakdown at the
  same times — `docs/segments-vocabulary.md` already has `Breakdown / Break`
  and `Build-Up` for this; no vocabulary change proposed.

## Reach test

Time-bearing output → `reference/proposals/stem_presence_sections.json`,
rendered as the **Stem Presence Sections** debugger lane, below Human Hints.
Not promoted; no top-level file.
