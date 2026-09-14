# Experiment — Rhythm Drum IOI

## Status

**OPEN.** Candidate producer for `sections.json`'s `rhythm.drums` field
(`docs/product-refinement-v3.6.md` item 6, method (a)). Scores are
**provisional** until item 4's `segments.seed.json` is operator-reviewed —
the seed shares this method, so a loss against the seed alone cannot kill it
(item 6's seed/incumbent circularity rule).

Debugger lane: **`Rhythm Drum IOI`**, flask badge, reads
`reference/proposals/rhythm_drum_ioi.json`.

## Method

Dominant inter-onset interval of `drum_events.json` events inside a segment
span, divided by the local beat period (`beats.json`), mapped to the nearest
of `half`/`quarter`/`eighth`/`sixteenth`/`eighth_triplet` by log-distance;
below 1 onset per bar -> `none`. Same rule as `segment_seeds.features.
drum_rhythm` (item 4's seed writer) — see `experiments/rhythm_energy_common.py`
for the shared math and its confidence formula (normalised margin between
best and second-best candidate).

## How to run it

```bash
docker compose run --rm app ./experiment --song "/data/songs/<song>.mp3" --only rhythm_drum_ioi
```

or directly:

```bash
docker compose run --rm --no-deps app python -m experiments.rhythm_drum_ioi.run compute --song <name>
docker compose run --rm --no-deps app python -m experiments.rhythm_drum_ioi.run export --song <name>
docker compose run --rm --no-deps app python -m experiments.rhythm_drum_ioi.run score
```

Run on the 4 segment songs (`ayuni`, `Cinderella - Ella Lee`, `_test_song`,
`What a Feeling - Courtney Storm`) and `Armin - Revolution` (fixture source).

## Results

Not yet run — placeholder. Scores land in `out/score.txt` after `run score`;
this section and `docs/experiments.md`'s entry get real numbers once the
orchestrator runs compute/export/score on the corpus above.

## Reach test

Candidate for `sections.json`'s `rhythm.drums` field (fused by confidence
alongside `rhythm_stem_autocorr`'s `(b)` and `rhythm_vocal_onsets`' `(c)` —
docs/product-refinement-v3.6.md item 6). Not yet promoted.
