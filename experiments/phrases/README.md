# Experiment — Phrases

*(no external model or repo — classical, numpy; calls `gestures.py`'s primitive detectors as functions)*

## Status

**Built and run 2026-10-01 (v3.10 item 15): 299 phrases over 27 songs, 96
flagged `resolved: false`.** Rapture matches stem-presence; **Charli-VonDutch
does not (F1 0.833 vs 0.909 on hints, 0.667 vs 0.714 on segments) — the
done-when is not met.** Against the incumbent allin1 the phrase edges lose on
section boundaries (F1 0.431 vs 0.609) and win only on EDM-shaped songs'
fine-grained hints (0.667 vs 0.490, two songs). Nothing in `src/` reads
anything here. Queue row enabled. Debugger lane **Phrases** (flask badge).
Promotion waits on the operator's lane review.

## Why? What for?

A moving-head show changes behaviour where the *audio* changes: a bass drop, a
drums-out, a riser ending on a gap. `sections.json` cuts coarser (and
`stem_presence_sections` only on bass/drums persistence), and nothing publishes
what a chunk between two changes is *like* (kick? bass? vocals? a riser inside
it? a kick that drops out before the next hit?). Bar counting is not an option:
downbeat F1 is 0.226, `grid_consensus`'s 8-bar grid scored 0/7, radio edits
break any count.

Question:

> Do the edges where stems enter/leave, impacts land, pre-drop gaps close and
> risers / snare rolls end — each at the nearest trusted beat, no bar counting —
> find the operator's boundaries better than `stem_presence_sections` alone,
> and as well as allin1 where it matters, while carrying per-phrase features
> a cue author can use?

Incumbent: allin1 raw segments (`artifacts/allin1/raw.json`). Baseline:
`stem_presence_sections` (its proposals are also an *input*, see below).

## Method

1. **Trusted beats** (`features.py`): `beats.json` beat times outside
   `off_grid_spans`. Downbeats and bar numbers are never read. Beat length is
   the median beat interval.
2. **Edge candidates**, each with a weight and an evidence *group*:
   * `arrangement_state.json` stem entries/exits: bass/drums weight
     `1.0 x confidence`, vocals/harmonic `0.5 x confidence`. The state flickers,
     so a change that does not persist 4 beats keeps a quarter of its weight
     (same hysteresis idea as stem-presence, per stem).
   * `stem_presence_sections` boundaries, read as data from
     `reference/proposals/stem_presence_sections.json` (its state machine, folded
     in as an input): weight 1.5 (0.75 if its onset refinement found no crossing).
     It already survived a 4-bar persistence test, so on its own it clears the
     acceptance score; this makes its edges a floor.
   * `song_event_timeline.json` `impact` rows: `0.6 x confidence`. (Section
     transition rows are never used — they are derived from sections.)
   * Ends of `gestures.py` risers, reverse cymbals (`0.4 x conf`), snare rolls
     (`0.4 x conf`) and pre-drop gaps (`0.8 x conf`; a gap ends on the hit that
     follows), from the primitive detectors called as functions.
3. **Edges** (`detect.py`): candidates within 3 beats cluster; a cluster is an
   edge when its distinct evidence groups sum to >= **1.5**. A lone impact,
   riser end or roll end can never be an edge. The edge's time is the
   strongest *positional* member (presence boundary, then impact, then hard
   stem change), moved to the nearest **trusted** beat within one beat;
   otherwise it stays at the physical time and is flagged. Edges closer than
   4 beats (a beat count, not a bar length) or within 4 beats of the song's
   ends are dropped, keeping the stronger. Phrases tile the song: first start
   0.0, last end = `info.json` duration.
4. **Conflicting evidence -> `resolved: false`** on both phrases at the edge:
   stem sources (bass/drums arrangement + presence) more than 2 beats apart;
   one stem both entering and leaving in a cluster; no trusted beat within a
   beat. The edge is still published, never forced into agreement or deleted.
5. **Per-phrase features** (`build.py`, over beat windows, no bar grid):
   * `kick_presence` — fraction of beats where the **drums-stem** FFT bands
     below 150 Hz (sub + bass) peak >= max(0.2, 0.5 x the song's p95). Never
     `drum_events`' kick (it folds in toms and ghost hits).
   * `bass_presence`, `vocals_presence` — fraction of beats where the stem's
     `loudness.json` level >= 0.35 / 0.40 x its song p95 (stem-presence's
     fractions).
   * `riser_density`, `snare_roll_density` — fraction of the phrase's seconds
     covered by `gestures.py` riser + reverse-cymbal / snare-roll spans.
   * `filter_sweeps` — rows of `reference/proposals/filter_sweep.json` (item 14)
     with >= half their length inside; `null` when that file is absent.
   * `noise_sweep` (+ `noise_sweep_strength`) — in the phrase's last <=16 beats
     every band from low-mid to brilliance of the mix FFT rises (r2 >= 0.4,
     mean rise >= 0.2). A tonal riser lifts one or two bands, noise lifts all.
   * `kick_dropout_near_end` — kick presence in the last 4 beats <= 0.25 while
     the rest of the phrase's is >= 0.5; `null` when there is no kick to lose.
   * `ends_on_gap` — a `pre_drop_gap` ends within a beat of the phrase end.
   * `repeat_of` — the earlier phrase with a near-identical kick/bass/vocals
     presence + mix-band profile (RMS distance <= 0.12) and length within
     0.8-1.25x. Texture similarity, **not section identity** (MFCC 0.73 is the
     number identity must beat).
   * `confidence` — mean over the phrase's two edges of `min(1, score/4)`;
     `null` if the song has no edges. 1.5 (just accepted) reads 0.375.

Output `reference/proposals/phrases.json`: `blocks[]` with `id`, `start_s`,
`end_s`, the features above, `start_edge` / `end_edge` (`score`, `onset_s`,
`snapped`, `kinds`, `conflicts`), `resolved`, `conflicts`, `confidence`.

## Run

```bash
docker compose run --rm --no-deps app python -m experiments.phrases.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.phrases.run export  --all-songs
docker compose run --rm --no-deps app python -m experiments.phrases.run score    # writes out/score.txt
docker compose run --rm test python3 -m pytest experiments/phrases/tests -q
```

`compute` caches `cache/<song>.json`; run `filter_sweep` and
`stem_presence_sections` `export` first (the queue order does).

## UI lane

**Phrases** (`phrases`, flask badge, after Filter Sweeps). Label = phrase
number (`n?` when unresolved), wide label adds kick/bass/vox presence and the
first flag; unresolved phrases are tinted grey; the inspector lists every
feature and the conflicts.

## Scoring

`score.py`, boundary P / R / F1 at +-1.0 s, micro-averaged over boundaries,
against two reviewed truths: **segments** (`reference/human/segments.json`
starts, 10 songs, coarse) and **hints** (`type: "review"` rows' starts/ends,
8 songs, fine). Songs with `reference/pre-analysis/structure.json`
`genre.family == "edm"` (Armin, Rapture, Sash on segments; Rapture, Sash on
hints) are reported apart. Methods: phrases, phrases restricted to unresolved-free edges,
allin1 raw, stem-presence. `out/score.txt` has every song.

## Results

Pooled, P / R / F1:

| truth | group | phrases | phrases (resolved edges only) | allin1 (incumbent) | stem-presence (baseline) |
| --- | --- | --- | --- | --- | --- |
| segments | edm (3) | 0.483 / 0.424 / **0.452** | 0.417 / 0.303 / 0.351 | 0.559 / 0.576 / **0.567** | 0.364 / 0.242 / 0.291 |
| segments | non-edm (7) | 0.500 / 0.367 / 0.423 | 0.509 / 0.322 / 0.395 | 0.684 / 0.578 / **0.627** | 0.634 / 0.289 / 0.397 |
| segments | all (10) | 0.495 / 0.382 / 0.431 | 0.481 / 0.317 / 0.382 | 0.645 / 0.577 / **0.609** | 0.540 / 0.276 / 0.366 |
| hints | edm (2) | 0.789 / 0.577 / **0.667** | 0.733 / 0.423 / 0.537 | 0.522 / 0.462 / 0.490 | 0.722 / 0.500 / 0.591 |
| hints | non-edm (6) | 0.404 / 0.319 / 0.357 | 0.380 / 0.264 / 0.311 | 0.444 / 0.444 / **0.444** | 0.455 / 0.208 / 0.286 |
| hints | all (8) | 0.500 / 0.388 / 0.437 | 0.462 / 0.306 / 0.368 | 0.463 / 0.449 / 0.456 | 0.549 / 0.286 / 0.376 |

Required songs, F1 (P / R):

| song | truth | phrases | stem-presence | verdict |
| --- | --- | --- | --- | --- |
| Rapture - Nadia Ali | segments | 0.500 (0.385 / 0.714) | 0.500 (0.385 / 0.714) | match |
| Rapture - Nadia Ali | hints | 0.769 (0.769 / 0.769) | 0.769 (0.769 / 0.769) | match |
| Charli-VonDutch | segments | 0.667 (0.833 / 0.556) | 0.714 (1.000 / 0.556) | **below** |
| Charli-VonDutch | hints | 0.833 (0.833 / 0.833) | 0.909 (1.000 / 0.833) | **below** |

Reading it:

* **Rapture matches only because stem-presence's edges are a floor** (weight
  1.5 clears acceptance alone); nothing beats it. Charli finds the same 5 of 6
  hint boundaries stem-presence does plus one extra edge (36.25 s, drums and
  vocals entering together at the verse) that no hint labels — precision 0.833
  vs 1.000, same recall. The 125.3 s "full vocal peak" boundary is missed by
  both (vocals-only change).
* **allin1 stays the better section-boundary finder** (0.609 vs 0.431 on
  segments), and on the six non-EDM hint songs (0.444 vs 0.357). Phrase edges
  win only where the operator's hints are stem-shaped and fine-grained: EDM
  hints F1 0.667 vs allin1 0.490 and stem-presence 0.591 (two songs — Rapture
  and Sash; too few to claim).
* Precision against **segments** is capped by design: phrases are finer than
  sections, so interior phrase edges count as false positives.
* **Resolved-only edges are worse on recall everywhere** (0.317 vs 0.382,
  segments): the conflict flag marks edges that are often right but whose
  sources disagree on the time; `resolved: false` is "check this one", not
  "wrong". 96 of 299 phrases (32 %) carry it, mostly `position` (stem sources
  >2 beats apart, 56 phrase-sides) and `grid` (no trusted beat near, 40).
* **Features, corpus-wide**: `ends_on_gap` 62 of 299 phrases; `kick_dropout_near_end`
  38; `repeat_of` 41; snare-roll density > 0 on 108, riser density > 0 on only
  29 (the riser detector is rare); **`noise_sweep` fires on only 3** — the
  all-bands-rising rule is too strict to be useful as written (negative
  result); 78 filter sweeps land in phrases. None of these features has
  ground truth; the lane review is their only test.

## Tuning disclosure

Parameters were set a priori from each source's role, then changed once after
a first run: with `ACCEPT_SCORE = 1.0` and stem-presence weight 0.8 both
required songs were *below* stem-presence and corpus hint precision was 0.31
(impact + pre-drop-gap pairs inside drops count as edges and no hint labels
them). A six-point sweep of the acceptance score (F1, segments/hints pooled;
Rapture seg/hint; Charli seg/hint):

| accept | segments | hints | Rapture | Charli |
| --- | --- | --- | --- | --- |
| 1.0 | 0.386 | 0.384 | 0.400 / 0.710 | 0.435 / 0.500 |
| 1.25 | 0.362 | 0.357 | 0.476 / 0.741 | 0.455 / 0.526 |
| **1.5 (shipped)** | 0.431 | 0.437 | 0.500 / 0.769 | 0.667 / 0.833 |
| 1.75 | 0.441 | 0.436 | 0.526 / 0.800 | 0.571 / 0.727 |
| 2.0 | 0.422 | 0.411 | 0.556 / 0.833 | 0.615 / 0.800 |

(Sweep rows use the shipped presence weight 1.5 and cluster window 3.) 1.5 was chosen as "one persisted state
change, or two corroborating groups" and it is the best Charli point, **so it is
tuned against the labels of 10 songs and the figures above are optimistic by
that much**. Also changed after the first run, on principle not score: the
presence weight to 1.5, cluster window 2 -> 3 beats, the position-conflict test
to ignore impacts and use 2 beats (the first run flagged 38 % of 521 phrases; 32 % of 299 after), the
position priority (presence onset before arrangement block time), and
confidence scaling `score/2` -> `score/4` (it saturated at 1.0). Nothing else
was tuned. The min-phrase length (4 beats) was never swept.

## Known weaknesses

* `arrangement_state` blocks are 0.25 s steps and flicker; edges built on it
  alone are the noisiest, hence the persistence discount.
* Trusted-beat snapping moves a physical onset by up to a beat; both times are
  published (`onset_s` on the edge).
* `repeat_of` is texture similarity over 10 numbers — it is not identity and
  should not be read as "same section".
* `noise_sweep` is nearly silent (3 phrases); `riser_density` is almost always 0.
* A vocals-only change (Charli 125.3 s) cuts nothing by design.
* The truth sets are small (10 and 8 songs, 123 and 98 boundaries); EDM hints
  are two songs.

## Reach test

Time-bearing output -> `reference/proposals/phrases.json`, the **Phrases**
debugger lane. Not promoted; no top-level file. Items 16 (downbeat anchors) and
17 (section names) read this file as data.
