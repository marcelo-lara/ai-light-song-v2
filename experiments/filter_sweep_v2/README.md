# Experiment — Filter Sweeps v2

*(no external model or repo — log-frequency spectrogram of the harmonic stem, numpy/librosa STFT)*

## Status

**Built and run 2026-10-03 (v3.12 item 31): 27 songs, 131 sweeps, 85 of them with aftermath `none`.**
No sweep ground truth exists; the operator's review of the **Filter Sweeps v2** lane (flask badge) is
the acceptance test. Queue row enabled (runs before `bar_features`). `bar_features` gains
`sweep_slope` / `sweep_state`. Nothing in `src/` reads it.

## Why? What for?

`experiments/filter_sweep` (centroid over 7 per-band-normalised FFT bands) barely moves in a dense mix:
0 sweeps on *Armin*, *ayuni*, *Charli-VonDutch*. `light_changes` missed Armin bar 55. The cue a light
show needs is the **end** of a sweep (top reached, cut, gap, drop landing) and what follows it; a
sweep end followed by nothing is a suspect detection.

## Method

1. `features.py`: harmonic stem (`artifacts/stems/harmonic.wav`, 32 kHz) -> STFT 4096/512 -> 6 bins per
   octave, 100 Hz-15.5 kHz, averaged per half-beat window of `beats.json`. Per window: `peak_hz` and
   `sharpness` (strongest peak over a 13-bin running mean), `hl_db` (10 log10 of energy > 2 kHz over
   energy < 500 Hz), `roll_hz` (99 % energy rolloff), `level_db`. Windows 50 dB under the song's p95
   level are NaN.
2. `detect.py`: per bar, slope (per bar, least squares on half-beat points) and consistency (|r|) over the
   last 1/2/4/8 bars for `hl`, `roll` (log2 Hz) and `peak` (log2 Hz): a running indicator.
3. State: `opening` if over a trailing 4 or 8 bar window `hl` rises >= 1.5 dB/bar or `roll` >= 0.15 oct/bar
   with consistency >= 0.6 (`closing` mirrors). A bar whose stem level is >= 6 dB under the previous four
   bars' median is a **dropout**: no state, and windows restart after it, so a gap ends a sweep. One-bar
   gaps bridged, runs under 3 bars dropped.
4. Sweep end = first beat of the bar after a run (on the grid). `end_kind` `cut` if `hl` snaps back >= 6 dB
   in that bar, else `top`.
5. `aftermath.py` (from `bar_features` rows, recomputed in memory): reference = mean mix RMS of the run's
   last two bars; hole = under 0.75 of it. `gap` = bar e hole, e+1 not; `break` = both holes; `drop` = e not a
   hole and a bar in e..e+1 reaches 1.25x or `kick_present` turns on; else `none`.
6. `confidence` = (0.3 + 0.7 x (0.5 consistency + 0.5 hl depth / 15 dB)) x 0.5 if `none`. Heuristic, not calibrated.

The peak Hz is reported but drives nothing: on *Armin* bars 55-58 it jumps 119 -> 1068 -> 189 -> 424 Hz
(chord tones), while the high/low ratio climbs -10 -> 0 dB. The rolloff is what tracks *Medicine*'s slow opening.

Output `reference/proposals/filter_sweep_v2.json`: `blocks[]` (`direction`, `start_s`, `end_s`, `start_bar`,
`end_bar`, `end_time`, `end_kind`, `aftermath`, `hl_change_db`, `roll_change_oct`, `consistency`,
`confidence`) and `bars[]` (`bar`, `start_s`, `state`, `hl_slope_4`, `roll_slope_4`).

## Run

```bash
docker compose run --rm --no-deps app python -m experiments.filter_sweep_v2.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.filter_sweep_v2.run export  --all-songs
docker compose run --rm --no-deps app python -m experiments.filter_sweep_v2.run score    # out/score.txt
docker compose run --rm --no-deps app python -m experiments.bar_features.run compute --all-songs  # picks up the new columns
docker compose run --rm test python -m pytest experiments/filter_sweep_v2 experiments/bar_features
```

`bar_features` reads this experiment's `cache/<song>.json`; `export` here recomputes the `bar_features`
table in memory, so the order is `compute` (here) -> `export` (here) -> `bar_features`.

## UI lane

**Filter Sweeps v2** (`filterSweepV2`, flask badge): one block per sweep run, label `opening -> gap`, tinted by
aftermath (`none` grey = suspect). Inspector: bars, end time, end kind, hl/roll change, consistency, confidence.

## Results (`out/score.txt`)

* **Armin - Revolution**: bars 51-58 `opening`, bar 59 (the gap: stem level -17 dB) no state; the run's end is
  109.39 s = bar 59 `top`, `aftermath: gap` (mix RMS .037 vs .055 before, .052 back at 60). Bars 55-58 are
  inside the run; the run starts earlier (51) than the target because a trailing 8-bar window lags.
* **Medicine-MilkInc**: bars 7-15 `opening` (hl 8-bar slope +1.4..+2 dB/bar over 9-14, rolloff 1.8 kHz -> 5.7 kHz);
  bar 16 is the 1-beat grid slip and carries no state; end 27.25 s (bar 16) `aftermath: drop`. Bars 9-15 of the
  asked 9-16 hold; bar 16 does not.
* **ayuni** 2 sweeps (v1: 0): opening 127.7-133.5 s (bars 65-68, aftermath `break`), opening 145.4-155.2 s (bars
  74-79, `none`). **Charli-VonDutch** 2 (v1: 0): opening 50.5-56.1 s (bars 28-31, `drop`), closing 126.3-135.5 s
  (bars 69-74, `none`, hl only -0.8 dB: weak). Listed for operator review.
* **Corpus**: 131 sweeps in 102 minutes (1.3/min; v1 had 79): 63 opening / 68 closing; aftermath `none` 85,
  `drop` 26, `break` 12, `gap` 8; end `top` 102 / `cut` 29.

**Thresholds chosen on validation songs** (*Armin*, *Medicine*; not held out): HL_SLOPE 1.5, ROLL_SLOPE 0.15,
MIN_CONS 0.6, DROPOUT_DB 6, MIN_RUN_BARS 3, HOLE_RATIO 0.75, DROP_RATIO 1.25. Medicine's earlier opening
(bars 7-8) and Medicine's block 21-33 are not scored.

**Known weaknesses.** State is a *trailing* window, so a run starts late-to-early by up to a window and the 8-bar
window makes slow builds read as sweeps (65 % end with nothing after them, so they are low confidence).
The dropout rule makes a gap end a run by construction, which flatters the Armin check. Kick attacks are
absent on Armin (hat bed), so its `drop` aftermath would rest on loudness alone.
