# Experiment — Light Changes

*(no external model or repo — change-point detection on `bar_features`, numpy)*

## Status

**Built and run 2026-10-03 (v3.12 item 2): 27 songs, 7 of 8 validation targets
hit at 4.7 points/min.** A proposal to audition; nothing validated by ear
(no ground truth beyond the two described songs). Nothing in `src/` reads it.
Queue row enabled (needs `bar_features` first; queue order handles it).

## Why? What for?

A light show must follow changes that sit inside a section and leave loudness
flat (Medicine bars 8-23). Question: *do multi-feature change points on the
per-bar table find the operator-described light changes, with the right role,
without firing on steady bars and without firing everywhere?* Scored against
described light changes, not section boundaries. Cheap baseline: **loudness-only**
change points (same walk, mix-loudness only).

## Method (`detect.py`)

1. Channels from `bar_features.json`: log mix/stem loudness, band groups, brightness,
   transients, hit counts (per nominal bar), vocal cover, arrangement events, and
   `texture_novelty` (`texture.py`: that experiment's Foote novelty on its 28-dim
   per-stem band feature, peak within +-0.2 s of the bar start; one-sided: only a rise counts).
2. A window under 2 beats (a grid slip, Medicine bar 16) is merged into the next one,
   keeping the slip's start; the grid itself is not touched.
3. Walk the bars: each bar vs the median of the previous <= 8 bars **of the current
   segment**; a point starts a new segment, so a settled new state is not re-flagged.
   For the bar right after a point the pre-point reference is kept too, and it fires
   if a group escalated by >= 2.5 sigma (a fill, then the groove lands).
4. Per channel z = delta / robust spread of the song's own bar-to-bar differences
   (floored). The detector pools **mix-level** groups only (loudness, low band, high
   band, texture, hits, vocal cover, arrangement, novelty); stem channels feed the role
   rules, because a stem moving alone (a fill's drum decay) is not a light change.
   A bar fires when `S = sum_g clip(max|z|_g - 2, 0, 5) >= 7`. No fixed bar grid.
5. Roles are ordered rules over signed deltas plus the next bar: `gap` (sub and highs
   collapse, sub back next bar), `drop` (sub up with loudness/kick), `fill` (drum level
   up, falling next bar, no kick/snare pulse), `groove_in` (hit counts up from a near-empty
   baseline), `build` (brightness/highs/transients up), `break` (the same down);
   anything else is `unknown`. `confidence` is `null`: the score is not calibrated.

**Honesty about tuning.** The structure (segment reset, staged second step, short-window
merge, stem channels role-only) and the role rules were designed while looking at the
Medicine and Armin tables, which the refinement doc itself describes; those two songs are
**not** an independent test of the role rules. Thresholds are round numbers; the one
selected on data is S >= 7: the highest round value that kept 7/8 hits (5/6/7 all hit 7/8;
8 hits 5/8) while cutting the corpus rate from 6.6 to 4.7 points/min.

## Run

```bash
docker compose run --rm --no-deps app python -m experiments.light_changes.run compute --all-songs
docker compose run --rm --no-deps app python -m experiments.light_changes.run export  --all-songs
docker compose run --rm --no-deps app python -m experiments.light_changes.run score    # out/score.txt
docker compose run --rm test sh -c "python -m pytest experiments/light_changes"
```

## UI lane

**Light Changes** (`lightChanges`, flask badge): one block per point (the bar it starts),
label = role, tinted per role (`unknown` grey); inspector lists the groups that moved
and the score.

## Results

Hit = a point within one beat of the target bar's start. Current `beats.json` bars.

| Target | Got | Role |
| --- | --- | --- |
| Medicine 8 fill | bar 8, +0.00 s | fill ok |
| Medicine 9 groove_in | bar 9, +0.00 s | groove_in ok |
| Medicine 16 build | bar 16 (merged 1-beat window), +0.00 s | build ok |
| Medicine 19 break | bar 19, +0.00 s | break ok |
| Medicine 23 drop | bar 23, +0.00 s | drop ok |
| Armin 55 build | **MISS**: nearest point bar 52 (-5.5 s) | - |
| Armin 59 gap | bar 59, +0.00 s | gap ok |
| Armin 60 drop | bar 60, +0.00 s | drop ok |

Medicine steady bars 10-14: **0 points**. Medicine also gets points at 18, 20, 21 (the
kick roll peak and the break's continuing steps). Armin 55-58 is a slow ramp (bands 5-6
.62 -> .93 over four bars): no single bar steps enough against the previous bars, so a
step detector is blind to it; that is item 5's job (sweep slope), not tuned around here.

Corpus (27 songs): **4.71 points/min** (per-song median 4.57, range 1.5-8.8; Medicine
and Armin are the two densest at 8.8 / 8.7, ayuni 8.8). Roles: break 162, drop 152,
build 124, groove_in 18, gap 12, fill 12, unknown 4: the rare roles are rare, the
rest lean on three labels.

Baseline and ablation, same 8 targets (`out/score.txt`):

| Detector | points/min | hits |
| --- | --- | --- |
| light_changes, S >= 7 | 4.71 | 7/8 |
| loudness-only, \|z\| >= 3 | 3.49 | 3/8 |
| loudness-only, rate-matched (\|z\| >= 2.5) | 4.60 | 5/8 |
| loudness-only, \|z\| >= 1.75 | 7.02 | 7/8 |
| light_changes without texture_novelty | 4.08 | 2/8 |

At a matched rate the multi-feature detector beats loudness-only (7/8 vs 5/8 at ~4.7/min),
and loudness-only needs ~7/min to reach 7/8. With 8 targets that is suggestive, not
statistical. **texture_novelty carries the result**: without it the same threshold hits
2/8; it was a negative section-boundary detector (F1 0.29) but is the strongest light-change
input here. Loudness-only has no roles.

*ayuni* (24 points, 8.8/min) and *Charli-VonDutch* (7 points, 2.6/min) have no bar-level
truth. `filter_sweep` finds 0 sweeps on both; this detector reports changes (ayuni: 24;
Charli-VonDutch bars 15, 17, 40, 53, 84, 85, 87), which can include sweep ends but
says nothing about sweep starts or slopes. Judge by the lane.
