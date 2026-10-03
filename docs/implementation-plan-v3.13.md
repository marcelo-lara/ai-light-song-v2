# Implementation plan — v3.13

**Status: planned.** Turns [`product-refinement-v3.13.md`](product-refinement-v3.13.md) into an ordered worklist for a Sonnet implementer in batch mode. The refinement doc holds the rationale; this plan says what each item builds, how it is checked, and what must not be undone. Items continue v3.12's numbering (28–38 shipped). Branch: `v3.13`.

## Item order

| # | Item | Refinement | Kind | Depends on |
| --- | --- | --- | --- | --- |
| 39 | Pre-flight | — | docs + baseline numbers | — |
| 40 | Round toward the bar edge | item 1 | `src/` | 39 |
| 41 | Kick snap | item 2 | `src/` + contract | 40 |
| 42 | Held-out validation and corpus run | validation table | data | 40, 41 |
| 43 | Close-out | — | docs | 39–42 |

**Scope.** Point times only. `beats.json` is never written; no bar is relabelled; no threshold of the detector (`detect`, `refine_offset`, sweep rules) changes. The debugger UI is not touched: the Light Changes lane draws whatever `time` is published.

---

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its tests in the container; only if they pass,
tick its checkboxes, then commit and push that item by itself (`git push origin
v3.13`; check `git branch --show-current` prints `v3.13` first, never commit to
`main`) before starting the next. Name the commit after the plan item as written
here — e.g. ``40. Round toward the bar edge``. One commit per item, never a
batch commit at the end.

**Use the recommendation; only a genuinely blocking decision stops an item.**
An open question mid-implementation is resolved by adopting the best
recommendation and continuing. Only a decision where proceeding under any
assumption would make the work wrong or wasted becomes a new `D` item written
into this plan; the session then **continues with the next item**, skipping only
items that depend on the blocked one.

**Checks run in the container**: `docker compose run --rm test` (analyzer),
the MCP suites (`docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test` /
`full-regression`), single-stage re-runs
`docker compose run --rm app ./analyze --song "/data/songs/<song>.mp3" --stage light-changes`
then `--stage publish-light-changes` (both, in that order, on every song touched), and the visual suite per
[`reference/ui-regression.md`](reference/ui-regression.md) (no baseline change expected: the fixtures' point times sit on bar starts and no fixture changes).

**Validation set** (refinement doc table). Tuning songs *Medicine-MilkInc* and *Armin - Revolution* carry the 8 targets of v3.12 item 37 (bar start from `bar_features.json`, offset in beats). Held-out songs: *Fascination*, *Cinderella*, *Titanium*, *Queen of Kings* (kick-rich); *Sash - Raindrops*, *Charli-VonDutch*, *ayuni* (kick-poor). Nothing is tuned on a held-out song; a number that only looks good after a change made while looking at one is reported as such.

**Contract changes are written as they land**, as current state, into
`docs/reference/downstream-contract.md`, `docs/mcp-definition.md` and
`docs/reference/artifacts.md`.

**A failure found after an item is committed:** → `docs/issues.md`; one
needing a design decision → a `BUG` in the refinement doc, "Addressed by item N".

---

## Status

| | |
| --- | --- |
| Done | 0 of 5 |
| Visual QA items | none (UI untouched; suite run in 42 as a regression check) |
| MCP full-regression | 42 (smoke-test on 41, which changes a published row) |
| Contract changes | 41 (`light_change` `start_time` / `light_changes.json` `time` no longer exactly on a beat; new `snap`) |
| Pre-existing failures | *(filled by item 39)* |
| Decisions | *(none yet)* |

---

## 39. Pre-flight

- [ ] Branch `v3.13` from `main`; commit this plan and the refinement doc as ``39. v3.13 plan``.
- [ ] Run every suite above on HEAD; list each failing test by name in Status → "Pre-existing failures".
- [ ] Baseline, recorded in this item: for all 27 songs, `light_changes.json` point count (expect 494), roles, histogram of `bar_edge_offset_beats` (−1/0/+1), and the sha256 of every `artifacts/light_changes/light_changes.json` and top-level `song_event_timeline.json` / `bar_features.json`. The 8 targets' offsets as in v3.12 item 37.
- [ ] For each of the 8 targets, the half-beat `shift` `refine_offset` returned (add a debug print or read it from a scratch run; nothing committed). A target with shift −2 is a whole beat early physically and item 40 will **not** move it: say so here before item 40 runs.

---

## 40. Round toward the bar edge

Refinement item 1.

- [ ] `light_changes.py` `locate`: shift in rows → whole-beat offset by rounding toward zero (±1 row → 0, ±2 rows → ±1). `bar_edge_offset_beats` follows. No other line of the detector changes.
- [ ] Tests: `locate` table for shifts −2..+2; a synthetic half-beat-early step lands on the bar edge, a full-beat-early step lands one beat early.
- [ ] Re-run `light-changes` then `publish-light-changes` on all 27 songs. Record here: the 8 targets' offsets before/after (all within ½ beat; Medicine 9/16, Armin 55/59/60 at 0; Medicine 10–14 empty), point count and roles unchanged, the offset histogram before/after (−1 shrinks, +1 unchanged), number of points moved per song.
- [ ] The Medicine extra break at 29.41 s (bar 18 beat 1) is reported, not fixed.

**Checks**
- [ ] `docker compose run --rm test`; MCP `smoke-test`; visual suite green with no baseline change.

---

## 41. Kick snap

Refinement item 2.

- [ ] `light_changes.py`: after `locate`, read `artifacts/kick_attacks/kick_attacks.json` (already an input of `bar_features`); candidate = event with `echo_of` null, `on_grid` true, `grid` `"trusted"`, `confidence` ≥ `SNAP_MIN_CONF` 0.5, `|event.time − beat.time|` ≤ `SNAP_MAX_FRAC` 0.25 × `beat_len`; nearest wins. Point `time` = event time; `bar`/`beat`/`bar_edge_offset_beats` stay the grid beat's; new `snap: { source: "kick", offset_ms }` or `null`. Sweep points are never snapped (they sit on a bar edge by construction).
- [ ] Constants are fixed here, before measuring; not tuned on any song.
- [ ] `publish-light-changes`: `light_change` `start_time` = snapped `time`; `light_change_role` still on the grid beat's bar.
- [ ] Tests: snap taken, snap refused (echo, off-grid, untrusted, low confidence, beyond ¼ beat), nearest of two, sweep point untouched, missing `kick_attacks.json` → `AnalysisError` naming it.
- [ ] Re-run both stages on all 27 songs. Record here per song: points, snapped share, mean and max `|offset_ms|`; corpus: no point moved more than ¼ beat from its item-40 time; point count and roles unchanged.

**Contract**
- [ ] `artifacts.md` (`light_changes.json` row: `time` "on a beat or within ¼ beat of one (kick-snapped)", `snap`), `downstream-contract.md` (`light_change` `start_time` same wording), `mcp-definition.md` (if `get_detail` projects `snap`: recommendation **no** — `{time, role}` and the overview byte budget 6900 stay; `snap` is artifact-only).

**Checks**
- [ ] `docker compose run --rm test`; MCP `smoke-test` (fixtures have no `snap`; the projection must not require it).

---

## 42. Held-out validation and corpus run

- [ ] Re-run the pipeline on all 27 songs (`--all-songs`); re-run *Medicine* a second time and hash all top-level `*.json` plus `artifacts/light_changes/`: byte-identical.
- [ ] Table, tuning songs: the 8 targets, time and bar landed, offset in beats, role, item-40 vs item-41 time, `snap` taken or not. Pass: all 8 within ½ beat, roles as before, Medicine 10–14 empty.
- [ ] Table, held-out kick-rich (*Fascination*, *Cinderella*, *Titanium*, *Queen of Kings*): points, snapped share, mean/max `|offset_ms|`. Expect snapped share ≥ 0.5 on step points; a song below that is reported, not tuned.
- [ ] Table, held-out kick-poor (*Sash*, *Charli-VonDutch*, *ayuni*): snapped share (expect low), every snapped point listed with time and offset for operator review.
- [ ] Corpus: offset histogram v3.12 → 40 → 41; `drop` points within ±1 beat of a `human_hints.json` boundary on the 15 hinted songs, before/after (informational; must not decrease, a decrease is a `D` item, not a revert).
- [ ] Operator lane review list: every moved point on the held-out songs (debugger Light Changes lane, the marker now sits off the ruler tick where snapped). Written to `docs/issues.md` "Operator lane review" as a dated list.

**Checks**
- [ ] MCP `full-regression`; `docker compose run --rm test`; visual suite green with no baseline change.

---

## 43. Close-out

- [ ] `CLAUDE.md` state table (Light changes row: offset rule, snap, numbers from 42), `analysis-definition.md`, `downstream-contract.md`, `artifacts.md`, `experiments.md` if any number it quotes changed.
- [ ] `docs/issues.md`: the "0.95–1.00 beat early" entry closed with the item-42 numbers; the lane-review list added.
- [ ] Refinement doc: shipped items dropped. Status → "Done", then mark this plan implemented.
