# Filter Sweeps v2 — a sweep as a running slope, and its end as the cue

[← archive index](experiments_archive.md)

**Promoted v3.12 item 32, in part** (ported as plan item 32), into
`src/analyzer/stages/harmonic_spectrum.py` (`extract-harmonic-spectrum`, 1.5,
`artifacts/harmonic_spectrum/half_beats.json`) and the sweep-state logic of
`light_changes.py`. Succeeds `filter_sweep` (v3.10, centroid over 7
per-band-normalised bands; found 0 sweeps on Armin, ayuni, Charli-VonDutch),
which stays an unshipped experiment.

Shipped: half-beat harmonic-stem spectrum (high/low ratio, 99 % rolloff), per-bar
slope and consistency, `sweep_state` (`opening`/`closing`/null) as a column of
`bar_features.json`, and the ramp-onset walk-back that finds **Armin bar 55**.
Not shipped: the sweep **end** event and `aftermath` (no consumer); resonant peak
Hz is reported but drives nothing (it jumps between chord tones). Experiment
result: 131 sweeps (1.3/min), 65 % with `aftermath: none`; Armin 51-58 opening
ending at bar 59 `gap`; Medicine 7-15 opening; ayuni 2 and Charli-VonDutch 2
sweeps. Thresholds set on Armin and Medicine (not held out). Open items:
`docs/issues.md`.

The "Filter Sweeps v2" debugger lane still reads
`reference/proposals/filter_sweep_v2.json` until re-pointed or retired
(`docs/issues.md`); `experiments/filter_sweep_v2/` stays in the tree as the reference.
