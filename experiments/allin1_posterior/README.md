# Experiment — allin1's label posterior

**Status: measured, negative on item 2. Item 1 was moot — already shipped.**
Nothing in `src/` reads anything in here. Full entry:
[`../../docs/experiments.md`](../../docs/experiments.md#allin1s-label-posterior--the-structure-it-already-computes-and-throws-away).

## The question

`segmentation.py` ships an argmax over allin1's ten-label frame posterior,
quantised to 8 bars, discarding the rest — but the pipeline already caches
the full posterior (`analyzer.allin1_cache`) at zero marginal cost. Two
questions, no model run:

1. Does per-section posterior entropy make a real confidence?
2. Do "shadow labels" — a non-argmax label sustaining a share of the
   posterior the argmax discards — mark real, un-published structure
   (e.g. `Armin - Revolution`'s `break`, 30% of the posterior across
   143-175s, invisible to `sections.json`)?

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.allin1_posterior.run export --all
docker compose run --rm --no-deps app python -m experiments.allin1_posterior.run score
```

`export` writes `reference/proposals/allin1_posterior.json` per song
(`shadow_labels`, plus a `section_entropy_parity_check` against production).
`score` scores the 4 gold songs' shadow-label boundaries against
`sections.json` (incumbent) and an even grid at matched budget (baseline).

## Results

**Item 1 (entropy confidence) is a non-result — it already shipped.**
`segmentation.py::_function_confidence_for_span` (`1 - mean posterior
entropy` per section) already backs `sections.json`'s `function_confidence`
field. This entry's original "not yet run" status was stale; nothing to add.

**Item 2 (shadow labels) reproduces the worked example, loses on the score.**
Detected `Armin` `break` spans 144.31-155.53s and 155.57-168.16s (mean share
0.32/0.32) against the original 143.4-175.0s/0.30 observation — zero overlap
with any published section, confirmed. Boundary recall (of hint boundaries)
at matched `bounds_per_min`, shadow labels vs the even-grid baseline:

| song | shadow @0.1/0.25/0.5s | even-grid @0.1/0.25/0.5s |
| --- | --- | --- |
| `_test_song` | 0/0/2 | 1/3/7 |
| `Hideaway - Kiesza` | 0/1/3 | 1/2/3 |
| `Armin - Revolution` | 5/7/8 | 6/7/8 |
| `Titanium - David Guetta ft Sia` | 0/2/6 | 1/2/4 |

Shadow labels lose to even-grid on 3 of 4 songs; only ties/wins at ±0.5s on
`Titanium`. `sections.json` (the incumbent) still wins outright where it has
any boundaries at all (`_test_song`, `Armin`) and is empty on `Hideaway`/
`Titanium` — full numbers in `docs/experiments.md`.

## Conclusion

Not promoting. Item 1 needs no action. Item 2's shadow-label boundaries are
not specific enough to clear a trivial baseline at a matched firing budget —
the same failure mode as several other entries in this queue (high recall at
an inflated budget, not proven against one that's controlled for). The
**allin1 Posterior** debugger lane renders `shadow_labels` for eyeballing why.
