# Product backlog

Parked work, not scheduled. One entry per idea: what, why, when it is ready.
Entries are numbered ("backlog item 2"). Promoting one moves it into a
`product-refinement-v*.md` and deletes it here. Numbers are never reused or
renumbered: a new entry takes the next number after the highest ever used.

- **[1] Energy/tension as a curve within stages.** Replaces the per-section 1–5
  scalars cut in v3.10 item 9, which cannot express a rise or fall inside a
  section. Derived from the published per-stem loudness and FFT bands, read
  per stage (a build's slope, a breakdown's depth). Ready after v3.10 items 2
  and 4; build only if show authoring needs more than `get_detail`'s
  loudness.
- **[2] Drum-hit shape checks: `clap_events`, `kick_check`, `crash_check`.**
  Three experiments with lanes, none promoted; numbers in each `README.md`.
  Needs an operator verdict per lane: promote into `drum_events.json`, keep
  as a clue layer, or archive (record it in `docs/experiments.md`).
- **[3] `crash` over-fires on bright hats/rides.** 17 of 23 songs publish
  > 15 crashes/min where real crashes are a few per section. Until fixed, no
  consumer treats `crash` as an accent. Follows backlog item 2's `crash_check` verdict.
