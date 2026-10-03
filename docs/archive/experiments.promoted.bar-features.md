# Bar Features — one row per bar from what already exists

[← archive index](experiments_archive.md)

**Promoted v3.12 item 32** (operator lane-review verdict: promote), ported into
`src/analyzer/stages/light_changes.py` (`light-changes`, phase 3, never audio),
and published as top-level `bar_features.json` by `publish-light-changes`
(v3.12 item 33). Replaced nothing: Medicine bars 9-17 showed in four artifacts
and was acted on by none; one per-bar table lets one detector read one thing.

Shipped: the per-bar table (loudness per source, 7 bands per source,
`brightness`, `transient_mean/std`, kick/snare/hat counts, vocals cover,
arrangement entries/exits, `kick_present`, `sweep_state`/`sweep_slope`, plus a
half-beat variant) in `artifacts/light_changes/bar_features.json`; the
published file is the slim projection (`bar`, `start`, `end`, `irregular`,
`brightness`, `transient_density`, `kick_present`, `sweep_state`,
`light_change_role`). Not shipped: `filter_sweep` overlap and the gesture
overlap columns (the old v1 sweep detector is not an input). No scorer: the
table makes no claim; it is judged through `light_changes`.

`experiments/bar_features/` stays in the tree as the reference (its README holds
the numbers); `src/` never imports it.
