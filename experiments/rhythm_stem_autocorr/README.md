# Experiment — Rhythm Stem Autocorr

## Status

**OPEN.** Candidate producer for `sections.json`'s `rhythm.{drums,bass,
harmonic,vocals}` fields (`docs/product-refinement-v3.6.md` item 6, method
(b)). Scores are **provisional** until item 4's `segments.seed.json` is
operator-reviewed — the seed shares this method (`segment_seeds.features.
stem_rhythm`), so a loss against the seed alone cannot kill it.

Debugger lane: **`Rhythm Stem Autocorr`**, flask badge, reads
`reference/proposals/rhythm_stem_autocorr.json`.

## Method

Per stem (`bass`/`drums`/`harmonic`/`vocals`), strongest sub-beat
autocorrelation peak of that stem's 20 ms loudness curve
(`loudness.json`) at half/quarter/eighth/sixteenth/eighth_triplet lags of the
local beat period (`beats.json`); `vocals` is `"none"` where no
`vocals_phrase` overlaps the span. Confidence: normalised margin between the
best and second-best lag's correlation, or the honest distance below the
`MIN_AUTOCORR` floor for `"none"` — see
`experiments/rhythm_energy_common.py`.

## How to run it

```bash
docker compose run --rm app ./experiment --song "/data/songs/<song>.mp3" --only rhythm_stem_autocorr
```

or directly:

```bash
docker compose run --rm --no-deps app python -m experiments.rhythm_stem_autocorr.run compute --song <name>
docker compose run --rm --no-deps app python -m experiments.rhythm_stem_autocorr.run export --song <name>
docker compose run --rm --no-deps app python -m experiments.rhythm_stem_autocorr.run score
```

Run on the 4 segment songs plus `Armin - Revolution`.

## Results

Not yet run — placeholder. Real numbers land in `out/score.txt` and this
section, and in `docs/experiments.md`, after the orchestrator runs
compute/export/score.

## Reach test

Candidate for `sections.json`'s `rhythm.*` fields (fused by confidence
alongside `rhythm_drum_ioi`'s `(a)` and `rhythm_vocal_onsets`' `(c)`). Not
yet promoted.
