# Implementation plan — v3.0

Executes [`product-refinement-v3.0.md`](product-refinement-v3.0.md): the wave-2
module verdicts, deletions and replacements together. Read the refinement doc
first — it carries the measured evidence for every decision here, and this file
does not repeat it.

Roughly 6,000 lines and ~20 MB of per-song artifact leave `src/`; four projected
files change shape. Compatibility is not a constraint (constitution §10);
documenting the change is (item 15, written incrementally).

---

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its tests the way this project requires — in the
container, `docker compose run --rm test`, plus the visual suite for any item
carrying a Visual QA block. Only if they pass, tick its checkboxes, then commit
and push that item by itself before starting the next. Name the commit after the
plan item as this plan writes it — for example ``4. Delete `patterns.py` ``. One
commit per item, never a single batch commit at the end: a later failure then
cannot strand the validated work in front of it, and the history reads as this
plan's own sequence.

**Use the recommendation; only a genuinely blocking decision stops an item.** An
open question that surfaces mid-implementation is resolved by adopting the best
recommendation and continuing — do not idle waiting to ask. The exception is a
decision where proceeding under any assumption would make the work wrong or
wasted. In that case write the decision and its options into this plan as a new
`D` item, then **continue with the next item**, skipping only those that
genuinely depend on the blocked one. A single unresolved question must never
stall the whole run; everything independent of it still gets built.

---

## Status

| | |
| --- | --- |
| Items | 16 |
| Done | 7 |
| Contract-change note | `docs/contract-change-v3.0.md` — created in item 5, extended by items 7–13 |
| Blocking decisions (`D`) | none open |

---

## Standing rules for every item

- **Docker only.** Nothing runs on the host. Tests: `docker compose run --rm test`.
  Pipeline: `docker compose run --rm app ./analyze …`.
- **Delete the tests with their subject.** A deleted module's test file is
  deleted in the same commit; a reshaped module's tests are rewritten, not
  skipped.
- **Delete the docs with their subject** (constitution §4). Every item that
  invalidates a line in `docs/` fixes or deletes that line in its own commit.
  Item 15 is the sweep for what is left over, not the place to defer to.
- **No compatibility shims.** When a field goes, it goes; the change note
  records it.
- **No silent fallbacks** (constitution §2). A stage that cannot produce an
  honest value emits `unknown` or fails — never a plausible default.
- **`SCHEMA_VERSION`** in `src/analyzer/models.py` is bumped once, in item 7,
  the first item that reshapes a projected file.

### Removing a debugger lane

Several deletion items remove a lane. The full set of touch points, so no item
has to rediscover them:

1. `ui/src/data/paths.ts` — the `artifactPaths` entry.
2. `ui/src/data/sparseArtifacts.ts` — the parser and its exported types.
3. `ui/src/timeline/laneState.ts` — the registry row in the lane list.
4. `ui/src/timeline/laneContent.ts` + `laneRenderers.ts` + `sparseTints.ts` —
   the lane's `kind` branch.
5. `ui/src/App.tsx` — the load call and any state wiring.
6. `ui/src/data/__fixtures__/` — the unit-test fixture, if the lane has one.
7. `ui/src/**/*.test.ts(x)` — assertions naming the lane.
8. `tests/ui-visual/fixtures/analysis/*/` — rebuild via
   `python3 tests/ui-visual/fixtures/build-fixtures.py` so the frozen fixtures
   stop carrying the deleted artifact and the suite stops 404-ing on it.
9. `tests/ui-visual/__screenshots__/` — re-capture the affected baselines.
10. `docs/reference/ui-regression_guide.md` §2 — the surface row, if the lane is
    named there.

### The Visual QA contract

Items carrying a **Visual QA** block are executed by a low-reasoning executor.
Every check below is binary and carries its expected value inline. The executor
runs **every** check for the surfaces the item touches and reports each as
pass/fail **with the observed value** — never a single overall verdict. If a
check needs an expected value this plan does not give, that is a spec defect to
report back, not a judgement call.

Run, per `docs/reference/ui-regression_guide.md` §6:

```bash
python3 tests/ui-visual/fixtures/build-fixtures.py
docker compose -f docker-compose.yml -f docker-compose.visual.yml up -d --build ui
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9090/     # expect 200
docker run --rm --network host -v "$PWD/tests/ui-visual:/work" -w /work \
  mcr.microsoft.com/playwright:v1.56.0-noble \
  sh -c "npm ci && npx playwright test"
```

Baselines are re-captured with `--update-snapshots` **only** when the item's own
block says the change is intended, and the commit carries a one-line
justification per changed snapshot.

**Runtime assertions, asserted on every Visual QA run before any image diff.**
These need no visual reasoning and catch the largest class of regression:

- R1 — zero `console.error` and zero `console.warn` across the run.
- R2 — zero `pageerror` and zero unhandled promise rejections.
- R3 — zero failed network responses for a resource the page expects. A 404 for
  an artifact an item **deleted** is a failure of step 8 above (the fixture
  still carries it, or the app still requests it), not an allowed case.

Primary baseline surface for every block below is `song-full`
(`/?song=RegFull - Fixture`), the fully-populated fixture. `_test_song` is the
no-audio surface and is never the only target.

---

## Phase A — removals

Nothing in this phase is gated on an experiment; each subject is measured at
zero or has no consumer at all.

### 1. Delete the ML event stack

- [x] Delete `src/analyzer/stages/event_ml.py`, `src/analyzer/event_ml_train.py`,
      `src/analyzer/event_ml_models.py`, `src/scripts/train_event_classifier.py`.
- [x] Remove the `generate-ml-events` entry from `STAGE_PIPELINE_IDS`, its
      import, its `_run_single_stage` branch and its `run_phase_1` call in
      `src/analyzer/pipeline.py`. Drop the unused `ml_events` local.
- [x] Remove `events.ml.json` from `info.json`'s `artifacts` block.
- [x] Delete `tests/test_event_ml.py` and `tests/test_event_ml_train.py`.
- [x] Remove the seeded model directory under `models/` if it exists and is used
      by nothing else.
- [x] Remove the **ML Events** lane (see *Removing a debugger lane*).
- [x] `docs/data_folder_reference.md`: delete the `events.ml.json` entry.
      `docs/source_files_reference.md`: delete §4's Event Classifier row.

**Tests:** `docker compose run --rm test` — full suite green with the two
deleted test files gone. `docker compose run --rm app ./analyze --song
"/data/songs/_test_song.mp3"` completes and writes no `events.ml.json`.

**Visual QA — item 1**

- Surface: `/?song=RegFull - Fixture`, wait for `data-ui-ready` on the document
  element.
- R1, R2, R3 as defined above. R3 specifically: **no request is made to any URL
  containing `events.ml.json`** — observed request count for that substring must
  be `0`.
- V1.1 — the lane list contains no lane whose header label is `ML Events`.
  Observed: the list of lane labels.
- V1.2 — the lane count in `ui/src/timeline/laneState.ts` order is one lower
  than before this item; every remaining lane header renders a non-empty label.
- V1.3 — `song-full` baseline diff: **changes are expected** (one lane row
  removed, lanes below shift up). Re-capture with `--update-snapshots`;
  justification line: "ML Events lane removed with the ML event stack (plan v3.0
  item 1)". Every other baseline (`song-no-audio`, `left-panel`,
  `header-readout`, `follow-playhead`) must diff **only** in lane-row vertical
  offset, and `lanes-hidden-all` must not diff at all.

**Contract note:** none — `events.ml.json` was never projected.

### 2. Delete `event_benchmark.py`

- [x] Delete `src/analyzer/stages/event_benchmark.py` and
      `tests/test_event_benchmark.py`.
- [x] Remove the `benchmark-event-outputs` stage entry, import, single-stage
      branch and `run_phase_1` call from `src/analyzer/pipeline.py`, and the
      `event_benchmark` row from `info.json`'s `artifacts` block.
- [x] Remove `validation/event_benchmark.json` from
      `docs/data_folder_reference.md`.

**Tests:** `docker compose run --rm test`; a `_test_song` run writes no
`artifacts/validation/event_benchmark.json`.

**Visual QA:** none — the file backs no lane.

**Contract note:** none.

### 3. Delete `unified.py`

- [x] Delete `src/analyzer/stages/unified.py` and
      `src/analyzer/stages/validation/unified.py`.
- [x] Remove the `assemble-music-feature-layers` stage, the
      `validate-unified` wiring in `src/analyzer/stages/validation/__init__.py`
      and `report.py`, and the `music_feature_layers` row from `info.json`.
- [x] Delete `music_feature_layers.json` from `docs/data_folder_reference.md`.

**Tests:** `docker compose run --rm test`; a `_test_song` run writes no
`artifacts/music_feature_layers.json`.

**Visual QA:** none.

**Contract note:** none — not on the MCP surface.

### 4. Delete `patterns.py`

- [x] Delete `src/analyzer/stages/patterns.py` and
      `src/analyzer/stages/validation/patterns.py`.
- [x] Remove the `extract-chord-patterns` stage and the `patterns_layer` /
      `pattern_mining` rows from `info.json`.
- [x] **Clear the copy-pasted `from analyzer.stages.patterns import
      MAX_PATTERN_BARS, _build_bars, _build_beat_rows, _display_window,
      _pattern_sequence` block from every module under
      `src/analyzer/stages/validation/`** (`sections.py`, `drums.py`,
      `energy.py`, `events.py`, and any other carrying it). Most are unused; any
      that is genuinely used moves with the helper into
      `validation/utils.py` rather than keeping `patterns.py` alive.
- [x] Delete `tests/test_patterns.py`.
- [x] Remove the **Pattern Occurrences** lane (see *Removing a debugger lane*),
      including `parsePatterns` and the `PatternsFile` / `PatternOccurrence`
      types in `sparseArtifacts.ts`.
- [x] Delete the `layer_d_patterns.json` and `pattern_mining/chord_patterns.json`
      entries from `docs/data_folder_reference.md`.

**Tests:** `docker compose run --rm test`; a `_test_song` run completes and
writes neither pattern artifact.

**Visual QA — item 4**

- Surface: `/?song=RegFull - Fixture`.
- R1, R2, R3. R3 specifically: **zero requests to any URL containing
  `layer_d_patterns.json`**.
- V4.1 — no lane header labelled `Pattern Occurrences`.
- V4.2 — `song-full` baseline diff expected; re-capture, justification
  "Pattern Occurrences lane removed with `patterns.py` (plan v3.0 item 4)".
  `lanes-hidden-all` must not diff.

**Contract note:** none.

### 5. Remove the Moises takeover of the canonical grid

This is the honesty repair, and it **must land before item 16**. See
refinement §4 item 7 for why.

- [x] Delete `build_reference_timing_grid` from `src/analyzer/stages/timing.py`
      and `build_reference_harmonic_layer` from
      `src/analyzer/stages/harmonic.py`.
- [x] Remove the `build-reference-timing-grid` and
      `build-reference-harmonic-layer` stage entries, imports and single-stage
      branches from `src/analyzer/pipeline.py`.
- [x] In `run_phase_1`, delete the whole `has_reference_chords` takeover path:
      the `beats_inferred.json` side-write, the `layer_a_harmonic.inferred.json`
      side-write, the `generate-timing-diagnosis` call that compares the two, and
      the two `report["notes"].append(...)` lines that explain the substitution.
      `essentia/beats.json` and `layer_a_harmonic.json` are now always the
      pipeline's own output.
- [x] Decide `generate-timing-diagnosis` in the same commit: it exists only to
      diff inferred against reference-rebuilt grids. Delete it and its stage
      entry.
- [x] **Correct the false note** wherever `phase_1_report.json` states that
      reference chord files are *"authoritative human-validated comparison
      inputs"* (`src/analyzer/stages/validation/report.py` and/or `chords.py`).
      The replacement text states plainly that `reference/moises/*.json` is
      Moises.ai **inference**, that only `lyrics.json` carries a confidence
      field and only its `"0.99"` rows are operator-curated, and that a chord
      comparison against it measures **agreement with a second model**, not
      correctness.
- [x] Update `docs/data_folder_reference.md`: delete the `beats_inferred.json`
      and `layer_a_harmonic.inferred.json` entries; correct the
      `reference/moises/` description to say inference, not ground truth.
- [x] **Create `docs/contract-change-v3.0.md`** with the header paragraph (the
      v2.1 → v3.0 transition; compatibility was not a constraint, documenting it
      is) and its first section: `essentia/beats.json` and
      `layer_a_harmonic.json` are no longer ever rebuilt from
      `reference/moises/`, so a consumer that saw a Moises-derived grid on a
      re-run will not any more.

**Tests:** `docker compose run --rm test`. Then, on a gold song that **has** a
Moises chord reference: `docker compose run --rm app ./analyze --song
"/data/songs/Titanium - David Guetta ft Sia.mp3"` and assert
`artifacts/essentia/beats.json`'s `generated_from.engine` is
`"essentia.RhythmExtractor2013"` — not `"reference.moises.chords"` — and that no
`beats_inferred.json` is written.

**Visual QA:** none — no lane changes shape.

**Contract note:** first section of `contract-change-v3.0.md`, as above.

### 6. Delete symbolic note transcription

- [x] **First**, move `_nearest_beat_alignment` and `_section_for_time` from
      `src/analyzer/stages/symbolic/utils.py` into
      `src/analyzer/stages/drums.py` (or `validation/utils.py` where a validator
      also uses them), so `drums.py` no longer imports from `symbolic/`.
- [x] **Keep `src/analyzer/stages/_omnizart_runtime.py`.** `drums.py` needs
      `resolve_omnizart_drum_model_path`. The verdict table lists it for removal;
      that is a table error, recorded in refinement §2.
- [x] Delete `src/analyzer/stages/symbolic/`,
      `src/analyzer/stages/_basic_pitch_subprocess.py` and
      `src/analyzer/stages/_basic_pitch_runtime.py`.
- [x] Remove the `extract-symbolic-features` stage and every `symbolic` argument
      threaded through `run_phase_1`. Remove the `symbolic_layer`,
      `symbolic_hints` and `symbolic_validation` rows from `info.json`.
- [x] `src/analyzer/stages/ui_data.py`: delete `_beat_aligned_bass_notes`,
      `_pitch_to_note_name`, `NOTE_NAMES` and the `bass` key from each
      `beats.json` row. `chord` stays (it comes from `layer_a_harmonic.json`).
- [x] `src/analyzer/stages/hints.py`: drop its `symbolic` parameter and every
      hint category that reads the symbolic layer — `motif_recall` above all.
      This is a partial cut; item 11 rebuilds the module.
- [x] Remove `basic-pitch` from `requirements.txt` and any basic-pitch-only
      install lines from `Dockerfile`. Leave omnizart and its drum checkpoint.
- [x] Delete `tests/` files whose subject is the symbolic layer; keep
      `tests/test_drums_transcription.py` and fix its imports.
- [x] Remove the **Symbolic Phrases** lane (see *Removing a debugger lane*).
- [x] `docs/data_folder_reference.md`: delete `layer_b_symbolic.json`,
      `symbolic_transcription/validation.json`,
      `symbolic_transcription/hints.json` and the whole
      `symbolic_transcription/basic_pitch/` block (8 entries). Keep
      `drum_events.json` and `omnizart/drums.mid`.
- [x] `contract-change-v3.0.md`: add the `beats.json` row — the `bass` field is
      removed; `time`, `type`, `bar`, `beat` and `chord` are unchanged.

**Tests:** `docker compose run --rm test`. A `_test_song` run completes, writes
`symbolic_transcription/drum_events.json` and `omnizart/drums.mid`, writes no
`layer_b_symbolic.json` and no `basic_pitch/` folder, and the resulting
`beats.json` rows carry no `bass` key. Rebuild the image first
(`docker compose build`) so the requirements change is exercised.

**Visual QA — item 6**

- Surfaces: `/?song=RegFull - Fixture`, then `/?song=_test_song`.
- R1, R2, R3. R3 specifically: **zero requests to any URL containing
  `layer_b_symbolic.json`**.
- V6.1 — no lane header labelled `Symbolic Phrases`.
- V6.2 — the **Drum Density** lane still renders: its lane body contains at
  least one drawn element, and its header label is exactly `Drum Density`. This
  is the check that catches deleting too much.
- V6.3 — `song-full` and `song-no-audio` baseline diffs expected; re-capture with
  justification "Symbolic Phrases lane removed with the symbolic layer (plan
  v3.0 item 6)".

**Contract note:** `beats.json` loses `bass`.

---

## Phase B — replacements

### 7. Replace `sections/` with allin1 named segmentation

The largest item. Refinement §5 item 8 carries the numbers and the reasoning.

- [x] **Image.** Add to `Dockerfile`, after the existing torch install:
      `natten==0.15.1+torch210cu121` from
      `https://shi-labs.com/natten/wheels/cu121/torch2.1.0/index.html`
      (`--trusted-host shi-labs.com`), then `allin1`. Copy the pinning comment
      from `experiments/drop_detection/research/Dockerfile.allin1` — it is the
      one place the reason is written down. Verify `docker compose build`
      succeeds and `import allin1` works inside the `app` service.
- [x] **New stage** `src/analyzer/stages/segmentation.py` (phase 2), stage id
      `segment-sections`, replacing the old one at the same point in
      `run_phase_1`. It:
      - runs `allin1.analyze(..., include_activations=True)` **seeded with the
        pipeline's own stems from `artifacts/stems/`** — port `_seed_demix` from
        `experiments/allin1/model.py`. Seeding is mandatory for determinism
        (constitution §6), not an optimisation;
      - merges equal-labelled neighbouring segments into section runs (ship the
        merged runs, not the raw phrase edges);
      - computes `function_confidence` as `1 −` normalised posterior entropy
        inside each section (port `experiments/allin1/activations.py`);
      - sets `function_status: "unknown"` on every row of a degenerate song
        (fewer than 3 distinct labels, or one label covering >90 % of the
        track), and leaves the boundaries usable;
      - sets `same_label_as` to the `section_id` of the first section carrying
        the same label, else `null`;
      - **does not** use allin1's beat or downbeat times here — item 8 handles
        the downbeat phase separately, and its beat times are never used.
- [x] Delete `src/analyzer/stages/sections/` entirely (`segmenter.py`,
      `form.py`, `utils.py`, `__init__.py`).
- [x] Delete `src/analyzer/stages/_stem_activity.py` **if** `event_features/` is
      already gone; otherwise it goes in item 9.
- [x] `artifacts/section_segmentation/sections.json` rows become:
      `section_id`, `start`, `end`, `function`, `function_confidence`,
      `function_status`, `same_label_as`, `confidence`. **`section_character` is
      removed.**
- [x] `src/analyzer/stages/ui_data.py`: delete the `SECTION_DESCRIPTIONS` map
      keyed by the old 13-value vocabulary and the `energy_character` /
      `repetition_group` / `form_role` fields. Top-level `sections.json` rows
      become `start`, `end`, `label` (from `function` + index + confidence, same
      display shape as today), `description` (one sentence generated from the
      functional label and the section's own measured shape), `section_id`,
      `confidence`. Keep the existing `section_id` join validation — it is the
      MCP join key and must not regress.
- [x] Bump `SCHEMA_VERSION` in `src/analyzer/models.py`.
- [x] Rewrite `tests/test_sections_v2.py` and `tests/test_form_labelling.py`
      against the new stage, or delete them and add
      `tests/test_segmentation.py`. Fix `tests/test_ui_data_section_join.py`.
- [x] **Determinism check** — run `segment-sections` three times on
      `_test_song` and assert byte-identical
      `artifacts/section_segmentation/sections.json`. This is the check that
      catches an unseeded demux.
- [x] `contract-change-v3.0.md`: a `sections.json` section with one row per
      change (`section_character` removed; `function`,
      `function_confidence`, `function_status`, `same_label_as` added), the
      concrete new row shape, and an explicit statement that
      **`get_song_brief`'s `similar_sections` grouping must move from
      `section_character` equality to `function` + `same_label_as`** — naming
      the consumer operation, per the handoff rules.
- [x] `docs/reference/analysis-input-guide.md`: replace the `section_character`
      controlled-vocabulary block and the `similar_sections` paragraph.
- [x] `docs/data_folder_reference.md`: update both `sections.json` entries.

**Tests:** `docker compose run --rm test`. Then all four gold songs:
`docker compose run --rm app ./analyze --song "/data/songs/<song>.mp3"` for
`_test_song`, `Titanium - David Guetta ft Sia`, `Hideaway - Kiesza`,
`Armin - Revolution`. Assert per song: `sections.json` and
`section_segmentation/sections.json` have equal length and the same
`section_id` order; every row carries a non-null `function` **or**
`function_status: "unknown"`; `_test_song` is flagged `unknown` (it is the one
degenerate song of 21).

**Acceptance metric — this is the item's success condition.** Score the new
boundaries against `reference/moises/segments.json` across the four gold songs
with `validate-sections`. **Recall @±1.0 s ≥ 0.50, precision ≥ 0.85, F1 ≥ 0.65**,
against the incumbent's 0.32 / 0.27 / 0.29. If precision lands below 0.85, the
likely cause is shipping phrase edges instead of merged runs — check the merge
before touching anything else. Record both numbers in the commit message
(constitution §3).

**Visual QA — item 7**

- Surface: `/?song=RegFull - Fixture`. Rebuild the fixtures first — the frozen
  `section_segmentation/sections.json` must carry the new shape or every check
  below is meaningless.
- R1, R2, R3.
- V7.1 — the **Sections** lane renders at least 3 blocks, and every block's
  label text matches `^\d+ (Intro|Verse|Chorus|Bridge|Inst|Break|Outro|Solo|Start|End)( \d+)? \(\d\.\d\d\)$`.
  Observed: the list of block labels. A label containing any of `Momentum Lift`,
  `Vocal Spotlight`, `Groove Plateau`, `Breath Space` or any other old
  mood-adjective value is a **fail** — the old vocabulary is still in the tree.
- V7.2 — the leftmost Sections block's left edge is within 2 px of the timeline
  content's left edge, and the rightmost block's right edge is within 4 px of
  the ruler's far right edge at the current zoom. Checked at the **far** end, not
  inferred from the near one.
- V7.3 — click the first Sections block; the inspector shows fields named
  `function`, `function_confidence`, `function_status` and `same_label_as`, and
  shows **no** field named `section_character` or `repetition_group`.
- V7.4 — `song-full`, `timeline-scrolled`, `timeline-zoom` and `lane-collapsed`
  baseline diffs expected in the Sections lane region only; re-capture with
  justification "Sections lane now carries allin1 functional labels (plan v3.0
  item 7)".

**Contract note:** `sections.json` + `artifacts/section_segmentation/sections.json`
— the release's headline change.

### 8. Take the downbeat phase from allin1, with per-downbeat confidence

- [ ] `src/analyzer/stages/timing.py`: keep `extract_timing_grid`'s essentia
      beat *times* exactly as they are. Replace the
      `beat_in_bar = ((index - 1) % 4) + 1` assignment — there is no downbeat
      detection today, only a modulo — with a phase derived from allin1's
      downbeat activations, computed once in item 7's stage and read here (or
      recomputed from the cached model output; do not run the model twice).
- [ ] Beat *times* stay essentia's. allin1's own beats sit a clean half-beat off
      on 4 of 21 songs and halve the tempo on 1; they are never used.
- [ ] Add `confidence` (float) to each `type: "downbeat"` row in the projected
      `beats.json`, from the downbeat activation strength at that beat.
- [ ] Add an `unknown` span representation: where essentia's and allin1's phases
      disagree by a whole beat or more, the affected bars are marked rather than
      silently snapped (constitution §7). Choose the smallest honest encoding —
      a `bar_phase_confidence` block in `beats.json`'s header, or
      `confidence: null` on the affected downbeats — and record the choice in
      the change note.
- [ ] `docs/reference/analysis-input-guide.md`: update the `beats.json` row
      contract.
- [ ] `contract-change-v3.0.md`: `beats.json` gains per-downbeat `confidence`
      and the unknown-span marker; **bar numbers change on most songs**, which
      is the row a consumer most needs to see.

**Tests:** `docker compose run --rm test`. Then score downbeats against
`reference/moises/beats.json` on the four gold songs via `validate-beats`.
**Success condition: downbeat F1 @±70 ms ≥ 0.50**, against the shipped 0.16.
Beat-time F1 must not regress — it is 1.00 on two gold songs today and must stay
there. Both numbers go in the commit message.

**Visual QA — item 8**

- Surface: `/?song=RegFull - Fixture`.
- R1, R2, R3.
- V8.1 — the ruler's bar numbers are strictly increasing left to right with no
  repeats and no gaps. Observed: the first eight bar labels.
- V8.2 — the header bar.beat readout at the default playhead position matches
  the ruler bar under the playhead. Observed: both values.
- V8.3 — `header-readout`, `song-full` and `timeline-zoom` baseline diffs
  expected (bar numbering shifts); re-capture with justification "downbeat phase
  now from allin1 (plan v3.0 item 8)".

**Contract note:** `beats.json`.

### 9. Replace the `event_*` stack with the gestures stage

- [ ] **New stage** `src/analyzer/stages/gestures.py` (phase 3), porting
      `experiments/gestures/primitives.py` and `assembly.py`. It reads only
      phase-1/2 artifacts — `fft_bands.json`, `rms_loudness.json`,
      `drum_events.json`, `beats.json`, `section_segmentation/sections.json` —
      and **never opens the audio** (constitution §5.2).
- [ ] Detectors: riser and downlifter (sliding-window linear regression on
      high-band energy), reverse cymbal (rising mix-RMS ramp into a
      `transient_strength` spike), snare roll (per-bar onset-density doubling in
      `drum_events.json`), impact (simultaneous sub-band + transient spike),
      pre-drop gap (`dropout_strength` spike immediately before an impact).
      Assembly anchors each gesture on a detected impact and fills
      approach / build / tension / release from the primitives in the preceding
      window. **A phase with no supporting primitive is absent, never guessed.**
- [ ] Delete `src/analyzer/stages/event_rules/`,
      `src/analyzer/stages/event_machine/`,
      `src/analyzer/stages/event_features/`,
      `src/analyzer/stages/event_timeline.py`,
      `src/analyzer/stages/event_review.py`,
      `src/analyzer/stages/event_identifiers.py`,
      `src/analyzer/stages/review_queue.py`,
      `src/analyzer/event_contracts.py`, and
      `src/analyzer/stages/_stem_activity.py` if item 7 left it.
- [ ] Remove the stages `build-event-feature-layer`, `infer-song-identifiers`,
      `generate-rule-candidates`, `generate-machine-events`,
      `generate-event-review`, `export-event-timeline`, `build-review-queue`
      from `pipeline.py`, and the eight `event_*` / `review_queue` /
      `energy_identifiers` rows from `info.json`.
- [ ] Rewrite `src/analyzer/contracts/song_event_schema.json` and
      `event_vocabulary.json` to the gesture-phase vocabulary
      (`approach`, `build`, `tension`, `impact`, `release`, plus section
      transitions). Delete `contracts/event_threshold_profiles.json` and
      `contracts/song_event_timeline.json`.
- [ ] **`song_event_timeline.json` is rebuilt** from gesture phases plus item 7's
      section transitions. Each event carries `type`, `start_time`, `end_time`,
      `confidence`, `intensity`, `section_id`, `section_name`, `provenance`,
      `summary`, and `evidence_summary` holding the per-primitive evidence that
      supports it. No `layer_add` / `layer_remove` per-beat deltas. No internal
      implementation notes in `summary` — the string
      `"Breakdown candidates are merged across adjacent negative-delta beats."`
      must not appear in any output.
- [ ] A drop is **never** detected directly; naming stays with the section-pair
      transition (constitution §5.2). The gesture stage says "a build of this
      shape happens here", not "this is the drop".
- [ ] Delete `tests/test_event_features.py`, `test_event_identifiers.py`,
      `test_event_machine.py`, `test_event_rules.py`, `test_event_review.py`,
      `test_event_timeline.py`, `test_event_contracts.py`,
      `test_review_queue.py`. Add `tests/test_gestures.py`.
- [ ] Remove the **Machine Events** and **Identifier Hints** lanes (see
      *Removing a debugger lane*).
- [ ] `docs/data_folder_reference.md`: delete the whole `event_inference/` block
      and `energy_summary/hints.json`; rewrite the
      `song_event_timeline.json` entry.
- [ ] `docs/reference/analysis-input-guide.md`: rewrite the
      `song_event_timeline.json` contract's event vocabulary.
- [ ] `contract-change-v3.0.md`: the `song_event_timeline.json` section —
      removed event types, the new phase vocabulary, the removed
      `event_inference/` file set.

**Tests:** `docker compose run --rm test`. Then all four gold songs. Assert per
song: every event's `section_id` resolves against
`section_segmentation/sections.json` (an unresolvable id is dropped by the MCP
read — this is the check that catches it); every `summary` is non-empty and
contains none of the three known boilerplate strings; events/min is under 20.

**Acceptance metric.** Impact-phase recall of the 7 hand-marked drop impacts:
**≥ 4/7 @ ±1.0 s and ≥ 2/7 @ ±0.25 s**, against the incumbent's 2/7 and 0/7.
Both numbers in the commit message.

**Visual QA — item 9**

- Surface: `/?song=RegFull - Fixture`. Rebuild fixtures first.
- R1, R2, R3. R3 specifically: **zero requests to any URL containing
  `events.machine.json` or `energy_summary/hints.json`**.
- V9.1 — no lane header labelled `Machine Events` or `Identifier Hints`.
- V9.2 — the **Gestures** lane renders at least one block, and each block's label
  is one of `approach`, `build`, `tension`, `impact`, `release` or a section
  transition of the form `<label> → <label>`. Observed: the block labels.
- V9.3 — open the Gestures lane events panel; the first card's body text is
  non-empty and does **not** equal any of: `Arrangement appears to gain material
  at this beat.`, `Arrangement appears to strip back at this beat.`,
  `Breakdown candidates are merged across adjacent negative-delta beats.`
  Observed: the card's body text.
- V9.4 — `song-full`, `lane-events` and `lane-events-active` baseline diffs
  expected; re-capture with justification "event stack replaced by the gestures
  stage (plan v3.0 item 9)".

**Contract note:** `song_event_timeline.json`.

### 10. Cut validation to what has labels

Runs after item 9 so the validators die with their subjects.

- [ ] Delete `src/analyzer/stages/validation/events.py` and
      `validation/energy.py` (`validation/patterns.py` and `validation/unified.py`
      went in items 4 and 3).
- [ ] Reduce `src/analyzer/stages/validation/form_drops.py`: **delete the `form`
      target** — it reports `mode: "unlabelled"`, `labelled_boundary_count: 0`
      on all four gold songs, and `validate-sections` against
      `reference/moises/segments.json` supersedes it. **Keep the `drops`
      target, timed-only**: where a song has no timed human drop hints it emits
      `skipped` with the reason, never the `presence` check that passes by
      construction. Rename the module `drops.py`.
- [ ] Keep `validation/beats.py`, `chords.py`, `sections.py`, `drums.py`.
- [ ] **Fix the `validate-chords` crash** logged in `docs/issues.md`.
      `validation/chords.py` lines 62-63 read `row["bar_num"]` and
      `row["beat_num"]` from `reference/moises/chords.json`, which carries
      neither — 487 of 487 rows on Titanium lack both, and the real schema is
      `curr_beat_time`, `curr_beat`, `prev_chord`, `chord_*`. It raises
      `KeyError: 'bar_num'` and takes the whole run non-zero, so **item 16
      cannot pass until this is fixed**. Found during item 5 and not caused by
      it: the deleted `build_reference_timing_grid` read the same fields as
      `int(row.get("bar_num") or 0)` and so silently produced `bar: 0` rather
      than raising. Derive the bar/beat position from the pipeline's own grid,
      or state honestly that it cannot be computed — no invented default
      (constitution §2). Delete the `docs/issues.md` entry in the same commit
      that fixes it (constitution §4.2).
- [ ] Rewire `validation/report.py` and `validation/__init__.py` to the surviving
      set; remove the dead `compare_targets` entries from
      `src/analyzer/config.py` and the CLI help in `src/analyzer/cli.py`.
- [ ] Update `tests/test_validation.py` and `tests/test_validation_form_drops.py`
      (rename to match) to the reduced surface.
- [ ] `docs/reference/phase_1_validation_cli.md`: update the compare-target list
      and the report shape. `docs/data_folder_reference.md`: delete the
      `form_score.json` entry and the deleted validators' outputs.

**Tests:** `docker compose run --rm test`. A `_test_song` run writes a
`phase_1_report.json` whose compare targets are exactly the surviving four, with
no target reporting `mode: "unlabelled"`.

**Visual QA — item 10**

- Surface: `/?song=RegFull - Fixture`.
- R1, R2, R3.
- V10.1 — the **Regression Overlay** lane still renders and its header label is
  exactly `Regression Overlay`.
- V10.2 — the validation snapshot region shows a status value and a beat-match
  ratio, both non-empty. Observed: both values.
- V10.3 — `validation-snapshot` region diff expected if the target list is shown
  there; re-capture with justification "validation cut to labelled targets (plan
  v3.0 item 10)".

**Contract note:** none — `validation/` is not projected.

### 11. Rebuild `hints.json` around the human hints

- [ ] Merge `reference/human/human_hints.json` into `hints.json` as
      `source: "human"` hints under the matching `section_id`. Reuse the window
      → section matching already in `src/analyzer/stages/hint_alignment.py`
      rather than writing a second one.
- [ ] `summary.user_hint_count` must be **> 0 on every song that has a
      `reference/human/human_hints.json`** — four gold songs today. It is 0 on
      all 21 right now; that is the defect this item closes.
- [ ] Cut the generated hints to those that name a moment, a contrast or an
      intent. Delete every category whose text is a shape description
      ("layered section with undulating contour, dense activity"). `motif_recall`
      is already gone with item 6.
- [ ] `category` stays a short tag from `strobe`, `movement`, `intensity`,
      `transition`, `color`, `phrase_boundary`.
- [ ] Drop any hint whose `text` is empty.
- [ ] Rewrite `tests/test_hints.py`; add a case asserting `user_hint_count`
      is non-zero for a fixture song carrying human hints, and a case asserting
      a human hint's `text` reaches `hints.json` verbatim.
- [ ] **Never write to `reference/human/`** (constitution §9). This item reads
      it only.
- [ ] `docs/reference/analysis-input-guide.md`: update the `hints.json` category
      list. `contract-change-v3.0.md`: the `hints.json` section — human hints now
      present, removed inference categories listed by name.

**Tests:** `docker compose run --rm test`. Then the four gold songs; assert
`hints.json`'s `summary.user_hint_count` equals the number of hints in that
song's `reference/human/human_hints.json`, and that
`inference_hint_count` has fallen (877 across 21 songs today).

**Visual QA — item 11**

- Surface: `/?song=RegFull - Fixture`.
- R1, R2, R3.
- V11.1 — the **Human Hints** lane renders exactly 3 blocks for the `RegFull`
  fixture (the three frozen blocks the regression guide §3.1 pins), at their
  pinned `start_time` / `end_time`. Observed: the three time pairs.
- V11.2 — open the Human Hints lane events panel; the first card's text is
  non-empty. Observed: the text.
- V11.3 — `lane-events` and `song-full` baselines must **not** diff. This item
  changes a generated artifact, not the human-hints lane rendering; a diff here
  means the hint merge wrote into the human-hint path and is a **fail**.

**Contract note:** `hints.json`.

---

## Phase C — publishing, docs, re-baseline

### 12. `energy.py` — keep the computation, stop publishing it

- [ ] `extract_energy_features` stops writing
      `artifacts/energy_summary/features.json` (4.0 MB/song) and returns its
      payload in memory to `derive_energy_layer`.
- [ ] `derive_energy_layer` keeps writing `layer_c_energy.json` — small, and the
      debugger's **Energy Profile** lane reads it.
- [ ] Remove the `energy_features` row from `info.json` and the
      `energy_summary/features.json` entry from
      `docs/data_folder_reference.md`. Fix the two `_run_single_stage` branches
      that load `energy_summary/features.json` from disk: single-stage execution
      of `derive-energy-layer` now recomputes the features rather than reading a
      file that no longer exists.

**Tests:** `docker compose run --rm test`. A `_test_song` run writes
`layer_c_energy.json` and no `energy_summary/` folder.
`./analyze --stage derive-energy-layer` on an already-analysed song succeeds.

**Visual QA — item 12**

- Surface: `/?song=RegFull - Fixture`.
- R1, R2, R3.
- V12.1 — the **Energy Profile** lane renders a non-empty curve: its canvas has
  at least one non-background pixel column in the left, middle and right thirds
  of the lane body. Checked in all three thirds, not only the left.
- V12.2 — `song-full` baseline must **not** diff.

**Contract note:** none — neither file is projected.

### 13. `harmonic.py` — project a compact form

Decision taken in refinement §6 item 13: keep and project.

- [ ] Add `key` and `chord_progression` to each top-level `sections.json` row —
      the section's key, and its dominant repeating chord sequence as a short
      string (e.g. `"Am–F–C–G"`). Both `null` where confidence is too low to
      state one; **no invented C-major default** (constitution §2).
- [ ] Carry the honest confidence: the projected value must reflect that exact
      root+quality agreement with Moises is 1.00 / 0.69 / 0.51 / 0.38 across the
      four gold songs.
- [ ] If a compact form cannot be produced honestly on the gold songs, **stop
      computing chords instead**: delete `harmonic.py`, `validate-chords`, the
      chord lane and the `chord` field in `beats.json`, and record that in the
      change note. Do not ship a field the model cannot trust. Write the outcome
      into this item's checkbox line either way.
- [ ] `docs/reference/analysis-input-guide.md` and
      `docs/data_folder_reference.md`: the two new `sections.json` fields.
- [ ] `contract-change-v3.0.md`: `sections.json` gains `key` and
      `chord_progression`, with the agreement numbers stated.

**Tests:** `docker compose run --rm test`. The four gold songs; assert every
`sections.json` row has both keys present, each either a non-empty string or
`null`, and that no row carries a chord label where the section's chord
confidence is below the stage's stated threshold.

**Visual QA — item 13**

- Surface: `/?song=RegFull - Fixture`.
- R1, R2, R3.
- V13.1 — click a Sections block; the inspector shows `key` and
  `chord_progression` fields. Observed: both values (`null` is a pass).
- V13.2 — the **Chord Regions** lane still renders at least one block.
- V13.3 — `song-full` baseline diff expected only if the inspector is open in
  the baseline; otherwise no diff.

**Contract note:** `sections.json`.

### 14. Consolidate the debugger lanes

Only the *promotions* remain — the removals landed with their items.

- [ ] The **allin1 Sections** and **allin1 Transitions** experiment lanes are
      removed from the registry (constitution §3.2: a lane comes out when its
      experiment is promoted). Their content now lives in the production
      **Sections** lane from item 7 and the transition events in
      `song_event_timeline.json` from item 9.
- [ ] The **Gestures** lane stops reading
      `reference/proposals/gestures.json` and reads the production
      `song_event_timeline.json` instead. Remove `artifactPaths.gestures` and
      the `experiment:` marker from its registry row.
- [ ] Remove `artifactPaths.allin1` and its parser.
- [ ] **Leave untouched**: `Drop Proposals`, `Vocal Phrases`, `Reactive Bands`,
      `Phrase Grid`, `Character`, `Vocal Transcription`, `Moises Lyrics`. Those
      experiments are not promoted by this release.
- [ ] Rebuild the frozen fixtures and re-capture the affected baselines.
- [ ] `docs/reference/ui-regression_guide.md` §2: update the surface rows that
      name a removed lane (`inspector-promote` names `allin1Sections` — repoint
      it at the production `sections` lane).

**Tests:** `docker compose run --rm test` (unchanged); the visual suite below;
`cd ui && npm run test` inside the `ui` container for the unit tests.

**Visual QA — item 14**

- Surface: `/?song=RegFull - Fixture`.
- R1, R2, R3. R3 specifically: **zero requests to any URL containing
  `reference/proposals/allin1.json` or `reference/proposals/gestures.json`**.
- V14.1 — no lane header labelled `allin1 Sections` or `allin1 Transitions`.
- V14.2 — the lane headers `Drop Proposals`, `Vocal Phrases`, `Reactive Bands`,
  `Phrase Grid`, `Character`, `Vocal Transcription` and `Moises Lyrics` are all
  still present, each carrying its experiment badge. Observed: the seven labels
  and their badge presence. A missing one is a **fail** — this release does not
  promote those experiments.
- V14.3 — the **Gestures** lane renders at least one block with the fixture's
  production `song_event_timeline.json` in place, and its header carries **no**
  experiment badge.
- V14.4 — `song-full`, `experiment-badge` and `promote-hint` baseline diffs
  expected; re-capture with justification "allin1 and gestures lanes promoted to
  production artifacts (plan v3.0 item 14)".

**Contract note:** the `ui/` consumer section of `contract-change-v3.0.md`.

### 15. Documentation sweep and experiment archival

Everything each item could not finish in its own commit.

- [ ] **`docs/contract-change-v3.0.md`** — finalise. Cross-check every item above
      marked done: each one that changed a consumer-facing surface must be
      traceable to a row. Add the **New files** table and an **Unchanged for
      v3.0** section naming the surfaces a consumer might expect to have changed
      and did not (`info.json`, `genre.json`, `rms_loudness.json`,
      `drum_events.json`).
- [ ] **`CLAUDE.md`** — rewrite "Current state — what to trust": the "Not
      trusted, roughly 5,900 lines" section is now the deleted set; the line
      counts, the "known-good direction (researched, not yet implemented)"
      paragraph and the "what actually reaches the light show" file list all
      change.
- [ ] **`docs/source_files_reference.md`** — currently maps `src/` by Epic and
      describes stages this release deleted. Rewrite it to the surviving tree.
- [ ] **`docs/data_folder_reference.md`** — final pass. Also delete the
      `data/fixtures/fixtures.json` and `data/fixtures/pois.json` entries: that
      folder has never existed in this repo and is out of scope per constitution
      §1.1.
- [ ] **`docs/experiments_pending.md`** — move the `allin1`, `CLAP` and
      `Transition-FX and gesture phases` entries, with their filled-in results
      and conclusions, to `docs/archive/experiments.md`, marked **promoted**
      (constitution §3.4). The CLAP entry is promoted only in part — its
      character layer is **not** in this release — so it moves marked
      *identity result archived, character layer still queued*, and the
      character-layer question stays in `experiments_pending.md` as its own
      entry. Add a line to the wave-2 review section saying which release
      executed its §1–§2 verdicts.
- [ ] **`experiments/allin1/README.md`** and **`experiments/gestures/README.md`**
      — change the status line from "not promoted" to naming this release. The
      measurements stay: measured evidence does not go stale (constitution §4).
- [ ] **`docs/README.md`** — the "Open work" and "Measured evidence" tables.
- [ ] **Root `README.md`** — its "Pipeline" table lists the Epic 2 pattern
      mining, Epic 4 symbolic layer, Epic 5 ML classifier and Epic 7
      feature-layer assembly, all of which this release deletes. Rewrite the
      table to the surviving stages. Any status line points at this plan rather
      than restating it.

**Tests:** `docker compose run --rm test`. Then a documentation consistency
check: every file path named in `docs/data_folder_reference.md` under
`data/analysis/<song>/` exists after a full `_test_song` run, and every stage
name in `docs/reference/phase_1_validation_cli.md` exists in
`STAGE_PIPELINE_IDS`.

**Visual QA:** none.

### 16. Re-run the corpus and re-baseline

**Runs last, and never before item 5.** Before item 5 lands, a re-run rebuilds
`essentia/beats.json` for `Titanium`, `Hideaway` and `Armin` out of Moises's
chord file.

- [ ] `docker compose build` so the image carries the item 7 additions and the
      item 6 removals.
- [ ] `docker compose run --rm app ./analyze --all-songs --device cuda` — 21
      songs, each in its own subprocess.
- [ ] Confirm `validate-beats`, `validate-chords` and `validate-sections` now
      report a real result on all four gold songs rather than `skipped` on 20 of
      21. That is the item's whole point: one run turns 1 validated song into 4.
- [ ] Record the four gold songs' post-run numbers — section F1 against the
      Moises boundaries, downbeat F1, impact recall — in the commit message, and
      write them into `CLAUDE.md`'s "Current state" section, replacing the
      pre-v3.0 figures.
- [ ] Rebuild `tests/ui-visual/fixtures/` from the re-run output and re-capture
      any baseline that moves.
- [ ] Spot-check artifact sizes: the per-song `artifacts/` tree should have lost
      roughly 20 MB (`event_inference/` 8.8 MB, `layer_b_symbolic.json` 7.0 MB,
      `energy_summary/features.json` 4.0 MB).

**Tests:** the full corpus run is the test. It must exit non-zero on no song.

**Visual QA — item 16**

- Surfaces: `/?song=RegFull - Fixture` and `/?song=_test_song`, after the
  fixture rebuild.
- R1, R2, R3 — on both surfaces.
- V16.1 — every lane in the registry either renders at least one element or is
  absent from the DOM entirely. Observed: for each lane, its label and its
  element count. A lane present with zero elements on the fully-populated
  fixture is a **fail**.
- V16.2 — full baseline set re-captured and reviewed; the commit carries one
  justification line per changed snapshot.

**Contract note:** none — item 15 finalised it.

---

## Decisions (`D`)

*None open.* Two verdicts the source table left ambiguous were resolved in the
refinement doc before planning: `patterns.py` → remove (item 4),
`harmonic.py` → keep and project (item 13). A decision that surfaces during
execution and genuinely blocks an item is added here as `D1`, `D2`, … and the
run continues with the next independent item.

### D1 — the visual-regression suite was already red at HEAD — **resolved**

Measured before item 1 landed, on a clean tree at `6cc30dd`: the Playwright
suite reports **26 failed, 3 passed, 1 did not run**. The identical counts come
back with item 1's changes applied, so this release did not cause it. Two
independent pre-existing causes:

1. **Fixture gap.** The `NEEDED` list in
   `tests/ui-visual/fixtures/build-fixtures.py` was never updated when four
   lanes were added to the UI registry, so the frozen fixtures do not carry
   `reference/proposals/{vocal_phrases,reactive_bands,gestures,grid}.json`. The
   app 404s on all four, which trips R1 and R3 on every spec that asserts a
   clean console.
2. **Stale baselines.** `tests/ui-visual/__screenshots__/` was last captured
   before those lanes existed — `song-full.png` expects 1280×1044 where the app
   now renders 1280×1148.

**Decision:** repair the harness in its own preparatory commit, *before* item 1,
rather than logging it and continuing. Rationale: this plan gates eight items on
a **Visual QA** block whose runtime assertions R1–R3 are defined as "zero
console errors, zero 404s". Against a suite that is already failing those
assertions for unrelated reasons, no item's block can distinguish a regression
it caused from the standing red, so every Visual QA verdict in the run would be
unfalsifiable. The repair touches only `tests/ui-visual/` — no `src/`, no
`ui/src/` — so it changes no app behaviour and no item's scope. Item 16's own
fixture rebuild and re-baseline still stands; this makes the intervening fifteen
items checkable.

**What the repair did.** Reconciling `NEEDED` against every URL the UI actually
requests found **seven** missing entries, not the four that were 404-ing: the
four proposal files above, plus `reference/human/song_facts.json` and
`artifacts/validation/review_queue.json` (fetched by `ReviewQueuePanel.tsx`) and
`reference/moises/lyrics.json`, which survived in the fixture tree only as a
leftover from an older list — untracked, the next rebuild's `rmtree` would have
deleted it silently. Ten baselines were re-captured. One further stale
assertion surfaced: `experiment-badge.spec.ts` expected exactly five flask
badges while `laneState.ts` tags nine. The **app is right and the spec was
stale** — constitution §3.2 badges a lane while its experiment is unpromoted,
and item 14's V14.2 requires seven of those nine to keep their badge; the two
allin1 lanes it promotes are the other two. The spec was corrected to track the
registry, `laneState.ts` was not touched. Suite now **30 passed, 0 failed**.

**Note for item 16.** The rebuild also revealed that the source analysis data on
disk still carries Epic-7 `lighting_events` / `beatdrop_visual_plan` fields in
`info.json`, which CLAUDE.md says were deleted in 2026-09-02. That drift was
reverted rather than frozen into the fixtures; item 16's corpus re-run is what
actually clears it.
