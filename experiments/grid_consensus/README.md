# Experiment — Bar grid and phrase grid by musical consensus

**Status: measured, negative/inconclusive, not promoted.** Nothing in `src/`
reads anything in here. Queue entry, with the same numbers in summary form:
[`../../docs/experiments.md`](../../docs/experiments.md)
(docs/experiments.md).

## The question

Beat tracking is good (7/7 impacts within 0.25 s of an essentia beat).
Downbeats are not: essentia, beat-this and allin1 hit 3/7, 3/7 and 4/7 and
disagree with each other, and `CLAUDE.md` says outright: do not assume a
correct bar grid. Everything downstream (`beats.json`'s `type: "downbeat"`,
`bar`) assumes one anyway.

> Can the downbeat **phase** (essentia's beat *times* are trusted; the open
> question is which beat is bar-1) be resolved by musical evidence — kick
> placement, chord-change concentration, section boundaries, gesture impacts
> — better than trusting any single tracker?

Scope, stated up front: this experiment assumes 4/4 throughout and resolves a
single global phase per song from essentia's own trusted beat sequence,
rather than re-deriving beat times or handling time-signature changes.

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.grid_consensus.run export
docker compose run --rm --no-deps app python -m experiments.grid_consensus.run score
```

Reads three existing caches as data (not code) dependencies: `beats.json`
(essentia, trusted), `experiments/allin1/cache/*.json` (already committed),
and `experiments/drop_detection/research/cache/beatthis/*.npz` (already
committed) — no new model or container needed. `score` reproduces
[`out/score.txt`](out/score.txt).

## Results

Full tables in [`out/score.txt`](out/score.txt). Gold set, 7 drop impacts.

**The evidence-weighting search is the actual finding here, and it is not
what the plan assumed.** The plan's hypothesis was that kick placement from
`drum_events.json` would be a strong phase discriminator ("harmonic rhythm
overwhelmingly lands on downbeats... kick placement..."). Measured: kicks in
this four-on-the-floor-heavy repertoire land **near-uniformly across all four
beat phases** (e.g. Titanium: `[77, 76, 65, 86]` — essentially flat). Every
weighting tried that included kick evidence at any nonzero weight scored **at
or below** chord-change evidence alone:

| weighting | hits @0.25s |
| --- | --- |
| kick-only | 1/7 |
| **chord-only (shipped)** | **3/7** |
| section-only | 2/7 |
| gesture-only | 3/7 |
| equal-all (kick included) | 2/7 |
| kick-heavy (as originally planned) | 2/7 |

Chord-change concentration turned out to be the strongest single signal.
Shipped weighting is chord-change-only, chosen by this measurement, not by
the plan's original assumption.

**Consensus vs. individual trackers, resolved phase, ±0.25s:**

| method | hits |
| --- | --- |
| essentia (own downbeat marking) | 3/7 *(CLAUDE.md)* |
| beat-this | 3/7 *(CLAUDE.md)* |
| **allin1** | **4/7** *(CLAUDE.md)* |
| this experiment's consensus | 3/7 |

**The consensus approach ties two of three individual trackers and does not
beat the best one (allin1).** This is a negative result for the specific
evidence-fusion method tried, not a confirmation of the hypothesis. On
`_test_song`, all four hypotheses agree confidently (phase 0, confidence
1.0) and the resulting downbeat still misses the impact by 0.66s — essentia's
own trusted beat *times* simply don't place a beat exactly on this impact,
which is consistent with (not contradicting) CLAUDE.md's downbeat warning: the
problem is deeper than picking the right beat out of four, on at least this
song.

**Phrase grid: a clear loss.** The derived 8-bar phrase edges score 0/7 at
±0.5s and ±1.0s, and 1/7 at ±2.0s — against allin1's already-measured raw
unmerged phrase edges at 3/7, 4/7, 6/7. The phrase-length-picking logic
(scoring 8 vs 16 bars against section/gesture evidence) did not get a chance
to matter much since the underlying bar anchoring is itself weak.

**Disagreement across the full 21-song corpus:** only 6/21 songs resolve
(confidence >= 0.45 and evidence-majority agreement) under the shipped
weighting; 15/21 come back `unknown`. Of the resolved songs, essentia's own
downbeat phase is overridden by evidence on 3/21. The high `unknown` rate is
itself informative — it says the chord-change signal, alone, is often too
sparse or ambiguous to confidently resolve a song's phase, which matches
`CLAUDE.md`'s standing warning better than a confident (and possibly wrong)
answer would.

## Conclusion

**Negative/inconclusive.** The specific fusion method tried does not beat the
best individual tracker on the gold set, and its phrase grid is clearly worse
than allin1's. The one solid finding is the kick-uniformity result, which
falsifies part of the plan's own reasoning and should inform any next
attempt: chord-change evidence is doing the real work, and needs either a
better source (the chord field's own boundary precision was not separately
audited here) or a genuinely stronger fourth evidence stream before this
approach is worth another round. `unknown` on 15/21 songs may be the most
honest thing this experiment produces — better than a confident wrong grid on
each of them.

## Reach test

`beats.json` (top-level, priority 4 in the input guide) and a
`phrase_boundary` hint category. Given the measured result — ties, does not
beat, the best available single tracker, and loses clearly on phrase edges —
**not ready to promote**. If allin1 is promoted for section structure
(pending its own entry), the honest next step is simply using allin1's
downbeat *phase* directly (it already wins this exact comparison at 4/7) and
retiring this fusion approach rather than iterating further on it.
