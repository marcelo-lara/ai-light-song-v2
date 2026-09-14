# Experiment — Tension Shape

## Status

**OPEN.** Candidate producer for `sections.json`'s `tension` field
(`docs/product-refinement-v3.6.md` item 6). Scores are **provisional** until
item 4's `segments.seed.json` is operator-reviewed — the slope half of this
method matches the item-4 seed rule, so a loss against the seed alone cannot
kill it.

Debugger lane: **`Tension Shape`**, flask badge, reads
`reference/proposals/tension_shape.json`.

## Method

Mix-loudness slope across the span (2nd-half mean minus 1st-half mean,
`loudness.json`), song-relative quintile-binned to 1-5, **+1** when a
`song_event_timeline.json` gesture `build`/`tension` phase overlaps the span,
**+1** when the sibling `experiments/phrase_periodicity` experiment's
`through-composed` regime overlaps the span (reads its existing
`reference/proposals/phrase_periodicity.json` — a file dependency, not an
import), clamped to 5. Confidence is the quintile-bin margin on the slope
only — `experiments/rhythm_energy_common.py`.

## How to run it

```bash
docker compose run --rm app ./experiment --song "/data/songs/<song>.mp3" --only tension_shape
```

or directly:

```bash
docker compose run --rm --no-deps app python -m experiments.tension_shape.run compute --song <name>
docker compose run --rm --no-deps app python -m experiments.tension_shape.run export --song <name>
docker compose run --rm --no-deps app python -m experiments.tension_shape.run score
```

Run on the 4 segment songs plus `Armin - Revolution`, **after**
`phrase_periodicity` has run for the same song (its proposal file feeds the
regime bump; absent, the bump is simply never true — no crash).

## Results

Not yet run — placeholder. Real numbers land in `out/score.txt` and this
section, and in `docs/experiments.md`, after the orchestrator runs
compute/export/score.

## Reach test

Candidate for `sections.json`'s `tension` field (fused by confidence
alongside the CLAP-character, Texture Novelty and Phrase Periodicity
adapters in `experiments/truth_common/adapters.py`). Not yet promoted.
