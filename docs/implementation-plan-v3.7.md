# Implementation plan — v3.7

**Status: not started.** Turns
[`product-refinement-v3.7.md`](product-refinement-v3.7.md) (the refinement doc
in the rest of this plan) into an ordered worklist for a Sonnet implementer in
batch mode. The refinement doc holds the evidence and schemas. This plan says
what each item builds, how it is checked, and what must not be undone.

**v3.7 answers:** two things. First, whether a claim-bearing lane's emitted
blocks are actually real — a precision instrument the debugger has never had.
Second, whether the MCP answers in the terms a reader reasons in (sections,
bars, beats) instead of forcing every consumer to recompute derived views from
raw series by hand.

## Item order

| # | Item | Refinement item | Kind | Depends on |
| --- | --- | --- | --- | --- |
| 0 | Pre-flight | — | checks only, no commit | — |
| 1 | Block reviews — schema + scaffold | 1 | `ui/` scaffold + fixture | — |
| 2 | Block reviews — verdict control + save | 1 | `ui/` | 1 |
| 3 | Block reviews — scorer | 1 | `experiments/truth_common/` | 1 |
| 4 | `impact_alignment` | 2 | `src/` + contract | — |
| 5 | Musical addressing — `position` + `bars` scope | 3 | `mcp/` + `src/` + contract | 4 |
| 6 | Musical addressing — `section_id` reattribution | 3 | `src/` | 5 |
| 7 | Intensity summaries | 4 | `mcp/` + `src/` + contract | 5 |
| 8 | Drum density | 5 | `mcp/` + contract | 5 |
| 9 | Dropouts | 6 | `mcp/` + contract | 5, 8 |
| 10 | Correction proposals — MCP tools | 7 | `mcp/` + contract | — |
| 11 | Correction proposals — UI approve/reject | 7 | `ui/` | 10 |
| 12 | Close-out | — | docs | 1–11 |

Items 1–3 (block reviews) and 4–9 (musical addressing) and 10–11 (proposals)
are otherwise independent chains; only the ordering within a chain is a real
dependency.

---

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a
time. When an item is complete, run its tests the way the project requires
(in the container, where the project is Docker-based); only if they pass,
tick its checkboxes, then commit and push that item by itself before starting
the next. Name the commit after the plan item as the plan writes it — for
example ``4. `impact_alignment` ``. One commit per item, never a single batch
commit at the end: a later failure then cannot strand the validated work in
front of it, and the history reads as the plan's own sequence.

**Use the recommendation; only a genuinely blocking decision stops an item.**
An open question that surfaces mid-implementation is resolved by adopting the
best recommendation and continuing — the session does not idle waiting to
ask. The exception is a decision where proceeding under any assumption would
make the work wrong or wasted. In that case the session writes the decision
and its options into the plan as a new `D` item, then **continues with the
next item**, skipping only those that genuinely depend on the blocked one. A
single unresolved question must never stall a whole run; everything
independent of it still gets built.

**Checks run in the container**: `docker compose run --rm test` (analyzer),
`docker compose run --rm ui npm run test` and `docker compose run --rm ui npm
run build` (`ui/`), the visual suite
([`docs/reference/ui-regression.md`](reference/ui-regression.md) §6), the MCP
suites (`docker compose run --rm --no-deps -T --entrypoint python mcp
mcp/tests/run.py smoke-test` / `full-regression`).

**A failure found after an item is committed:** an analysis defect goes to
`docs/issues.md`; a `ui/` defect to `docs/web-ui/ui-issues.md`; a defect
needing a design decision becomes a `BUG` in the refinement doc, annotated
"Addressed by item N". Never fix across item boundaries in one commit.

---

## Status

| | |
| --- | --- |
| Done | 0 of 12 |
| Visual QA items | 1, 2, 11 |
| MCP full-regression | items 5, 7, 8, 9, 10 (smoke-test on every item) |
| Contract changes (`docs/reference/downstream-contract.md`, written as current state in the item that makes the change) | 4, 5, 6, 7, 8, 9, 10 |
| New writable `reference/human/` files | `block_reviews.json` (item 1), `reference/proposals/pending.json` (item 10 — not `reference/human/`, never operator-authored directly) |
| Pre-existing failures | `tests/test_run_queue.py::QueueFileTests::test_seeded_queue_parses_with_three_enabled_app_rows` (stale test — asserts `queue.toml` has `[[experiment]]` rows; the file is now empty after v3.6's promotions). Pre-dates this plan, not owned by any v3.7 item. |
| Decisions | none yet |

---

## 0. Pre-flight

- [x] Commit `docs/product-refinement-v3.7.md` and `docs/implementation-plan-v3.7.md` alone as ``0. v3.7 refinement and plan``, so no item commit sweeps them in.
- [x] Run every suite named in "How this plan is worked" on HEAD. List each failing test by name in Status → "Pre-existing failures". Later items are not blamed for these.

---

## 1. Block reviews — schema + scaffold

Refinement item 1, the `block_reviews.json` schema and lane set.

- [x] `data/analysis/{song}/reference/human/block_reviews.json`: writer function in `ui/vite.config.ts` beside `blockEnergyFilePath`/`lyricValidationsFilePath`, following the merge-on-write, per-click pattern `lyric_validations.json` uses (item is the join key `(lane_id, start)`, not an index). New `PUT /api/block-reviews/{song}` handler. `ui/src/data/paths.ts` gains `blockReviews`.
- [x] Loader + normalizer in `ui/src/data/` reads the file, rounds `start` to 3 decimals to match, and marks a review **stale** (never dropped, never re-attached) when no block of that `lane_id` in the current run has a `start` within ±0.25 s.
- [x] Lane set this applies to: every lane in `ui/src/timeline/laneState.ts` carrying an `experiment` field (`segmentSeeds`, `vocalPhrases`, `allin1Posterior`, `rhythmDrumIoi`, `rhythmStemAutocorr`, `rhythmVocalOnsets`, `energyLevel`, `tensionShape`, `character`, `vocalTranscription`), plus `gestures`. Not `moisesSections`, `moisesLyrics`, or a human-authored lane.
- [x] Regression fixtures: add a `block_reviews.json` fixture (`RegFull`) with at least one `correct`, one `wrong`, one `misplaced`, and one stale row (a `start` no current block matches).

**Checks**
- [x] `docker compose run --rm ui npm run test` and `npm run build` green.
- [x] A `PUT` with a `start` that matches no current block within ±0.25 s is accepted and stored, but the loader reports it stale, never dropped or reattached (`blockReviewMatch.test.ts`).

---

## 2. Block reviews — verdict control + save

Refinement item 1, UI surface.

- [ ] Three-state verdict control (`correct` / `wrong` / `misplaced`) on the block inspector and on each lane-events-panel card, following `SegmentedRating`'s existing per-block pattern (`ui/src/panel/LaneEventsPanel.tsx`, `ui/src/panel/SegmentEditorPanel.tsx`). `reason` (fixed vocabulary: `boundary`/`label`/`value`, required non-null only when verdict is `wrong` or `misplaced`) and free-text `note`.
- [ ] Saved per click through the item-1 PUT handler — no explicit Save button, matching `lyric_validations.json`'s pattern, not `block_energy.json`'s.
- [ ] A reviewed block is tinted in the lane (coverage visible without opening the inspector); a stale review renders with a distinct stale treatment, never silently hidden.

**Checks**
- [ ] `docker compose run --rm ui npm run test` and `npm run build` green.

**Visual QA** (`RegFull`)
- [ ] Runtime assertions per `ui-regression.md` §3 (no console errors, no failed network requests).
- [ ] A block with a saved verdict shows the tint on the lane at its `[data-lane]`/block position.
- [ ] A stale review's block shows the stale treatment, not the normal tint.
- [ ] Baseline re-captured with a one-line justification.

---

## 3. Block reviews — scorer

Refinement item 1, the measurement side.

- [ ] New family in `experiments/truth_common/` reading `block_reviews.json` (the only `reference/human/` tier this module reads) and emitting a per-lane, per-song table: block count, reviewed count, `correct`/`wrong`/`misplaced` split, `wrong` reported separately from `misplaced`. Precision = `correct / reviewed`.
- [ ] A stale review is excluded from the scored count (it does not describe any block the current run emitted).

**Checks**
- [ ] `docker compose run --rm test` green.
- [ ] On the item-1 fixture (or an equivalent scratch fixture), the scorer's precision figure matches a hand count of the fixture rows.

---

## 4. `impact_alignment`

Refinement item 2. Fused in `src/analyzer/stages/section_clues.py`, which
already reads `sections.json` and `song_event_timeline.json` for
`tension_shape` — reuse its `_best_overlap_row`/gesture-scan helpers rather
than a second nearest-impact search.

- [ ] Per section row: nearest gesture impact to `start`; `null` when none falls within ±2 bars (an honest omission, never a nearest-match at any distance).
- [ ] Fields: `gesture_id`, `impact_time`, `offset_s` (signed, `impact_time - start`; positive = late), `offset_beats` (`offset_s` at the song's BPM), `impact_position` (per item 5's `position` shape — until item 5 lands, this sub-field is `null`; item 5 backfills it, no schema change).
- [ ] `field_sources` gains `impact_alignment: "impact_alignment"`.
- [ ] Contract: `docs/reference/downstream-contract.md` `sections.json` section; `docs/reference/source-map.md`.

**Checks**
- [ ] `docker compose run --rm test` green.
- [ ] On *What a Feeling – Courtney Storm*: section-008 emits `offset_s ≈ 3.83` (start 127.27 vs. impact 131.10); section-010 emits `offset_s ≈ 0.50` (start 157.95 vs. impact 158.45).
- [ ] A section with no impact within ±2 bars emits `impact_alignment: null`.
- [ ] `--stage section-clues` re-run on the same song is byte-identical.

---

## 5. Musical addressing — `position` + `bars` scope

Refinement item 3, the addressing mechanism.

- [ ] `position` shape `{"bar", "beat", "section_id", "resolved"}`, derived **on read** in `mcp/serializers.py` from the beat grid — never stored. `resolved: false` where the bar is tempo-arithmetic across a downbeat with `null` `downbeat_confidence`, rather than read from a detected downbeat.
- [ ] Attach `position` to every time field the MCP serializes: section edges, gesture phases and impacts (including `impact_alignment.impact_position` from item 4), transitions, hints, arrangement blocks, vocal phrases, dense-frame rows, drum-event rows.
- [ ] `get_detail` gains `bars: [start, end]` (inclusive) as a fourth scope selector alongside `section_id`/`gesture_id`/(existing time-range selector) in `mcp/server.py` and `DetailScopeError` handling — still exactly one selector per call.
- [ ] Seconds remain the only stored/joined unit; nothing in `src/` changes to store bars.
- [ ] Contract: `docs/reference/downstream-contract.md` (every block gains `position`; the `bars` selector), `docs/mcp-definition.md`.
- [ ] Regenerate `mcp/tests/__snapshots__/` with one justification line each.

**Checks**
- [ ] MCP smoke-test and full-regression green.
- [ ] On *What a Feeling*, `get_detail(bars=[79, 80])` returns the span 155.83–159.70 s.
- [ ] A bar derived across a null-confidence downbeat reports `resolved: false` on at least one fixture row.

---

## 6. Musical addressing — `section_id` reattribution

Refinement item 3, the attribution fix.

- [ ] `src/analyzer/stages/hints.py` and `src/analyzer/stages/gestures.py`: attribute `section_id` by timestamp against the **published** `sections.json`, never allin1's `artifacts/section_segmentation/sections.json`.
- [ ] `field_sources` entries updated to name the published table as the source of `section_id`.

**Checks**
- [ ] `docker compose run --rm test` green.
- [ ] On *What a Feeling*, the `Drums cut` hint reports `section-007` (the published pre-chorus), not `section-003` (allin1's).
- [ ] `--stage generate-section-hints` / `--stage gestures` re-run is byte-identical.

---

## 7. Intensity summaries

Refinement item 4.

- [ ] `vocals_phrase` rows — published into `arrangement_state.json` by `src/analyzer/stages/ui_data.py`'s `_whisperx_vocal_phrase` (the WhisperX VAD promotion, not `arrangement_state.py` itself) — gain `peak`, `mean` (normalized vocals loudness) and the `position` of the peak.
- [ ] `get_detail`'s structural view gains `stem_summary` in `mcp/serializers.py`: per requested stem, `peak`/`mean`/peak `position` over the resolved span, served on **every** call including spans past the 5 s dense cap (the cap withholds frames, not this summary).
- [ ] Contract: `downstream-contract.md` detail-files section.

**Checks**
- [ ] `docker compose run --rm test` and MCP smoke-test/full-regression green.
- [ ] A `section_id`-scoped `get_detail` on *What a Feeling* section-006 returns `stem_summary` with dense frames withheld (span exceeds 5 s).

---

## 8. Drum density

Refinement item 5.

- [ ] `get_detail`'s structural view gains `drum_density` in `mcp/serializers.py`: one row per bar in the requested span, per instrument (`kick`, `snare`, `hat`, `crash`), with `count` and implied `subdivision` (`quarter`/`eighth`/`sixteenth`/`none`/`mixed`) computed from `drum_events.json` onsets against the beat grid. Each row carries `changed_from_previous` (bool).
- [ ] Per-hit confidence stays `null` (omnizart emits none) — do not synthesize one.
- [ ] Contract: `downstream-contract.md` detail-files section.

**Checks**
- [ ] MCP smoke-test/full-regression green.
- [ ] On *What a Feeling*, snare `subdivision` reads `quarter` at bar 61 beat 3 and kick reads `eighth` in bar 79, both with `changed_from_previous: true`.

---

## 9. Dropouts

Refinement item 6. Depends on item 8 for the shared per-bar/onset scanning
helpers in `mcp/serializers.py`.

- [ ] `get_detail`'s structural view gains `dropouts`: per stem, every span of two beats or more with no onsets (drums) or at the stem's noise floor (others), `position` at both edges.
- [ ] Where `arrangement_state` calls a stem absent and onsets/energy disagree, emit the span with `disagreement: true` and both producers named — never resolved automatically.
- [ ] Contract: `downstream-contract.md` detail-files section.

**Checks**
- [ ] MCP smoke-test/full-regression green.
- [ ] *What a Feeling*'s drum cut emits at bar 62 beat 4 – bar 64 beat 1, its start `resolved: false` (bar 62's downbeat has null confidence).
- [ ] Each chatter gap under a synth pulse is emitted.
- [ ] The pre-chorus drums span is emitted with `disagreement: true`.

---

## 10. Correction proposals — MCP tools

Refinement item 7, the queue side. Read-only boundary preserved: these tools
write only `reference/proposals/pending.json`, never `reference/human/`.

- [ ] `propose_hint(song, start, end, title, summary, evidence)` and `propose_section_field(song, section_id, field, value, evidence)` (`field` one of `energy`, `tension`, `rhythm.<stem>`) in `mcp/server.py`. `evidence` required, rejected (error, not silent drop) if empty.
- [ ] Proposals land in `data/analysis/{song}/reference/proposals/pending.json`, append-only until approved/rejected.
- [ ] Contract: `downstream-contract.md` (two new tools, their write-only-to-proposals boundary), `docs/mcp-definition.md`.

**Checks**
- [ ] MCP smoke-test/full-regression green.
- [ ] Calling `propose_hint` with empty `evidence` errors and writes nothing.
- [ ] Two calls append two distinct entries to `pending.json`, neither overwriting the other.

---

## 11. Correction proposals — UI approve/reject

Refinement item 7, the approval side.

- [ ] `ui/src/panel/` lists pending proposals beside the existing operator-write surfaces. Approve writes the change to the correct `reference/human/*.json` through the **existing** PUT handlers (item 10 never gains its own write-to-human path) and re-runs the stage that consumes it (`section-clues` for section fields, `generate-section-hints` for hints). Reject keeps the entry with its reason, so it is not re-queued.
- [ ] `ui/vite.config.ts` gains the pending-list read + approve/reject write endpoints.

**Checks**
- [ ] `docker compose run --rm ui npm run test` and `npm run build` green.
- [ ] A proposed tension change, once approved in the UI, is served by `get_detail` with `tension_source: "human"` and no manual stage run.
- [ ] Nothing proposed and unapproved appears in any published (top-level) file.

**Visual QA** (`RegFull`)
- [ ] Runtime assertions per `ui-regression.md` §3.
- [ ] Pending-proposals panel renders one card per `pending.json` entry on a fixture with ≥2 proposals.
- [ ] Baseline re-captured with a one-line justification.

---

## 12. Close-out

- [ ] `CLAUDE.md` "Current state" table: gestures precision figure (closing `docs/issues.md`'s entry, false-positive bound written in), structure (`impact_alignment`), MCP surface (`position`, `bars` scope, `stem_summary`, `drum_density`, `dropouts`, proposal tools).
- [ ] `docs/issues.md`: delete the `gestures` per-primitive-precision entry (item 3's per-gesture-phase precision figure across the four gold songs discharges it).
- [ ] `docs/product-refinement-v3.7.md` Status → implemented.
- [ ] `docs/reference/downstream-contract.md`, `docs/mcp-definition.md`, `docs/reference/source-map.md`, `docs/reference/artifacts.md` read through once for drift against what actually shipped.

**Checks**
- [ ] Every suite green: analyzer, ui test + build, visual, MCP full-regression.
