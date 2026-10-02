# Experiment — Downbeat anchors

*(no external model — classical; reads `reference/proposals/phrases.json` as data)*

## Status

**Built and run 2026-10-01 (v3.10 item 16). Negative result: the phrase-anchored
downbeats do NOT beat the incumbent.** Pooled F1 @ +-70 ms against the Moises
downbeats: incumbent allin1 phase **0.343** (5 songs) / **0.234** (the 4 songs
behind the documented 0.226); anchors + allin1 fallback (as specified)
**0.301** / **0.119**. Nothing in `src/` reads anything here. Not promoted;
`timing.py` is unchanged.

## Why? What for?

Bar numbers are short of target (0.226 F1). A drop, a bass or drums entry or an
impact is where a bar starts, so a phrase edge on one is a *local* downbeat
that needs no song-wide grid. If edges are downbeats, counting in fours between
them (trusted beats only) yields bar positions with a better F1 than allin1's
activation, and two anchors that cannot both be right mark the span between
them `resolved: false` instead of guessing.

Question:

> Does counting bars in fours from confident phrase edges (entries and impacts)
> beat allin1's downbeat phase on downbeat F1 against Moises?

Incumbent: allin1 phase in `beats.json` (confidence-bearing downbeats only) —
documented 0.226. Baselines: `modulo` (every 4th beat from the first beat — the
old `beat_in_bar`) and `kick-phase` (one song-wide phase of four: the one whose
beats carry the most drums-stem sub+bass energy; no anchors).

## Method

`anchors.py` (pure) and `build.py` (I/O):

1. **Anchor** = a phrase start edge with no `conflicts`, `snapped` to a trusted
   beat, evidence including a `stem_enter` / `presence_enter` / `impact`
   (exits and gap/riser/roll ends alone are not downbeats), summed evidence
   `score` >= **1.5**, and a beat within 50 ms.
2. **Count**: between consecutive anchors a, b (beat indices), downbeats at
   a, a+4, a+8 ... .
3. **Disagreement**: `(b - a) % 4 != 0` -> span `resolved: false`
   (`phase_disagree`); a span crossing an untrusted (off-grid) beat ->
   `resolved: false` (`off_grid`). No downbeat is emitted inside either.
4. **Reach**: before the first and after the last anchor, counting continues
   16 bars (64 beats) through trusted beats only.
5. **allin1 fallback**: confidence-bearing allin1 downbeats are used only on
   beats no anchor reaches.

Constants chosen **before** scoring, and why: `ANCHOR_MIN_SCORE = 1.5` — equal
to phrases' own acceptance score, i.e. no extra filter (a stricter one would be
a tuning knob against the labels); `REACH_BEATS = 64` — 16 bars, the
window `timing.py` already uses for its local phase vote; `SNAP_TOL_S = 0.05`
— the edge time is already a beat time, this only guards a lookup. Nothing was
tuned against Moises. The one exception is the `@2.5` column, which is
**sensitivity only**: run after seeing the default result, to see whether
stricter anchors help; it is not adopted and not the headline.

## Scoring

Same method as `analysis-definition.md` "Downbeats", reused as code
(`analyzer.stages.validation.beats._score_downbeats`, imported as a function):
reference = `reference/moises/beats.json` `beatNum == 1`; tolerance 70 ms;
greedy one-to-one nearest matching; the range is the span of
`reference/moises/chords.json`; the incumbent's predictions are `beats.json`
downbeats with non-null confidence. Five songs have `reference/moises/`:
`Armin - Revolution`, `Hideaway - Kiesza`, `Queen of Kings - Alessandra`,
`Titanium - David Guetta ft Sia`, `_test_song`. Pooled = micro-average.

**Reproducing 0.226.** The incumbent's per-song figures reproduce exactly
the stored `phase_1_report.json` values (0.606 / 0.060 / 0.878 / 0.000 /
0.618). The documented 0.226 is stale (Armin was 0.593 then, now 0.606) and
was the pool of the first four songs, 385 downbeats; Queen of Kings was added
later. Today's same-method figure: **0.234** on those four, **0.343** with
Queen of Kings. Both pools are reported. `out/score.txt` is the full output.

## Results

F1 @ +-70 ms (`out/score.txt`):

| Song | incumbent | modulo | kick-phase | anchors-only | anchors+allin1 | @2.5 (sens.) |
| --- | --- | --- | --- | --- | --- | --- |
| Armin - Revolution | 0.606 | 0.268 | 0.067 | 0.174 | 0.186 | 0.578 |
| Hideaway - Kiesza | 0.060 | 0.024 | 0.016 | 0.000 | 0.027 | 0.067 |
| Queen of Kings - Alessandra | 0.878 | 0.000 | 0.954 | 0.889 | 0.947 | 0.947 |
| Titanium - David Guetta ft Sia | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| _test_song | 0.618 | 0.033 | 0.033 | 0.653 | 0.618 | 0.618 |
| **Pooled, 4 songs (385 ref.)** | **0.234** | 0.083 | 0.026 | 0.106 | 0.119 | 0.223 |
| **Pooled, 5 songs (462 ref.)** | **0.343** | 0.069 | 0.180 | 0.273 | 0.301 | 0.361 |

What it says, plainly:

* **Done-when not met.** The specified method (anchors + allin1 fallback) is
  below the incumbent on both pools (0.119 vs 0.234; 0.301 vs 0.343). It does
  beat both cheap baselines on both pools (modulo 0.083 / 0.069, kick-phase
  0.026 / 0.180).
* **Anchors are only as right as the edge-to-downbeat assumption.** Fraction of
  anchors that land on a Moises downbeat: Queen of Kings 8/8, `_test_song` 2/2,
  Armin 3/7, Titanium 0/11, Hideaway 0/5. Where an anchor is right, the count
  between anchors is right too (Queen of Kings 35/35 counted bars, Armin 4/4).
  So the counting works; the premise fails on 3 of 5 songs.
* **Titanium: anchors agree with allin1, and both disagree with Moises.**
  9 of 11 anchors sit on a Moises *beat 3* — the same 2-beat offset that
  zeroes allin1 there (`analysis-definition.md`). The music's entries and
  allin1's activation both put the downbeat where the reference says beat 3;
  the reference convention (or its beat grid) is the odd one out, not
  something this experiment can fix.
* **Hideaway: 0/5 anchors** and 5/5 off a Moises beat entirely — essentia's
  beat grid is the wrong tempo there (already documented), so no phase choice
  on it can land within 70 ms.
* **Armin: 5 of 6 spans are unresolved (4 `phase_disagree`, 1 `off_grid`)**; phrase edges are often a pickup
  beat or a few beats off the bar, so the strict "disagree -> unresolved" rule
  throws away most of the counted bars and the allin1 fallback that would
  have scored 0.606 is not allowed to speak inside them. That is the rule as
  specified; it is why Armin falls from 0.606 to 0.186.
* **Abstention is large.** Unresolved spans: 12 of 28 across the five songs
  (corpus-wide 89 of 165; none on Queen of Kings, Sash, Gabry Ponte,
  Underworld, `_test_song`). That honesty is the point, but the F1 pays recall
  for it.
* **Sensitivity (not adopted).** `@2.5` keeps only strong anchors and lifts
  Armin back to 0.578; the 5-song pool reaches 0.361 (above 0.343) but the
  4-song pool stays below the incumbent (0.223 vs 0.234). With 5 songs and one
  threshold looked at after seeing labels, this is a hint for a follow-up,
  not a result.

## Not tried / next

* Anchors weighted by evidence kind (a bass entry and an impact together vs a
  presence entry alone); no per-kind audit of which edges are on a downbeat.
* Resolving a `phase_disagree` span by majority of nearby anchors instead of
  discarding it.
* A bar-phase check from the lyrics' `lead_in_bars` or other timing facts.

## Reproduce

```bash
docker compose run --rm --no-deps app python -m experiments.downbeat_anchors.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.downbeat_anchors.run export --all-songs
docker compose run --rm --no-deps app python -m experiments.downbeat_anchors.run score
docker compose run --rm test python -m pytest experiments/downbeat_anchors/tests -q
```

`export` writes `data/analysis/<song>/reference/proposals/downbeat_anchors.json`
(`anchors[]`, `spans[]` with `resolved`/`reason`, `downbeats[]` with `source` of
`anchor` / `counted` / `counted_edge` / `allin1` and a `confidence` that is
`null` for counted bars). No debugger lane exists for this experiment.
