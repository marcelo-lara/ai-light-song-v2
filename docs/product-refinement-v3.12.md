# Product refinement — v3.12

**Status: implemented** ([`implementation-plan-v3.12.md`](implementation-plan-v3.12.md)). Shipped and removed from this doc: per-bar feature table, light change points and roles, kick attacks, filter sweeps v2, texture published to the show, artifact cleanup (current state in [`analysis-definition.md`](analysis-definition.md), [`reference/downstream-contract.md`](reference/downstream-contract.md), [`mcp-definition.md`](mcp-definition.md)). What remains open is below.

---

## 3. Downbeat re-anchoring — outcome: gate not met

`experiments/downbeat_reanchor` (beat times unchanged; one phase per trusted run from kick-phase, impact and stem-entry votes; bars always 4 beats): downbeat F1 @ +-70 ms on the 5 Moises songs **0.024** / **0.163** vs allin1 **0.343**; zero bars != 4 beats outside `off_grid_spans` by construction (today's grid: 72 of 99 irregular bars). A constant phase per run cannot follow a real 1-beat slip (*Armin*), and the votes are thin. `timing.py` is unchanged; Medicine bar 16 is still a 1-beat bar and every bar after it one beat off.

**Remaining.** Let the phase change only inside an unresolved span (`docs/issues.md`). Done when: no bar != 4 beats outside `off_grid_spans` corpus-wide, and F1 above allin1's .343 on the Moises songs. Writes experiment first; `beats.json` `bar`/`beat`/`type` only on promotion, with the contract notes the plan item 30 lists.

---

## 7. Vocal cadence without lyrics — outcome: tier not shipped

`vocal_onsets.json` word onsets (all 27 songs) as a third `vocal_cadence.json` tier for the ~22 songs with no human/Moises lyrics: onset times only, word text never read or published. The 1-beat-rest rule scored pooled F1 **0.346** @ +-1 beat against lyric line starts (gate 0.7); `source` stays `null` without lyrics.

**Remaining.** Superseded by [`product-refinement-v3.13.md`](product-refinement-v3.13.md) item 3: cadence from the vocals stem's pitch track, no lyrics; the line-start gate is withdrawn (lyric lines are textual, not acoustic units).

---

## Carried over (operator actions, no build)

- Lane-review verdicts on the v3.10 experiments `filter_sweep`, `phrases`, `downbeat_anchors`, `section_names` (entries in `experiments.md`) and on the Filter Sweeps v2 and Kick Attacks lanes.
- Lane review of *ayuni* and *Charli-VonDutch* light-change placement, and of every song above 8 points/min (`docs/issues.md`).
- Confirm/reject the queued `verdict_check` on *Hideaway - Kiesza* `chorus_is_drop` in the debugger.
- Cross-repo: `ai-dmx-light-render`'s dead `fadeout.load_flagged_tail_window` (would read `artifacts/`) — removed there.
