# Experiment — Energy Level

## Status

**OPEN.** Candidate producer for `sections.json`'s `energy` field
(`docs/product-refinement-v3.6.md` item 6). Scores are **provisional** until
item 4's `segments.seed.json` is operator-reviewed — the seed shares this
method (`segment_seeds.features.compute_seed`'s `energy` rule), so a loss
against the seed alone cannot kill it.

Debugger lane: **`Energy Level`**, flask badge, reads
`reference/proposals/energy_level.json`.

## Method

`0.5 * mean(loudness.json mix normalized_values in span) + 0.5 *
(arrangement_state.json stems-playing fraction in span)`, song-relative
quintile-binned to 1-5. Confidence = quintile-bin margin (distance from the
nearest bin boundary) — `experiments/rhythm_energy_common.py`.

## How to run it

```bash
docker compose run --rm app ./experiment --song "/data/songs/<song>.mp3" --only energy_level
```

or directly:

```bash
docker compose run --rm --no-deps app python -m experiments.energy_level.run compute --song <name>
docker compose run --rm --no-deps app python -m experiments.energy_level.run export --song <name>
docker compose run --rm --no-deps app python -m experiments.energy_level.run score
```

Run on the 4 segment songs plus `Armin - Revolution`.

## Results

Not yet run — placeholder. Real numbers land in `out/score.txt` and this
section, and in `docs/experiments.md`, after the orchestrator runs
compute/export/score.

## Reach test

Candidate for `sections.json`'s `energy` field (fused by confidence
alongside the CLAP-character adapter in `experiments/truth_common/
adapters.py`). Not yet promoted.
