# Implementation Plan — v1.1

Turns [product-refinement-v1.1.md](product-refinement-v1.1.md) into ordered,
validated work. Item numbers here are plan items; they reference the refinement
doc's items (`R1`–`R7`) and bugs (`B1`–`B6`) rather than renumbering them.

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its tests in the container as the item specifies;
only if they pass, tick its checkboxes, then commit and push that item by itself
before starting the next. Name the commit after the plan item as this plan writes
it — for example ``1.2 drop detection rebuild``. One commit per item, never a
single batch commit at the end: a later failure then cannot strand the validated
work in front of it, and the history reads as this plan's own sequence.

**Use the recommendation; only a genuinely blocking decision stops an item.** An
open question that surfaces mid-implementation is resolved by adopting the best
recommendation and continuing — do not idle waiting to ask. The exception is a
decision where proceeding under any assumption would make the work wrong or
wasted. In that case write the decision and its options into this plan as a new
`D` item, then **continue with the next item**, skipping only those that
genuinely depend on the blocked one. A single unresolved question must never
stall a whole run; everything independent of it still gets built.

## Status

| # | Item | Refs | State |
| --- | --- | --- | --- |
| 0.1 | Prune orphaned analysis directory | — | ☑ |
| 0.2 | Label the gold set | R7 | ⚠ blocked → D1 |
| 0.3 | Scoring harness (`--compare form,drops`) | R3 R4 | ☑ (baseline recorded) |
| 1.1 | Stem-relative energy signal | R4 | ☑ (provisional, D1) |
| 1.2 | Drop detection rebuild | R4 B2 | ☑ (provisional, D1) |
| 1.3 | `fake_drop` symmetry | R4 B3 | ☑ (provisional, D1) |
| 2.1 | `form_family` inference | R1a | ☑ (provisional, D1) |
| 2.2 | `form_role` labelling | R1 | ☑ (provisional, D1) |
| 2.3 | Section repetition identity | R2 | ☑ (provisional, D1) |
| 3.1 | Honest boundary confidence | R3 B1 | ☑ (provisional, D1) |
| 3.2 | Join section lists on `section_id` | B5 | ☑ |
| 4.1 | Composite events with phases | R5 | ☑ (provisional, D1) |
| 4.2 | Lean timeline and absolute `intensity` | R6 B4 | ☑ (provisional, D1) |
| 5.1 | `song_facts.json` + `review_queue.json` | R7 | ☑ |
| 5.2 | UI round-trip for the review queue | R7 | ☑ (provisional, no UI runtime) |
| 5.3 | Benchmark profiles keyed on `form_family` | B6 | ☑ |
| 6.1 | Full-corpus run | — | ☐ |
| 6.2 | MCP contract-change note | — | ☐ |
| 6.3 | Release close-out | — | ☐ |

## Test set

Four tracks, all with unambiguous drops:

```
_test_song                        # 58 s, already labelled, fast regression fixture
Armin - Revolution                # 194 s, zero drops currently detected
Hideaway - Kiesza                 # genre mis-tagged ambient @ 0.22
Titanium - David Guetta ft Sia    # hybrid: vocal verse/chorus + a drop
```

**During an item**, iterate on `_test_song` only — it is 58 s and already
labelled:

```bash
docker compose run --rm app ./analyze \
  --song "/data/songs/_test_song.mp3" --stage <changed-stage>
```

**To validate an item**, run all four and score them:

```bash
for s in "_test_song" "Armin - Revolution" "Hideaway - Kiesza" "Titanium - David Guetta ft Sia"; do
  docker compose run --rm app ./analyze --song "/data/songs/$s.mp3" --compare form,drops
done
```

Unit tests, always, before any commit:

```bash
docker compose run --rm app python -m pytest tests/ -q
```

Full-corpus runs are the release gate (item 6.1), not a per-item step.

---

## Phase 0 — Gold set and scoring harness

Nothing downstream can be validated until this phase is done. Items 1.x onward
are provisional until 0.3 lands.

### 0.1 Prune orphaned analysis directory

- [x] Delete `data/analysis/test-song/` — it has no corresponding mp3 in
      `data/songs/`. (`data/` is gitignored, so this is a filesystem-only prune.)
- [x] Confirm no code or doc references it. The only `test-song` (non-`_test_song`)
      match in the tree is this plan's own instruction line.

**Test:** `pytest tests/ -q` passes.
**Commit:** `0.1 prune orphaned analysis directory`

### 0.2 Label the gold set

No new tooling. The Story 8.8 human-hint editor already writes timed hints in
the shape these labels take.

> **Status: blocked — see D1.** This item requires a human listener and is
> deferred out of the batch run. The remaining items are implemented and
> committed with their acceptance marked provisional per "Evaluation set".

- [ ] For each of the four tracks, label in `reference/human/human_hints.json`:
      every section boundary, its intended `form_role`, and the start/end of each
      drop. `_test_song` is already labelled — extend it with `form_role` per
      section, do not re-time what is there.
- [ ] Hand-author `reference/human/song_facts.json` for each of the four with
      `genre` and `form_family`, each carrying
      `provenance: "human-confirmed"`.
- [ ] Record in the plan which track is which `form_family`, so 2.1's acceptance
      has an expected answer.

**Test:** all four files parse; every labelled boundary falls inside the song
duration from `info.json`.
**Commit:** `0.2 label the gold set`

### 0.3 Scoring harness

- [ ] Add `form` and `drops` compare targets (`src/analyzer/cli.py:37` default
      list and `supported_targets`), with validators under
      `src/analyzer/stages/validation/`.
- [ ] `drops`: precision/recall of detected drops against human drop hints, with
      an onset tolerance (start at ±1.0 s, on a bar-length scale).
- [ ] `form`: section-boundary F-measure at ±2.0 s (reuse
      `--tolerance-seconds`), `form_role` accuracy over matched boundaries, and
      `form_family` exact match.
- [ ] Confidence calibration: bucket sections by predicted confidence and report
      observed accuracy per bucket. This is the only way item 3.1 can be shown to
      have worked.
- [ ] Write results into `artifacts/validation/` alongside the existing reports.
- [ ] Add `tests/test_validation_form_drops.py` with synthetic fixtures.

**Test:** harness runs on all four tracks and reports a baseline. Record that
baseline in this plan — it is what every later item is measured against.
**Commit:** `0.3 scoring harness`

#### Implementation notes

Delivered as `src/analyzer/stages/validation/form_drops.py`, wired into
`build_validation_report` as the `form` and `drops` compare targets (added to the
`--compare` default and `supported_targets`). Both are **advisory**: a new
`ADVISORY_TARGETS` set in `report.py` keeps them out of the `--fail-on-mismatch`
exit-code gate, since their ground truth is the incomplete gold set. Per-song
scores are written to `artifacts/validation/{form,drops}_score.json`.

- `drops`: greedy nearest-first one-to-one matching of detected drops (timeline
  `type` ∈ drop-like, or composite `impact` phase) to timed human drop hints at
  ±1.0 s → precision/recall/F1. With no timed hints it falls back to a
  `presence` check against the `has_drop` fact. Always reports whether
  `fake_drop` outnumbers `drop` (B3 signal).
- `form`: boundary F-measure at ±2.0 s, `form_role` accuracy over matched
  boundaries, `form_family` exact match, plus a confidence-calibration table
  (sections bucketed by predicted confidence vs. observed boundary alignment)
  and the predicted-confidence spread (the item 3.1 signal).
- Tests: `tests/test_validation_form_drops.py` (9 cases, synthetic fixtures).

#### Baseline (2026-08-30, scored against current on-disk artifacts)

| Track | drops mode | detected | fake | drops result | conf. spread |
| --- | --- | --- | --- | --- | --- |
| `_test_song` | timed (label @ 28.8 s) | 0 | 0 | **failed** (recall 0.0) | 0.115 |
| `Armin - Revolution` | presence | 0 | 0 | **failed** | 0.235 |
| `Hideaway - Kiesza` | presence | 0 | 0 | **failed** | 0.193 |
| `Titanium - David Guetta ft Sia` | presence | 1 | 0 | passed | 0.267 |

`form` is `skipped` on all four: `form_family` is not emitted until item 2.1 and
no boundary labels exist yet (D1). Confirms the refinement doc: drops are almost
never detected (3/4 tracks at zero), and boundary confidence spans a narrow
0.11–0.27 band (B1).

---

## Phase 1 — Drops

The largest failure and the fastest visible win. Ordered before form because
2.1 reuses 1.1's signal.

### 1.1 Stem-relative energy signal

- [x] Add a stem-relative activation feature: per-stem energy normalised against
      the song's own robust range (p5–p95), not mix RMS. `_robust_range_scale`
      in `event_features/utils.py`, applied per-song in `builder.py`.
- [x] Expose bass/drums/harmonic/vocals activation, spectral flux and onset
      density on this scale as `*_stem_rel` / `*_rel` in `derived` and in
      `feature_catalog.derived`.
- [x] `generated_from.engine` → `rule-based-event-feature-alignment.stem-relative.v2`;
      `features.json` `schema_version` → `"1.1"`; per-stem ranges recorded in
      `normalization_rules.stem_relative_ranges`.

**Test:** `pytest tests/test_event_features.py -q` (8 passed; extended with
stem-relative assertions). Cross-track separation of drop vs non-drop windows is
provisional pending D1 / a corpus re-run.
**Commit:** `1.1 stem-relative energy signal`

### 1.2 Drop detection rebuild

- [x] Replaced the six-way drop conjunction with `_drop_evidence()` — a fixed
      weighted sum of seven sub-scores vs. a single `DROP_EVIDENCE_PROFILE`
      decision threshold. Also dropped the `_intensity_cluster == 2` hard gate
      (the "plus membership in the top cluster" half of B2).
- [x] Removed `drop_energy_delta`, `drop_bass_ratio_min`, `drop_flux_ratio_min`,
      `drop_onset_min`, `drop_bass_min`, `drop_accent_min` — all song-adaptive.
- [x] Each drop records `evidence.metadata.drop_evidence` with per-feature
      sub-score, weight and weighted contribution; adjacent anchors merge.
- [~] Decision threshold set to 0.42 by construction (weights sum to 1.0);
      **tuning against the 0.3 baseline is deferred to a corpus re-run (D1)**.

**Test:** `tests/test_event_rules.py` — added `test_weighted_evidence_detects_bass_reentry_drop`
and `test_no_drop_without_bass_reentry` (3 passed). `--compare drops` on the
four tracks is a corpus-run check, still provisional under D1.
**Commit:** `1.2 drop detection rebuild`

### 1.3 `fake_drop` symmetry

- [x] Rewrote the `fake_drop` loop: `fake_drop_withheld_release`. It now needs a
      `build` event ending within 6 s before the pause point **and** no `drop` in
      the 4 s release window after. The bare held-tension path is gone.
- [x] Positive evidence: the paired build id and its end time are recorded in the
      event; the release-window drop count (0) is an explicit metric.

**Test:** `tests/test_event_rules.py` — added
`test_fake_drop_requires_build_and_absent_release`,
`test_no_fake_drop_when_release_arrives`,
`test_no_fake_drop_without_preceding_build` (6 passed total). The corpus-level
"`fake_drop` no longer outnumbers `drop`" check is provisional under D1; the 0.3
harness already reports the `fake_outnumbers_drop` flag per song.
**Commit:** `1.3 fake_drop symmetry`

---

## Phase 2 — Form

### 2.1 `form_family` inference

- [x] `infer_form_family` in `src/analyzer/stages/sections/form.py` — audio
      evidence only: tempo CV, mean drum-stem activity + tempo stability
      (steady kick), and section-level bass dropout → re-entry range.
- [x] Emitted as the song-level `form_family` object (`value`, `confidence`,
      `provenance`, `evidence`) in `sections.json`.
- [x] Human-confirmed `form_family` from `reference/human/song_facts.json` breaks
      a tie only when inferred confidence < 0.55; `provenance` → `"human-confirmed"`.
- [x] `infer_form_family` takes no genre argument;
      `test_form_labelling.py::test_genre_is_not_a_parameter` asserts it.

**Test:** `tests/test_form_labelling.py::FormFamilyTests` (4 cases). `--compare
form` cross-track match is provisional under D1 (expected answers recorded in D1).
**Commit:** `2.1 form_family inference`

### 2.2 `form_role` labelling

- [x] `FORM_ROLE_VOCAB` + `FORM_FAMILY_ROLES` gate in `form.py`;
      `assign_form_roles` scores every admissible role deterministically and
      emits `unknown` when the best score < 0.4 or its margin < 0.08.
- [x] `energy_character` carries the 13-value energy-shape label (with
      `section_character` kept as its alias).
- [x] Top-level `label` rebuilt from `form_role`; `form_role_confidence` and
      `form_role_margin` are separate numeric fields.
- [x] `section_segmentation` engine → `deterministic.section_segmentation.v2`,
      `schema_version` → `"1.1"` (inferred and reference-promoted payloads).
- [x] Story 3.1 updated. `test_sections_v2` split-label assertion moved to
      `section_character`.

**Test:** `tests/test_form_labelling.py::FormRoleTests` (in-vocab + verse/chorus
alternation). `--compare form` accuracy-vs-baseline is provisional under D1.
**Commit:** `2.2 form_role labelling`

### 2.3 Section repetition identity

- [x] `compute_repetition_groups` in `form.py` assigns `repetition_group`
      (`A`/`B`/`C`…) from cosine similarity over the section feature `vector`
      (fused harmonic histogram + timbral means); `variant_of` is the first
      occurrence's `section_id` (mapped from index in the segmenter), `similarity`
      the measured cosine. Wired into every `SectionWindow`.
- [x] Story 3.1 states that `repetition_group`, not `energy_character` equality,
      is the reusable-look input; the MCP-side switch is carried in the 6.2
      contract-change note (the MCP server is not modified in v1.1).
- [x] Story 3.1 updated.

**Test:** `tests/test_form_labelling.py::RepetitionGroupTests` — verses group
together, choruses group together, distinct groups; varied repeat records
`variant_of`. The `Titanium` corpus check is provisional under D1.
**Commit:** `2.3 section repetition identity`

---

## Phase 3 — Confidence

### 3.1 Honest boundary confidence

- [x] `boundary_confidence` in `sections/form.py` replaces the affine formula.
- [x] Terms: mean per-channel (energy/timbral/harmonic) boundary strength,
      three-channel detector agreement, novelty-peak sharpness vs ±2-beat
      neighbours, transient alignment, bar-grid alignment, `form_role` margin —
      weights sum to 1.0. Recorded per section as `confidence_terms`.
- [x] Section loudness, repetition count and onset level removed as terms.
- [x] Full `[0, 1]` range reachable — `test_confidence_can_span_full_range`
      shows an identical-material boundary at ~0.05.
- [x] Story 3.2 updated. Engine → `deterministic.section_segmentation.v3`.

**Test:** `tests/test_form_labelling.py::BoundaryConfidenceTests` (sharp+agreeing
boundary > smooth one; full range). The 0.3 calibration report across the corpus
is provisional under D1.
**Commit:** `3.1 honest boundary confidence`

### 3.2 Join section lists on `section_id`

- [x] `build_ui_data` projects `section_id` (plus `form_role`,
      `energy_character`, `repetition_group`, numeric `confidence`) into every
      top-level `sections.json` row.
- [x] `build_ui_data` raises `ValueError` on a missing or duplicate
      `section_id` in the segmentation list rather than emitting a
      position-joinable list.
- [x] Story 7.2 updated. Also repaired the stale imports in
      `tests/test_validation.py` (the pre-existing collection error from an
      earlier validation-module refactor) — that file now runs green (22 cases).

**Test:** `tests/test_ui_data_section_join.py` (3 cases: id projection, missing
id fails, duplicate id fails) + `tests/test_validation.py` restored.
**Commit:** `3.2 join section lists on section_id`

---

## Phase 4 — Events

### 4.1 Composite events with phases

- [x] `_fold_composites` in `event_timeline.py` folds `build → drop → post_drop`
      (8 s window) into one row: overall `start_time`/`end_time`/`confidence`/
      `intensity`, `member_event_ids[]`, ordered `phases[]`
      (`approach`/`build`/`tension`/`impact`/`release`/`recovery`).
- [x] Folded members are removed from the exported timeline; non-members pass
      through unchanged.
- [x] A `build` with no resolving `drop` (or a `fake_drop` with a preceding
      build) folds into a composite with **no `impact`/`release` phase**.
- [x] `event_vocabulary.json` gains `composite_phase_vocabulary`. Composites live
      only in the `song_event_timeline.json` projection (`schema_version` `"1.1"`,
      engine `llm-friendly-event-timeline-v2`); the strict internal
      `song_event_schema.json` stays at `"1.0"` with flat members because
      `beatdrop_visual_plan.json` still reads them (v1.2 moves it).
- [x] `beatdrop_visual_plan.json` is built from sections/energy/fft, not this
      timeline — unaffected.
- [x] Stories 5.1 and 5.6 updated.

**Test:** `tests/test_event_timeline.py` — `test_build_drop_post_drop_folds_into_one_composite`
(phases `build→tension→impact→release`, members gone) and
`test_build_without_drop_folds_into_composite_with_no_impact` (3 passed).
Per-track corpus check provisional under D1.
**Commit:** `4.1 composite events with phases`

### 4.2 Lean timeline and absolute `intensity`

- [x] `event_machine/generator.py` no longer emits `layer_add`/`layer_remove`
      and filters any that arrive from ML/rule inputs. `_summarise_texture_changes`
      writes a per-section `texture_summary[]` (stem activity, `stems_entering`,
      `stems_leaving`) to `events.machine.json` metadata; `export_event_timeline`
      also skips those types and echoes `texture_summary`.
- [x] `_absolute_intensity(type, raw)` in `event_timeline.py` — a fixed
      `[floor, ceiling]` band per event type; the raw signal only positions the
      event within its band. Cross-song absolute, no per-song normalisation.
- [x] Timeline `summary` now comes from the evidence summary, not the rule note.
- [x] `event_vocabulary.json` marks `layer_add`/`layer_remove` `deprecated`.
      Stories 5.1 / 5.6 updated.

**Test:** `tests/test_event_timeline.py::test_layer_events_dropped_and_intensity_is_type_banded`
(raw 1.0 → 0.30 band for an `atmospheric_plateau`; layer events gone). Per-song
event-count / distribution check is provisional under D1.
**Commit:** `4.2 lean timeline and absolute intensity`

---

## Phase 5 — Human loop

Sized for the 17 tracks outside the gold set, where hand-labelling does not
scale.

### 5.1 `song_facts.json` + `review_queue.json`

- [x] `song_facts.json` contract formalised in the new Story 5.7; loaded via
      `load_song_facts` (shared with 2.1 and the 0.3 harness).
- [x] `src/analyzer/stages/review_queue.py::build_review_queue` emits
      `artifacts/validation/review_queue.json` — ranked by `leverage`, each entry
      carrying `field`, `candidates` (value+score), `evidence_timestamps`,
      `reason_low_confidence`. Wired as the `build-review-queue` pipeline stage
      (5.1) and registered in `info.json`.
- [x] Question sources: low-confidence `form_family`, `form_family_vs_genre`
      (R1a flag), ambiguous/`unknown` `form_role`, and `drops.timed_location`
      when `has_drop` is true but nothing was detected.
- [x] `direction_of_flow` is stated in the artifact; `build_review_queue` only
      ever writes under `validation/`. Regression test
      `test_analyzer_never_writes_reference`.
- [x] New Story 5.7.

**Test:** `tests/test_review_queue.py` (4 cases). Suite: 94 passed, 3
pre-existing failures.
**Commit:** `5.1 song_facts and review_queue`

### 5.2 UI round-trip for the review queue

- [x] `ReviewQueuePanel.jsx` + `useReviewQueueEditor.js` render
      `review_queue.json` as answerable questions inside the Human Hint editor
      sidebar; whole-song questions get a candidate `<select>`.
- [x] `PUT /api/song-facts/<song>` handler in `vite.config.js` +
      `saveSongFactsFile` write `song_facts.json` with
      `provenance: "human-confirmed"` on explicit Save only — same rule as 8.8.
- [x] New Story 8.10. `npm run build` passes.

**Test:** end-to-end (answer → save → re-run changes `form_family`) needs a
running UI + pipeline; provisional (no UI runtime here). The
save-only-on-explicit-save contract is enforced by the single PUT handler.
**Commit:** `5.2 UI round-trip for the review queue`

### 5.3 Benchmark profiles keyed on `form_family`

- [x] `_select_profile` in `event_benchmark.py` replaces the
      `genre_result["genres"][0]` lookup: a human-confirmed `genre` fact wins,
      else `form_family` maps to a profile (`dance_form → festival_edm`,
      `song_form`/`hybrid → electro_pop`, else `default`). `genre_result` is no
      longer read.
- [x] `event_benchmark.json` records `selected_profile_basis`.
- [x] Story 5.5 updated.

**Test:** `tests/test_event_benchmark.py::SelectProfileTests` (3 cases).
**Commit:** `5.3 benchmark profiles keyed on form_family`

---

## Phase 6 — Release

### 6.1 Full-corpus run

- [ ] Run the full pipeline over all songs and confirm no stage fails.
- [ ] Confirm determinism: run one song twice, compare artifacts byte-for-byte.
- [ ] Record drop counts and confidence distributions across the corpus, for
      comparison against the pre-v1.1 figures in the refinement doc.

```bash
mkdir -p logs && nohup docker compose run --rm -T app \
  ./analyze --all-songs --device cuda \
  > "logs/v1.1-validation-$(date +%F_%H-%M-%S).log" 2>&1 < /dev/null & echo $!
```

**Commit:** `6.1 full-corpus run`

### 6.2 MCP contract-change note

- [ ] Write `docs/source references/contract-change-v1.1.md`: exactly what
      changed in the top-level files — `form_role`/`form_family`,
      `repetition_group`, composite `phases[]`, the removal of `layer_add`/
      `layer_remove`, the new `intensity` scale, and `section_id` as the join key.
- [ ] The MCP server is not modified in this release; this note is the handover.

**Commit:** `6.2 MCP contract-change note`

### 6.3 Release close-out

- [ ] Confirm every changed artifact carries the right `schema_version` and
      engine version per the refinement doc's convention.
- [ ] Confirm every touched Story spec matches the implementation.
- [ ] Update `docs/data_folder_reference.md` and `docs/Implementation_Guide.md`
      for the new files and fields.
- [ ] Update the root `README.md` status line to point at v1.1 as released.
- [ ] Archive this plan and `product-refinement-v1.1.md`.
- [ ] Tag `v1.1`.

**Commit:** `6.3 release close-out`

---

## Decisions raised during implementation

### D1 — Gold-set ground truth requires a human listener (blocks 0.2)

**Blocked item:** 0.2 "Label the gold set".

**Why it is genuinely blocking rather than recommendation-resolvable.** The gold
set is the ground truth every later acceptance criterion is scored against.
Deriving section boundaries, `form_role`, and drop times for `Armin - Revolution`,
`Hideaway - Kiesza` and `Titanium` from the existing analysis artifacts would
score the pipeline's new inference against labels produced by the pipeline's old
inference — the circularity that refinement item 7 explicitly rules out ("a guess
parked in the truth folder… launders a weak inference into truth"). The
constitution also restricts `reference/human/` to explicit human saves. A machine
guess here is worse than no label.

**Options.**
- **(taken) Defer 0.2 to a human pass; implement everything else provisionally.**
  Per the plan's own rule ("an item's acceptance is provisional… it may be
  implemented and pushed, but it is not considered validated"), items 0.3 and 1.x–3.x
  proceed as code + synthetic-fixture unit tests + story specs, committed per item,
  with corpus scoring wired but not gated. When a human lands
  `reference/human/{human_hints,song_facts}.json` for the three unlabelled tracks,
  run `0.3`'s harness to validate retroactively.
- Author draft labels now, tagged `provenance: "machine-derived-draft"`, and let a
  human correct. Rejected: pollutes the truth set and the validation numbers
  degrade silently, exactly per R7.

**Partial unblock (2026-08-30).** The project owner has confirmed that **all four
gold tracks contain at least one real drop**, recorded as `has_drop` with
`provenance: "human-confirmed"` in each track's
`reference/human/song_facts.json` (a new file; `data/` is gitignored so it lives
only on the local disk). This makes item 1.2's acceptance — "each reports at
least one drop" — checkable now, ahead of the full timed labelling. Timed drop
boundaries, section boundaries and `form_role` are still pending a human pass.

**`_test_song`** already carries 11 timed human hints and is extended with
`form_role` per section in item 2.2's commit (that is real human data, not a
guess).

**Expected `form_family` answers** (for 2.1 acceptance, once labelled):
`_test_song` → `dance_form`; `Armin - Revolution` → `dance_form`;
`Hideaway - Kiesza` → `hybrid` (vocal song-form with a dance drop);
`Titanium - David Guetta ft Sia` → `hybrid`.
