# Experiment — Filter Sweeps

*(no external model or repo — classical, numpy)*

## Status

**Built and run 2026-10-01 (v3.10 item 14): 79 sweeps over 27 songs, 0 to 9 per
song; nothing validated by ear yet.** No sweep ground truth exists, so there is
no precision/recall — the operator's review of the **Filter Sweeps** lane
(flask badge) is the acceptance test, and promotion into `gestures.py` is
asked for after it. Nothing in `src/` reads anything here. Queue row enabled.

## Why? What for?

A producer closes a low-pass filter on the pads or opens one on the bass over
4-16 bars, and the track changes tone while the same notes keep playing. For a
moving-head show that is a ramp in brightness or intensity with no new
instrument and no loudness change. Nothing published says so: `gestures`'
`riser` is a rise in *high-band energy* (a new sound getting louder) and
cannot tell "the pad got brighter" from "a noise riser entered".

Question:

> Does a near-monotonic move of a stem's spectral centroid over 2-16 bars,
> while that stem's loudness stays level, find filter sweeps — and find ones
> the incumbent `riser` does not?

Incumbent: `gestures`' `riser` / `downlifter` (`detect_ramps`, high-band mix
energy, r2 on a 2/4/8/16-bar window). It is the only published thing that
looks like a sweep. Cheap baselines: **depth only** (any 2-16-bar window whose
centroid moved >= the depth floor, no monotonicity, no level gate) and
**depth + monotonicity** (no level gate).

## Method

1. **Centroid** (`features.py`): per stem (`harmonic`, `bass`), per 50 ms frame
   of `artifacts/essentia/fft_bands.<stem>.json`, the level-weighted mean of
   log2(band centre Hz) over the 7 bands. Units are octaves, so `depth` is an
   interval. Silent frames (sum of band levels < 0.15) are NaN. The band
   levels are per-band 5th-95th percentile *normalised log power*, so the
   centroid is a relative brightness index — good for "brighter/darker",
   not an absolute Hz estimate.
2. **Level**: the same stem's `normalized_values` from top-level `loudness.json`.
3. Both series are averaged onto a half-beat grid, then (`detect.py`) smoothed
   with a 1-bar boxcar. **Bar length = 4 x the median beat interval**: no
   downbeats or bar numbers are read (downbeat F1 0.226).
4. For each stem, windows of 2, 3, 4, 6, 8, 12, 16 bars (stride half a bar)
   must: have the stem present (level >= 10 % of its song p95 throughout);
   move the centroid by >= 1.0 octave (`harmonic`) / 0.5 octave (`bass`, whose
   energy sits in the lowest bands); be monotonic (|Spearman rho| of centroid
   vs time >= 0.85); and keep loudness level — (p90 - p10) / mean <= 0.5 and a
   fitted level trend over the window <= 0.5 of the mean.
5. Survivors are ranked by depth x monotonicity, kept greedily without overlap
   per stem, and trimmed to the move itself (10 % of the range at each end).
   The result must still be 1.8-16.8 bars. Times are physical, never snapped
   to bars.
6. `confidence` = 0.25 + 0.75 x (0.4 monotonicity + 0.3 depth + 0.3 level
   flatness), each scaled 0..1. A heuristic ordering, **not calibrated**.

Output `reference/proposals/filter_sweep.json`: `blocks[]` of `direction`
(`opening` | `closing`), `stem`, `start_s`, `end_s`, `depth` (octaves),
`confidence`. Distinct from `riser`: it never looks at loudness rising and
requires the opposite (level stays flat).

## Run

```bash
docker compose run --rm --no-deps app python -m experiments.filter_sweep.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.filter_sweep.run export  --all-songs
docker compose run --rm --no-deps app python -m experiments.filter_sweep.run score    # writes out/score.txt
```

## UI lane

**Filter Sweeps** (`filterSweep`, flask badge, directly after Gestures).
Opening and closing sweeps are tinted apart; the inspector names stem,
direction, depth in octaves and confidence.

## Results

`out/score.txt`, all 27 songs that carry both stem FFTs:

* **79 sweeps**: 56 harmonic / 23 bass, 50 opening / 29 closing. Per song 0 to
  9: Titanium 9, Rapture 6, Medicine 6, Underworld 6, Hideaway 5, Only this
  moment 5; none on Armin, Best Friend, Charli-Guess, Charli-VonDutch,
  Fascination, Queen of Kings, Rotate, Yonaka, ayuni.
* **Distinct from the incumbent**: 11 of 79 sweeps overlap (>= 50 % of the
  sweep) one of the 54 riser/downlifter spans the incumbent finds on the
  same songs. 68 are sweeps `riser` does not see.
* **Baselines**: depth only finds 118, depth + monotonicity 118, the full
  detector 79. The level-flat gate removes a third of the depth candidates
  (stems that were also fading in/out — entries, not filter moves); the
  monotonicity gate removes **nothing** once the 1-bar smoothing is applied
  (the smoothing already does its job) — it is a guard, not a contributor.
* **No accuracy number.** `human_hints.json` has no sweep-typed hint on any
  song (the word "filtered" appears only on vocal hints), the operator has not
  yet named a heard sweep, and a count is not a score. Titanium's
  18.2-34.6 s harmonic opening and 88.6-93.6 s closing are the first ones to
  listen to.

**Known weaknesses.** A Demucs `other` stem carries separation error, so a
sweep may be a different instrument entering the harmonic stem (the level gate
only catches the loud ones). The thresholds (1.0 octave, 0.85, 0.5) were set
once by eye against the distributions, not tuned to any label. The bass stem's
centroid range is small, so its floor is lower and its rows are the least
certain. Done-when (refinement item 11: a sweep where one is heard, none on
steady sections of the same song) is still to be judged in the lane.
