# Kick Check — does an omnizart `kick` deserve its label?

## TLDR

**Question.** `Rapture - Nadia Ali`'s Breakdown/Chorus publish 57/37
kicks/min where the operator hears no kick at all — does the kick's own
spectral shape agree with omnizart, per-hit (product-refinement v3.9 item 2)?

**Method.** For every omnizart `kick` in `drum_events.json`: keep iff
`low_share >= 0.75` (20-150 Hz), `noise_share <= 0.10` (1-6 kHz, ruling out
hat/crash bleed), **and** a percussive-attack gate — the kick register's own
onset-strength envelope at that instant must clear `0.5x` this song's own
75th-percentile attack strength (`drum_hit_shape.attack_envelope`). The
attack gate is what separates a genuine kick transient from a sustained
sub-bass pad sharing the same `low_share`: measured on `Rapture`'s Breakdown,
the pad's attack ratio (post-onset RMS / pre-onset RMS) sits at 0.8-3.0x; the
Drop's real kicks sit at 17-150x.

**Run.**
```
docker compose run --rm app python3 -m experiments.kick_check.run compute --song "Rapture - Nadia Ali"
docker compose run --rm app python3 -m experiments.kick_check.run export  --song "Rapture - Nadia Ali"
docker compose run --rm app python3 -m experiments.kick_check.run score
```

**Results (2026-09-30), `Rapture - Nadia Ali`.**

| section | omnizart kicks | kept | kept/min | target | result |
| --- | --- | --- | --- | --- | --- |
| Breakdown 96.00-125.54 | 28 | 8 | 16.2 | <=5 | **FAIL** |
| Chorus 125.55-155.08 | 18 | 2 | 4.1 | <=5 | **PASS** |
| Drop 1 55.39-96.00 | 82 | 57 | 84.2 | >=100 | **FAIL** |
| Drop 2 169.84-210.46 | 74 | 60 | 88.6 | >=100 | **FAIL** |

## Why it does not fully clear the target, honestly

This is a genuine precision/recall tension, not an untried threshold:

- **Breakdown's 8 surviving "kicks" cluster at the section's own edges**
  (96.00-97.09s — the boundary with the preceding Drop — and 110.5-111.5s,
  125.3-125.53s — the boundary with the following Chorus/Drop). They are
  real kick-shaped transients bleeding in from the adjacent section's actual
  kick pattern, at the exact timestamp the published section boundary sits.
  Tightening the gates further to kill these also loses real Drop kicks
  (below), because they share the same shape.
- **The Drops lose ~15-18% of their own real kicks** to the same gates —
  a sweep over `low_share` in {0.5..0.85}, `noise_share` in {0.05..0.15},
  `attack_factor` in {0.5..1.5} never found one setting clearing both
  `<=5/min` on Breakdown/Chorus and `>=100/min` on both Drops
  simultaneously; every tightening that helped Breakdown cost more Drop
  recall than it gained precision. The two spectral shares plus a single
  attack ratio cannot fully separate "real kick played softly at a section
  edge" from "sustained pad" — they share the same low-frequency dominance
  and only differ in degree of attack, and the boundary cases sit in the
  overlap. A stronger check (e.g. cross-referencing the beat grid — genuine
  kicks in this corpus land on-beat, a held pad does not) is the next thing
  to try, out of scope for this pass.

Chosen thresholds (`verdict.py`): `LOW_MIN=0.75`, `NOISE_MAX=0.10`,
`ATTACK_FACTOR=0.5` — the best of the sweep above by total absolute
deviation from all four targets.

## Output

`reference/proposals/kick_check.json` — `kicks: [{time, verdict, low_share,
noise_share}]`, one row per omnizart `kick` event. Rendered as the **Kick
Check** debugger lane (keep vs reject shown distinctly).
