# Experiment — Downbeat reanchor

*(no external model — classical; reads item 29's `kick_attacks.json`, `song_event_timeline.json` impacts and `arrangement_state.json` entries as data)*

## Status

**Built and run 2026-10-03 (v3.12 item 30). The promotion gate is NOT met; not promoted.**
Downbeat F1 @ +-70 ms vs Moises, pooled over the 5 Moises songs: **0.024**
(confidence-bearing downbeats, the incumbent's convention) / **0.163** (every downbeat,
abstentions included) against allin1's **0.343** and `downbeat_anchors`' 0.301. Irregular
bars outside `off_grid_spans`: **0** corpus-wide (47 under today's grid), so that half of
the gate holds, by construction. `timing.py` is unchanged; items 32+ proceed on the old
grid. Queue row enabled (after `kick_attacks`). Debugger lane **Downbeat Reanchor**,
flask badge.

## Why? What for?

Medicine bar 16 is one beat long, so every bar after it is one beat off; the cue-authoring
model reads bar numbers. Can bar labels be rebuilt from facts that sit on a downbeat (kick
phase, impacts, bass/drums entries), never warping time, and beat allin1's phase?

## Method (`anchors.py`, pure; `build.py`, I/O)

Beat times are never touched. A bar is always 4 beats, so inside a **trusted run** (the
beats between `off_grid_spans`) the downbeat phase is one residue of the beat index mod 4;
a slip would need a bar of another length, which is never published.

1. **Votes** for "this beat is a downbeat": *kick-phase* (every stepped bar, an 8-bar
   window; the phase of four carrying most non-echo kick attacks, only if it carries 1.5x the
   runner-up and >= 6 attacks, so four-on-the-floor abstains; weight 0.25 per window), *impacts*
   (`start_time` on a trusted beat within 1/4 beat; weight = confidence), *bass/drums entries*
   (`entered` of an arrangement block; weight = confidence, 0.25 when null).
2. **Run phase** = highest summed vote. No vote -> allin1's majority phase (`beat == 1` rows),
   every downbeat of the run unresolved. No allin1 either -> the previous run's phase.
3. **Confidence** of a downbeat = share of the votes within +-16 beats that agree with the run
   phase, kept only when >= 0.75 and the evidence >= 1.0; otherwise `downbeat_confidence: null`
   and the downbeat sits in an unresolved span (`spans[]`).
4. **Labels**: a leading pickup is its own partial bar 1; bars count from the first downbeat.
   Untrusted beats between runs continue the previous run's counting, so a phase change may
   only happen inside a bar that holds an off-grid beat.

Constants fixed before scoring (not tuned): `KICK_MARGIN` 1.5, `KICK_MIN_ATTACKS` 6,
`KICK_WEIGHT` 0.25, `SNAP_BEAT_FRAC` 0.25, `NULL_CONF_WEIGHT` 0.25, `LOCAL_BEATS` 16, `AGREE_MIN`
0.75, `EVIDENCE_MIN` 1.0. No threshold was chosen on Medicine, Armin, ayuni or Charli-VonDutch.
A 24-point sensitivity grid (`AGREE_MIN` .5/.75, `EVIDENCE_MIN` .25/1, `KICK_WEIGHT` .1/.25/1,
`KICK_MARGIN` 1.2/1.5), run after seeing the result and **not adopted**, ranged 0.007-0.111
(confidence-bearing) and 0.072-0.166 (all downbeats): nothing near 0.343.

## Scoring

Same method as `experiments/downbeat_anchors` (`_score_downbeats`, 70 ms, range of the Moises
chords). Irregular = a bar whose beats carry the same `bar` number and are not 4; `outside`
skips a bar holding an off-grid beat and the two song-edge partials (pickup, trailing remainder),
`strict` counts every one.

| Song | allin1 | reanchor (conf.) | reanchor (all) |
| --- | --- | --- | --- |
| Armin - Revolution | 0.606 | 0.000 | 0.000 |
| Hideaway - Kiesza | 0.060 | 0.000 | 0.016 |
| Queen of Kings - Alessandra | 0.878 | 0.143 | 0.954 |
| Titanium - David Guetta ft Sia | 0.000 | 0.000 | 0.000 |
| _test_song | 0.618 | n/a | 0.000 |
| **Pooled (462 ref.)** | **0.343** | **0.024** | **0.163** |

Irregular bars outside `off_grid_spans`: today's grid 47 (Medicine 4), reanchor **0** (strict, with
song edges: 74). Full table: `out/score.txt`.

## Why it fails

* **A constant phase per run cannot follow a real slip.** *Armin*'s single trusted run holds
  Moises downbeats on two different residues (28 on one, 30 on another): the music slips by a
  beat and allin1's 16-bar windows follow it, a constant phase cannot. Zero irregular bars and
  tracking a slip are the same constraint pulling opposite ways.
* **The votes are thin and often wrong.** Armin's votes spread over all four residues (3.7 /
  7.4 / 5.2 / 6.8); *Hideaway* is on the wrong tempo grid; *Titanium* votes for the same
  residue as allin1 and both disagree with Moises (the documented 2-beat offset); only *Queen of
  Kings* is right (0.954 with all downbeats); `_test_song`'s votes pick the wrong residue.
* **Kick phase carries almost nothing.** `kick-only` scores 0.000 (18 predicted); item 29's click
  gate leaves most dense mixes with few attacks, and four-on-the-floor has no phase.
* Confidence rule: only 6 of 41 confident downbeats are right; 75 of 456 of all of them.
  Even an oracle phase per run could not reach 0.343 pooled on these songs (about 0.27 with all downbeats).

## Not tried / next

* Letting the phase change only at an unresolved span (relaxes zero-irregular to "irregular only
  where unresolved") and following allin1's windows between anchors.
* Per-kind anchor audit: which impacts/entries really sit on Moises downbeats.

## Reproduce

```bash
docker compose run --rm --no-deps app python -m experiments.downbeat_reanchor.run export --all-songs
docker compose run --rm --no-deps app python -m experiments.downbeat_reanchor.run score   # out/score.txt
docker compose run --rm test python -m pytest experiments/downbeat_reanchor -q
```

`export` writes `reference/proposals/downbeat_reanchor.json` (`runs[]`, `spans[]`, `bars[]`,
`beats[]` with the labels that would replace `beats.json`'s `bar`/`beat`/`type`/`downbeat_confidence`).
Debugger lane **Downbeat Reanchor**: one block per bar, label = re-anchored bar number, grey where
`downbeat_confidence` is null.
