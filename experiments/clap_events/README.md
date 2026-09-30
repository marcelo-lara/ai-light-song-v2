# Clap Events — accent detection by spectral shape, not omnizart's label

## TLDR

**Question.** Can a clap be told apart from drum-machine bleed by what its
spectrum looks like, when omnizart's own label cannot (product-refinement
v3.9 item 2)?

**Method.** Onset candidates from the drums stem (broadband +
1-6 kHz band-limited, unioned — `candidates.py`), classified by
`experiments/drum_hit_shape.py`'s 120 ms window: clap iff
`noise_share >= 0.50` (1-6 kHz) and `body_share <= 0.15` (120-400 Hz).
Thresholds and the window length are measured against the refinement's own
worked numbers — see that module's docstring for the reproduction table.

**Run.**
```
docker compose run --rm app python3 -m experiments.clap_events.run compute --song "Queen of Kings - Alessandra"
docker compose run --rm app python3 -m experiments.clap_events.run export  --song "Queen of Kings - Alessandra"
docker compose run --rm app python3 -m experiments.clap_events.run score
```

**Results (2026-09-30).**

| fact | result |
| --- | --- |
| Queen of Kings — 7/7 break claps (bars 42-48 beat 3) | **PASS** |
| Queen of Kings — no clap at 97.29 (rejected machine hit) | **PASS** |
| Queen of Kings — no clap on the drop-1 backbeat | **PASS** |
| Tutta L'Italia — claps on beats 2/4, bars 20-25 | **FAIL — 9/12.** Bars 20-21 (37.96, 38.89, 39.82) have no detectable 1-6 kHz energy in the drums stem at any window/offset tried (scanned +-300 ms, 20-200 ms windows); that register there is >=0.98 low-band. Either the clap is buried under a louder bass/kick note in the isolated stem, or genuinely absent from bars 20-21 specifically (a fill/pickup difference the operator heard in the full mix). Not a threshold-tuning fix — the signal is not present in this stem. Bars 22-25 (6/6) and bar 80 pass. |
| Tutta L'Italia — a clap in bar 80 | **PASS** |

## Known limitation

A loudness/onset gate alone was confirmed to fail exactly as the refinement
predicted — see `experiments/drum_hit_shape.py`'s docstring for the specific
counter-examples this shape test resolves.

The candidate generator occasionally fires twice within ~35 ms of the same
physical hit (seen once on Queen of Kings, 80.109/80.144) — both pass the
shape test as separate "claps". Not deduplicated further since it does not
affect any Done-when fact; a promotion pass should collapse near-duplicates
before writing `drum_events.json`.

## Output

`reference/proposals/clap_events.json` — `events: [{time, noise_share,
body_share, confidence}]`. Rendered as the **Clap Events** debugger lane
(point events).
