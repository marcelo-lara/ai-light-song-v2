# Experiment — Bar Features

*(no external model or repo — fusion of existing artifacts, numpy)*

## Status

**Built and run 2026-10-03 (v3.12 item 1): 27 songs, one row per bar plus a
half-beat variant.** A feature table, not a claim: the input to
`experiments/light_changes` (item 2) and to later detectors, so they stop
reading artifacts one by one. Queue row enabled. Nothing in `src/` reads it.

## Why? What for?

Medicine bars 9-17 was visible in four artifacts (brightness, transients, drum
hits, stem entries) and acted on by none. One table makes each change a column
move at a bar.

## Method (`features.py`)

Windows from `beats.json`: a bar is a run of consecutive beats with the same
`bar` number, `[start_s, end_s)`; the last window ends one median beat after the
last beat. **A bar whose length is not 4 beats is flagged** (`irregular`,
`beats_in_bar`) and never repaired (grid re-anchoring is item 3; Medicine bar 16
is 1 beat, bar 1 is almost always a 5-7 beat pickup). `off_grid` marks windows
mostly inside `beats.json` `off_grid_spans`. Per window:

| Field | Source |
| --- | --- |
| `loud_rms`, `loud_norm` (mix, bass, drums, harmonic, vocals) | `loudness.json` `values` / `normalized_values`, mean |
| `bands` (7 per source: mix + 4 stems) | `fft_bands{,.<stem>}.json`, mean level |
| `brightness`, `transient_mean`, `transient_std` | mix FFT frames `brightness_ratio`, `transient_strength` |
| `kick`, `snare`, `hat` | `drum_events.json` counts (omnizart; known over-labelling) |
| `kick_attacks`, `kick_present` | `reference/proposals/kick_attacks.json` (v3.12 item 29): non-echo mix-audio kick attacks; present = >= 2 confident in a bar (1 per beat if the bar is under 2 beats), >= 1 in a half-beat window |
| `vocals_cover` | fraction covered by `arrangement_state.json` `vocals_phrase` |
| `entered`, `left`, `playing` | arrangement blocks starting in the window / block at the midpoint |
| `sweep` `{opening, closing}` | overlap fraction with `reference/proposals/filter_sweep.json` |
| `sweep_slope`, `sweep_state` (bars only) | `experiments/filter_sweep_v2/cache` (v3.12 item 31): 4-bar slope of the high/low band ratio (`hl`, dB/bar) and of the 99 % rolloff (`roll`, oct/bar); state `opening` / `closing` / null |
| `gestures` | `song_event_timeline.json` overlap fraction per type (point events: 1.0 if inside) |

`half_beats[]` repeats the signal columns only (loudness, mix bands, brightness,
transients, drum counts, kick columns) for items 4/5. A missing input file raises.

## Run

```bash
docker compose run --rm --no-deps app python -m experiments.bar_features.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.bar_features.run export  --all-songs
docker compose run --rm test python -m pytest experiments/bar_features
```

Needs `reference/proposals/filter_sweep.json`, `reference/proposals/kick_attacks.json` and `experiments/filter_sweep_v2/cache/<song>.json` (`filter_sweep_v2.run compute`) first (queue order handles it).

## UI lane

**Bar Features** (`barFeatures`, flask badge): one block per bar, label = bar
number, tinted by that bar's brightness tercile within the song, grey when the
bar is not 4 beats. Caption: RMS per stem, brightness, transients, drum counts.

## Results

Validation set, current beats.json bars, read straight from the table:

- **Medicine** — bar 8: brightness .55 -> .68, drums RMS .002 -> .023, hats 3;
  9: kicks/snares start (k3 s3 h7), `bass` entered; 10: `bass` left (bass RMS
  .009 -> .002); 10-14 steady (mix RMS .019-.021, k4-6 s3 h8); 16 is the 1-beat
  bar, `build` gesture from 27.25; 18-19 drum roll k12 then k9, 19 `drums` left,
  brightness .79 -> .31; 20-22 k0-5 h0-1, brightness ~.30; 23 bass RMS .0005 ->
  .015, mix RMS .024 -> .035.
- **Armin** — 55-58 bands 5-6 (the top two) climb .62 -> .93 / .59 -> .79 and
  brightness .83 -> .91; 59 low bands collapse (.29/.33), kick 0, mix RMS .052 ->
  .037, `harmonic` and `vocals` left; 60 kick 13, bands 1-2 back to .9+,
  brightness .96, transient mean .097.

Medicine mix RMS in `loudness.json` is ~.02 here, not the .19 in the refinement
doc (that figure is another scale); the flatness over bars 4-15 holds either way.
