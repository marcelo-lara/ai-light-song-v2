# Experiment — Structural vs Micro

*(no external model or repo — classical 4-bar phrase-grid fit, numpy)*

## Status

**Measured, FAILED its kill condition, kept as a lane for one operator review
pass — kill candidate.** v3.4 item 8. Nothing in `src/` reads anything here.
Queue entry with the same numbers in summary form:
[`../../docs/experiments.md`](../../docs/experiments.md).

The debugger lane exists: **`4. Structural vs Micro`**, under Human Hints, flask
badge, reads `reference/proposals/structural_vs_micro.json`. `micro` blocks get a
distinct per-block tint (`structuralVsMicroMicro`) so the two classes read
differently at a glance.

**Do not tune to manufacture a pass.** **Do not re-open** `vocal_phrases`,
`grid_consensus` or `reactive_bands` — measured, none promoted, out of scope.

## Why? What for?

The pipeline **cannot express the distinction the operator marks in one file**: a
*structural* boundary that lands on the song's phrase grid (an intro→verse edge),
versus a *micro* cue that lives inside a phrase and never will (a pre-drop, a
near-silence, a 'hey', the sub-bar gesture phases). Both kinds sit in
`human_hints.json` with nothing telling them apart downstream.

This is **not** a precision filter for item 6 (Texture Novelty) — that was the
hypothesis the review started with, and it failed: averaged over all operator
edges the phrase-grid prior beats chance by only ~1.7–2.25× (refinement doc item
4). It is a **two-class split**: combine item 6's boundary set with item 7's bar
grid and label every proposed block `structural` | `micro`.

> Does a 4-bar phrase-grid fit label operator blocks `structural` vs `micro`
> better than block duration alone?

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.structural_vs_micro.run compute
docker compose run --rm --no-deps app python -m experiments.structural_vs_micro.run export
docker compose run --rm --no-deps app python -m experiments.structural_vs_micro.run score
```

`compute` re-derives one `cache/<song>.npz` per song from `data/analysis/**` —
including items 6 and 7's `reference/proposals/{texture_novelty,phrase_periodicity}.json`
outputs, which it **reads** (it does not import their code). `score` and `export`
read only the cache, so the tables reproduce on a checkout with no `data/`.

## Experiment Plan

**Method (fixed, not swept).**

1. **bar length** = median downbeat spacing from `beats.json` (period only).
2. **boundary set** = union of items 6 + 7 proposal-block edges, merged within
   0.5 s. Falls back to the operator block edges where a parent file is absent
   (`Queen of Kings` has no `texture_novelty.json` — item 6 ran on the 4 gold
   songs only).
3. **phrase grid** = lines every 4 bars. The phase offset is swept (400 steps +
   each downbeat) and the offset minimising the **median** edge-to-line distance
   over the boundary set is kept — this is the fit.
4. every operator block → `kind` + `grid_fit_bars`: `grid_fit_bars` is the
   better-locking of the two edges' distance to the nearest grid line, in bars;
   `kind` is `structural` when that is ≤ `0.12` bars, else `micro`. The `0.12`
   threshold is not tuned: the refinement doc's `Queen of Kings` fit puts
   structural edges at −0.06…0.00 bars and micro edges at 0.15…3.3 bars.

**Cheap baseline:** block duration alone — `< 1 bar ⇒ micro`.

**Operator-truth `kind`** (hand-checked against the five songs' hint lists,
`truth.py`): a title keyword decides where it can (`tension`/`impact`/`release`/
`pre-drop`/`micro`/`'hey'`/`spacer`/`drum hit` → micro; `intro`/`verse`/`chorus`/
`bridge`/`drop approach`/`drop build`/`breath`/… → structural), else duration
`< 1 bar ⇒ micro`. The keyword layer is the only thing that can separate the
phrase-grid predictor from the baseline on a block whose length disagrees with
its role — e.g. `Titanium`'s 3.2 s "drop tension".

**Metric:** per-class precision/recall/F1 and accuracy, pooled over the **four
gold songs**. `Queen of Kings` is reported separately (the 6-of-16 edge-lock
table), not in the metric.

**Kill condition:** the phrase-grid classifier fails to beat the duration-only
baseline on pooled macro-F1.

## Results evidence

Full tables: [`out/score.txt`](out/score.txt), reproduced by `run score`.

### Block-kind agreement — pooled, 4 gold songs (45 operator blocks, 23 structural / 22 micro)

| method | acc | macro-F1 | structural P/R/F1 | micro P/R/F1 |
| --- | --- | --- | --- | --- |
| **phrase-grid (4-bar fit)** | 0.42 | **0.41** | 0.41 / 0.30 / 0.35 | 0.43 / 0.55 / 0.48 |
| duration-only (`< 1 bar ⇒ micro`) | 0.80 | **0.80** | 0.77 / 0.87 / 0.82 | 0.84 / 0.73 / 0.78 |

Per song the phrase-grid classifier scores acc 0.27 / 0.47 / 0.40 / 0.60
(`_test_song` / `Titanium` / `Hideaway` / `Armin`); the baseline scores 0.80 on
every one.

### Kill condition — FAIL

`phrase-grid macro-F1 = 0.415`  <  `duration-only macro-F1 = 0.798`.

The phrase-grid fit does **not** beat block duration at labelling operator blocks.
Per the plan the lane is kept for one operator review pass, then removed by
Recipe B if the operator agrees. **Not tuned.**

### Phrase-grid prior vs chance (all operator edges)

Lock-rate ÷ chance lock-rate (`2·0.12/4 = 0.06`): `_test_song` 2.2×, `Titanium`
6.7×, `Hideaway` 1.7×, `Armin` 1.7×, `Queen of Kings` 6.8× — **a weak prior**,
consistent with the refinement doc's 1.3–2.25× framing (the two Eurovision-shaped
songs sit higher because their form is unusually grid-locked).

### `Queen of Kings` — 7 of 16 operator edges lock to the fitted 4-bar grid

`bar_len = 1.910 s`, `phrase_len = 7.640 s`, grid phase `0.898 s`.

| edge (s) | fit (bars) | kind |
| --- | --- | --- |
| 1.11, 16.32, 23.94, 31.57, 39.21, 62.16 | 0.06 – 0.11 | structural |
| 46.52 (Pre-drop phrase) | 0.112 | structural (marginal) |
| 45.0, 47.2, 48.7, 52.1, 52.5, 55.9, 56.3, 59.9, 63.95 | 0.24 – 1.19 | micro |

The **six** edges the refinement doc names lock cleanly; a seventh (46.52) is a
marginal call at exactly the threshold. The nine that miss are the sub-bar
micro-events — the pre-drop, the near-silence, the micro break, the 'hey' — as
the refinement doc predicts.

## Conclusion

**Killed on the metric.** The 4-bar phrase-grid fit labels operator blocks
`structural`/`micro` at macro-F1 0.42, well below block duration's 0.80. The
distinction is real (on `Queen of Kings` the six structural edges lock to ≈ 0.1 s
and the micro-events clearly do not), but on the gold corpus the *lengths* of the
operator's blocks already carry that information — a micro-event is short, and
that is enough. The phrase grid adds a weak prior that, pooled, hurts more than
it helps because a long block whose edges happen to miss the grid gets
mislabelled `micro`.

What survives the review: the `grid_fit_bars` number itself is an honest
per-edge signal a reviewer can read, and the `Queen of Kings` edge-lock table
reproduces the refinement doc's finding. Neither is promotable on this result.

## Reach test

Time-bearing output → `reference/proposals/structural_vs_micro.json`, rendered as
the **`4. Structural vs Micro`** lane. Not promoted, no top-level file, nothing
in `src/` or `mcp/` reads it — and on this result, not a promotion candidate.
