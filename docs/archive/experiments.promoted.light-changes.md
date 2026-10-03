# Light Changes — where the light should change, and what kind of change

[← archive index](experiments_archive.md)

**Promoted v3.12 item 32** (operator lane review: Armin good; Medicine, ayuni,
Charli-VonDutch very good), ported into `src/analyzer/stages/light_changes.py`;
published as `light_change` rows of `song_event_timeline.json` and the
`light_change_role` column of `bar_features.json` (item 33), projected by `mcp/`
(item 34). Replaced nothing (`texture_novelty`, archived negative as a
segmenter, is re-measured here as one input).

**Experiment: 7 of 8 targets, 4.7 points/min** (Armin 55, a slow ramp, missed;
loudness-only 3/8). **In `src/`: 8 of 8 targets within one beat with the right
role, Medicine 10-14 empty, 494 points / 103.0 min = 4.80/min over 27 songs.**
What changed in the port: Armin 55 is found by the filter-sweep ramp onset
(`filter_sweep_v2` state as an input); the point time is the beat containing the
change (half-beat table, floored, on the grid); `confidence` is `null` with a
`confidence_reason` (uncalibrated). Caveats: every threshold and the role rules
were chosen on Medicine and Armin (not held out); Medicine 8/19/23 land 0.95-1.00
beat early; one extra Medicine break at bar 18. Open items: `docs/issues.md`.

`experiments/light_changes/` stays in the tree as the reference; `src/` never
imports it.
