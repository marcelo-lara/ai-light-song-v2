# Experiment — Reactive band dynamics

**Status: measured, negative-leaning on the headline hypothesis, not
promoted.** Nothing in `src/` reads anything in here. Queue entry, with the
same numbers in summary form:
[`../../docs/experiments.md`](../../docs/experiments.md)
(docs/experiments.md).

## The question

MilkDrop's entire audio vocabulary is seven numbers — `bass`/`mid`/`treb` and
their damped twins plus `vol` — normalised against a *local running average*,
not a whole-song range. `artifacts/essentia/fft_bands.json` has strictly more
raw material (seven bands, `brightness_ratio`, `transient_strength`,
`dropout_strength`) but normalises against the whole song's 5th-95th
percentile, so a hit inside a quiet breakdown reads as numerically small even
when it is unmistakable to the ear.

> Does locally auto-gaining the same band-power signal find drop impacts
> better — especially inside quiet passages — than the incumbent's
> whole-song-percentile normalisation, at a fair (matched) firing budget?

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.reactive_bands.run compute
docker compose run --rm --no-deps app python -m experiments.reactive_bands.run export
docker compose run --rm --no-deps app python -m experiments.reactive_bands.run score
```

`bands.py` replicates the incumbent's exact FFT frame parameters (44100 Hz,
4096-sample Hann frames, 50 ms hop) so the *only* difference from
`fft_bands.json` is the normalisation — deliberately, so the ablation below is
fair on that one axis. `compute` computes raw (pre-percentile) band power for
the mix and all four stems; `export` writes per-beat/per-bar aggregates plus
a discrete accent list to `reference/proposals/reactive_bands.json`; `score`
reproduces [`out/score.txt`](out/score.txt).

## Results

Full tables in [`out/score.txt`](out/score.txt). Gold set, 7 drop impacts.

**A methodology bug was caught and fixed mid-run, and the fix matters more
than the original result.** The first ablation pass applied the *same
absolute* accent threshold to both normalisations. That is not a fair test:
the local ratio is unbounded (`power / running_mean`, can spike past 10), the
incumbent's percentile ratio is clipped to `[0, 2]` by construction — so a
threshold like `2.0` made the percentile curve fire **~0 accents regardless
of how good its normalisation was**, an artifact of the threshold, not a
finding about which normalisation is better. Fixed by binary-searching each
curve's own threshold to a matched accents/min budget (~29/min, the shipped
rate) before comparing recall — the only fair comparison.

**Honest result after the fix:**

| normalisation | ±0.25s | ±0.5s | ±1.0s | accents/min |
| --- | --- | --- | --- | --- |
| local running mean (2s) | 2/7 | 4/7 | 5/7 | 29.2 |
| **whole-song percentile (incumbent)** | **5/7** | **7/7** | **7/7** | 29.3 |

**At a matched firing budget, the incumbent's normalisation wins the
drop-impact recall comparison outright.** This is the opposite of the entry's
headline hypothesis and is reported as such — this repo values a
documented dead end over a repeated one. The low-loudness-passage hypothesis
this entry was actually designed around — does local normalisation help
*specifically* where the whole-song percentile should fail — has only **2**
qualifying impacts across the whole gold set (both tie 2/2 either way); that
is the noise-floor case, not resolved by this run either way.

**What still favours local normalisation:** the un-matched, "as shipped"
comparison against a truly naive detector — thresholded raw drums-stem RMS,
no band split, no auto-gain — the reactive-bands accent detector wins on
recall (4/7, 5/7, 6/7 vs 3/7, 4/7, 4/7) while firing 4.5× *less* often
(29/min vs 130/min). And the **primary deliverable was never the discrete
accent list** — it is the dense per-beat/per-bar `bass`/`mid`/`treb`
+ `_att` stream MilkDrop actually reads continuously; only the accent
extraction (a threshold applied on top) was measured here. That stream's own
value as a continuous "how hard, right now, relative to a moment ago" signal
is not directly tested by drop-impact recall and remains a plausible, untested
claim.

**Accent-threshold calibration.** The first value tried (0.5) fired 91
accents/min — useless as a discrete list. The full sweep (`out/score.txt`)
picked 2.0 (29/min, 5/7 @0.5s) as the shipped default; recall degrades
smoothly as the threshold rises, with no obvious "right" answer — a token-
budget decision as much as an accuracy one.

**Window sweep:** 2 s scored best among {1, 2, 4, 8}s at matched rate (5/7
@0.5s); the bar-length window (per-song median) is close behind (5/7) and is
arguably the more principled choice since it adapts to tempo — not adopted as
default only because it scored no better on this small a gold set.

## Conclusion

The normalisation ablation this entry exists to run came back **against**
the local-auto-gain hypothesis for discrete accent extraction, once measured
fairly. That is the headline result, not the accents-per-minute win over a
naive RMS baseline. Before any promotion discussion: (1) the dense per-beat
stream itself needs its own measurement, separate from accent extraction —
it's a different claim; (2) the low-loudness hypothesis needs more than 2
hand-marked qualifying impacts to test; (3) if local normalisation is kept at
all, it should be for the continuous stream, not as a replacement accent
detector.

## Reach test

A new dense artifact plus per-beat/per-bar aggregates — the input guide
explicitly invites this. Accents would become `song_event_timeline.json`
events with a real `intensity`. Given the ablation result above, **not ready
to promote** as a normalisation replacement; the continuous-stream claim is
untested and would need its own measurement before this question is settled.
