# Product refinement — v3.0

**The release that acts on the wave-2 module verdicts.** Its source is the
`Module-by-module: what is measured, and what it costs` table in
[`experiments.md`](experiments.md); the operator has approved
that table's **verdict column** as the scope of this release, replacements
included.

Compatibility is not a constraint here (constitution §10). Four projected files
change shape, one controlled vocabulary is deleted, and roughly 6,000 lines and
~20 MB of per-song artifact leave the tree. Documenting those changes is the
constraint — every contract change lands in `contract-change-v3.0.md` as its
item is implemented.

*Scope note.* §3 of the wave-2 review ("Complement — signals the pipeline has no
equivalent of": vocal phrase edges, character blocks as a standalone layer,
section identity) is **not** in this release. Those are queue entries in
`experiments.md`, not rows in the verdict table. The one place a §3
signal is unavoidable is `section_character`, because deleting `sections/`
deletes the field's producer — item 8 resolves that by replacing the field
rather than refilling it.

---

## 1. What this release is trying to fix

Three facts drive every item below.

**The expensive half of the pipeline produces nothing a cue author reads.**
`events.ml.json` holds an empty `events` array on every song that has the file.
`event_benchmark.py` writes `status: "skipped"` on 21 of 21 because
`benchmark_annotations/` has never existed in this repository. `hints.json`
reports `user_hint_count: 0` on all 21 songs while the operator's own timed,
lighting-specific hints sit unread in `reference/human/`. `repetition_group` is
absent from all 290 sections of all 21 projected `sections.json` files.

**The two highest-priority projected files measure worst.** `sections.json`
lands 0/7 hand-marked impacts within ±1.0 s and loses to an evenly spaced grid
at the same boundary budget; against the 38 Moises segment boundaries its F1 is
0.29 where allin1 reaches 0.67–0.80. `song_event_timeline.json` lands 0/7 at
±0.25 s, and 52 % of its 2,395 events are a per-beat energy delta with a fixed
sentence attached.

**There is no downbeat detection at all.** `timing.py` assigns
`beat_in_bar = ((index - 1) % 4) + 1` — bar 1 begins at the first beat essentia
returns, unconditionally. That is not a tracker that scores 3/7; it is a
modulo. It explains the 0.16 downbeat F1 against 385 Moises downbeats, and it
means the bar numbers the cue author snaps to are an assumption, not a
measurement.

---

## 2. The approved verdicts, and what each becomes

| `src/` module | verdict | this release's item |
| --- | --- | --- |
| `stems.py`, `loudness.py`, `fft_bands.py`, `drums.py`, `genre.py` | keep | untouched |
| `ui_data.py`, `hint_alignment.py` | keep | rewired by items 8–11 |
| `timing.py` | keep beats, replace downbeat phase | **9** |
| `harmonic.py` | keep as input — decide project-or-stop | **13** (decision: project) |
| `energy.py` | keep as input, stop publishing | **12** |
| `sections/` | REPLACE | **8** |
| `event_rules/`, `event_machine/`, `event_features/` | REPLACE | **10** |
| `event_timeline`, `event_review`, `event_identifiers`, `review_queue`, `event_contracts` | REPLACE | **10** |
| `event_ml*` | REMOVE | **1** |
| `event_benchmark.py` | REMOVE | **2** |
| `symbolic/`, `_basic_pitch*` | REMOVE | **5** |
| `patterns.py`, `validation/patterns.py` | REMOVE or project | **4** (decision: remove) |
| `unified.py`, `validation/unified.py` | REMOVE | **3** |
| `hints.py` | REBUILD | **11** |
| `validation/` (rest) | cut to what has labels | **6** |

**One correction to the table.** It lists `_omnizart_runtime` among the modules
to remove alongside `symbolic/`. `drums.py` — which the same table keeps —
imports `resolve_omnizart_drum_model_path` from it, and also imports
`_nearest_beat_alignment` and `_section_for_time` from `symbolic/utils.py`.
`_omnizart_runtime.py` therefore stays, and those two helpers move into
`drums.py` before `symbolic/` is deleted. Only `symbolic/`,
`_basic_pitch_subprocess.py` and `_basic_pitch_runtime.py` go.

---

## 3. Removals — inference that returns nothing

### Item 1 — delete the ML event stack

`event_ml.py`, `event_ml_train.py`, `event_ml_models.py`,
`src/scripts/train_event_classifier.py`, the `generate-ml-events` stage, and
`tests/test_event_ml.py` / `tests/test_event_ml_train.py`. 1,080 lines that
produce an empty `events` array on every song that has the file. The debugger's
**ML Events** lane and `artifactPaths.mlEvents` go with it.

Nothing reads `events.ml.json`. Nothing has ever read it.

### Item 2 — delete `event_benchmark.py`

175 lines that score against `benchmark_annotations/<song>.json`, a directory
that does not exist. Every run writes `status: "skipped", reason: "No benchmark
annotation file exists for this song."` A validation stage that has never
validated anything is worse than no validation stage, because the report it
writes reads like coverage. `tests/test_event_benchmark.py` goes with it.

### Item 3 — delete `unified.py` and `validation/unified.py`

351 lines that merge four layer files into `music_feature_layers.json`. None of
the four is on the MCP surface, so the merge is invisible squared.

### Item 4 — delete `patterns.py` and `validation/patterns.py`

**Decision: remove, not project.** Chord-pattern mining is honest deterministic
arithmetic, it has never been scored, and it reaches no projected file. The
argument for projecting it is that repeated chord sequences are a cheap proxy
for section identity — but identity is a measured, open question with a
standing bar (MFCC pair AUC 0.73) and its own queue entry, and shipping an
unmeasured proxy into `sections.json` would be exactly the confident-wrong
answer §2 forbids. 603 lines out, `layer_d_patterns.json` and
`pattern_mining/chord_patterns.json` gone, the debugger's **Pattern
Occurrences** lane gone.

Note that every module under `validation/` carries a copy-pasted import of
`MAX_PATTERN_BARS`, `_build_bars`, `_build_beat_rows`, `_display_window` and
`_pattern_sequence` from `analyzer.stages.patterns`, most of them unused.
Deleting `patterns.py` means clearing that block from each of them.

### Item 5 — delete symbolic note transcription

`symbolic/` (1,341 lines), `_basic_pitch_subprocess.py`,
`_basic_pitch_runtime.py`, and 7.0 MB per song of `layer_b_symbolic.json` plus
the `symbolic_transcription/basic_pitch/` tree. Its only route to the authoring
model is the templated `motif_recall` hint — 244 of the 877 generated hints, all
the same sentence — which item 11 deletes anyway. Projected drum events come
from `drums.py`, which stays.

Two consequences to handle rather than discover:

- `drums.py` keeps `_omnizart_runtime.py` and absorbs `_nearest_beat_alignment`
  and `_section_for_time`.
- `beats.json` rows lose their `bass` field, which `ui_data.py` derives from
  `basic_pitch/bass.json`. `bass` is not in the projected `beats.json` contract
  (`time`, `type`, `bar`, `beat`) and the input guide says per-beat features are
  not consumed, so this is a contract *narrowing*, recorded in the change note.
- `_stem_activity.py` is used only by `sections/` and `event_features/`, both
  deleted by items 8 and 10; it goes in whichever lands second.

### Item 6 — cut validation to what actually has labels

Keep the validators that compare against real reference data:

- **`validate-beats`** — compares against `reference/moises/beats.json`.
- **`validate-chords`** — compares against `reference/moises/chords.json`.
- **`validate-sections`** — compares against `reference/moises/segments.json`.
  This is the one that matters most after item 8: 38 interior boundaries across
  the four gold songs, which is 5× the evidence the seven hand-clicked impacts
  give, and it is the metric item 8 has to hold up under.
- **`validate-drums`** — an internal-consistency check on the drum artifact's
  own summary. No musical claim, cheap, catches artifact corruption.

Delete `validation/events.py`, `validation/energy.py`, `validation/patterns.py`
and `validation/unified.py` with their subjects. Reduce
`validation/form_drops.py` (387 lines): the `form` target reports
`mode: "unlabelled"`, `labelled_boundary_count: 0` on all four gold songs and is
superseded by `validate-sections` against the Moises segments — delete it. The
`drops` target keeps the 7 timed human impacts and stays, **timed-only**: where
a song has no timed drop hints it emits `skipped` with the reason, never the
`presence` check that passes by construction.

`validation/report.py` is rewired to the surviving set.

---

## 4. Honesty repairs

### Item 7 — stop substituting Moises inference for the canonical grid

`run_phase_1` currently does this whenever `reference/moises/chords.json`
exists: it writes essentia's grid aside as `beats_inferred.json`, then rebuilds
`essentia/beats.json` **out of the reference file's `curr_beat_time`,
`bar_num` and `beat_num` columns** (`build_reference_timing_grid`), and does the
same for the harmonic layer (`build_reference_harmonic_layer`). Every downstream
phase then runs on the substituted grid.

Three things are wrong with it, and all three are load-bearing now:

1. **The premise is false.** `reference/moises/*.json` is Moises.ai *inference*,
   not hand-labelling. Only `lyrics.json` carries a confidence field at all, and
   only its `"0.99"` rows are operator-curated; `beats.json`, `chords.json` and
   `segments.json` have no confidence key, so nothing in them is curated. The
   takeover promotes a second vendor's model output into the canonical artifact
   with no gate (constitution §2: "never copy `reference/` into a generated
   artifact except through an explicit, confidence-gated, provenance-recorded
   promotion").
2. **It contradicts the verdict table.** The table says *keep beats* — essentia
   is 7/7 within 0.25 s of a hand-marked impact and at or above Moises on beat
   F1 everywhere except `Hideaway`.
3. **It makes chord validation circular.** With the takeover on, the harmonic
   layer is rebuilt from Moises and then validated against Moises.

It also has not fired yet: the Moises references for `Titanium`, `Hideaway` and
`Armin` landed 2026-09-02, and the last full run was 2026-08-30. **The corpus
re-run (item 16) must not happen before this item lands**, or three of the four
gold songs silently acquire a Moises-derived beat grid.

Delete `build_reference_timing_grid` and `build_reference_harmonic_layer`, the
`build-reference-timing-grid` and `build-reference-harmonic-layer` stages, the
`beats_inferred.json` / `layer_a_harmonic.inferred.json` side-writes, and the
two report notes that explain them. In the same item, correct the
`phase_1_report.json` note that reads *"Chord validation treats reference chord
files as authoritative human-validated comparison inputs when present"* — they
are a second model's opinion, and the note must say so.

---

## 5. Replacements

Promotion is being asked for here by the operator, which is what constitution
§3.3 requires. The gating runs the wave-2 review recommended first —
**SongFormer**, the **gestures per-primitive precision audit by ear**, and the
**vocal-phrase budget-matched ablation** — have *not* happened. The operator has
chosen to proceed anyway. What that costs is recorded in §7 below rather than
argued here.

### Item 8 — `sections/` → allin1 named segmentation

**Replaces** `src/analyzer/stages/sections/` (1,403 lines: `segmenter.py`,
`form.py`, `utils.py`), the 13-value `section_character` vocabulary, and the
per-section mood adjectives.

**With** a phase-2 stage that runs All-In-One seeded with the pipeline's own
stems, and emits merged label runs over the Harmonix functional vocabulary
(`intro verse chorus bridge inst break outro solo start end`).

| | recall @±1.0 s vs 38 Moises boundaries | precision | F1 | bounds/min |
| --- | --- | --- | --- | --- |
| allin1 sections | 0.53 | **0.91** | 0.67 | 1.8 |
| allin1 phrase edges | **0.84** | 0.76 | **0.80** | 3.4 |
| shipped `sections.json` | 0.32 | 0.27 | 0.29 | 3.7 |
| evenly spaced grid, same budget | 0.24 | — | — | 3.7 |

Ship the **merged section** boundaries (0.91 precision, 1.8/min), not the
phrase edges: a boundary the cue author can trust is worth more than one more
recalled boundary, and merging equal-labelled neighbours is what turns an 8-bar
phrase grid into song form.

**Environment.** `experiments/drop_detection/research/Dockerfile.allin1` is
`FROM ai-light-song-v2:dev` plus two pip lines — `natten==0.15.1+torch210cu121`
from the NATTEN wheel index, then `allin1`. The analyzer image already carries
torch 2.1.2, which is the version natten 0.15.1 is built against. The dependency
conflict documented in the research sandbox is with `beat_this` (torch 2.13),
which this release does not promote. So allin1 moves into the analyzer image
directly; no sidecar container, no second image.

**Determinism.** allin1 runs `demucs` itself unless handed stems, and demucs is
not reproducible run to run — the experiment's caches disagree on 14 of 21 songs
across two unseeded runs, and the earlier "allin1 degenerates on instrumental
trance" conclusion was that plumbing bug, not a model property. Seeded with the
pipeline's stems it produced byte-identical section sequences over three
consecutive runs on each gold song. **Seeding from `artifacts/stems/` is
mandatory, not an optimisation** (constitution §6).

**Contract changes to `artifacts/section_segmentation/sections.json`:**

| field | change |
| --- | --- |
| `section_character` | **removed** — a 13-value invented vocabulary derived from a segmenter that measured at chance |
| `function` | **added** — the Harmonix functional label; the named part the constitution §1.2 asks for |
| `function_confidence` | **added** — 1 − normalised entropy of allin1's frame posterior inside the section |
| `function_status` | **added** — `"known"` / `"unknown"`; `"unknown"` on a degenerate song (1 of 21: `_test_song`, a 58 s excerpt), where the boundary may still be usable but the name is not |
| `same_label_as` | **added** — the `section_id` of the first section carrying this label, or `null` |
| `section_id`, `start`, `end`, `confidence` | unchanged; `section_id` remains the join key |

**`same_label_as` is label repetition, not acoustic identity.** It says "the
third thing allin1 called a chorus", not "this is the same music as the first
chorus". The field name and the change note must both say so, because the
temptation to read it as identity is exactly the overstatement that would make
it worse than the `null` `repetition_group` it succeeds.

**Downstream:** the MCP server's `get_song_brief` `similar_sections` grouping
currently runs on `section_character`. It must group on `function` +
`same_label_as` instead. That is a code change in a consumer this repo does not
own, and it is the headline row of the change note.

The top-level `sections.json` `label` and one-sentence `description` are
regenerated from the functional label and the section's own measured shape;
`ui_data.py`'s `SECTION_DESCRIPTIONS` map keyed by the old vocabulary goes.

### Item 9 — downbeat phase from allin1, with honest confidence

**Replaces** `timing.py`'s `((index - 1) % 4) + 1` bar assignment. **Keeps**
essentia's beat *times* untouched — this is a phase swap, not a grid swap.

| downbeat source | F1 @±70 ms vs 385 Moises downbeats | songs right |
| --- | --- | --- |
| allin1 | **0.59** | 3 of 4 |
| essentia as shipped | 0.16 | 1 of 4 |

allin1 is already in the pipeline once item 8 lands, so its downbeat phase costs
nothing. Take the **phase** only: allin1's own beats sit a clean half-beat off
essentia's on 4 of 21 songs and halve the tempo on 1, so its beat times are not
a second opinion worth having.

The honest part carries too, and it is not optional. On `Titanium` essentia sits
exactly +1.00 beats off Moises's bar phase and allin1 +1.96 — three independent
readings, three different phases, which is that song's bar grid being genuinely
unresolved rather than one tracker being sloppy. On `_test_song` all four
hypotheses agree at confidence 1.0 and still miss by 0.66 s. So `beats.json`
gains a **per-downbeat `confidence`** and the ability to mark a span
`"unknown"` where the trackers disagree, per constitution §7's "say so rather
than snapping".

### Item 10 — the `event_*` stack → the gestures stage

**Replaces** `event_rules/` + `event_machine/` + `event_features/` (2,447 lines)
and `event_timeline` + `event_review` + `event_identifiers` + `review_queue` +
`event_contracts` (1,352 lines), plus the 8.8 MB/song `event_inference/` tree
and the `energy_summary/hints.json` identifier file.

**With** a phase-3 stage built from `experiments/gestures/`: named sound-design
primitive detectors (riser, downlifter, reverse cymbal, snare roll, impact,
pre-drop gap) over `fft_bands.json`, `rms_loudness.json` and `drum_events.json`,
assembled on the bar grid into composite gestures with
approach / build / tension / impact / release phases. A phase with no supporting
primitive is absent, never guessed.

| | ±0.25 s | ±0.5 s | ±1.0 s | events/min |
| --- | --- | --- | --- | --- |
| gesture impact phase | 2/7 | 4/7 | 4/7 | 14.1 |
| incumbent `song_event_timeline` | 0/7 | 1/7 | 2/7 | 1.5 |
| RMS-derivative peak-picker (baseline) | **3/7** | **6/7** | **7/7** | 40.8 |

Read that third row honestly: **a one-line peak-picker beats the eight-detector
engine on raw impact recall, firing three times as often.** What it cannot
produce is the thing constitution §1.2 actually asks for — an approach, a build,
a tension span, an impact and a release, each with per-primitive evidence
auditable against the audio. The gestures stage is the only measured method that
produces those, and it beats the 3,800-line incumbent it replaces by a wide
margin. That is the basis for the swap; the recall column is not.

**`song_event_timeline.json` is rebuilt**, and the noise goes with the old
stack: no more `layer_add` / `layer_remove` per-beat energy deltas (52 % of the
current file), no more `"Breakdown candidates are merged across adjacent
negative-delta beats."` (258 occurrences of an internal implementation note in a
projected prose field). Events become gesture phases plus section transitions
from item 8, each with a real `intensity`, a tight window, its `section_id`, and
a `summary` that describes the musical moment.

`src/analyzer/contracts/song_event_schema.json` and `event_vocabulary.json` are
rewritten to the phase vocabulary; `event_threshold_profiles.json` and
`song_event_timeline.json` under `contracts/` go with the stack that used them.

**Constitution §5.2 applies here.** A drop is derived from a named section-pair
transition, not detected off bass-band transients — which is what
`event_identifiers.py` does today, producing 5 `drop` and 20 `fake_drop` events
across the whole 21-song corpus against 7 hand-marked impacts. The gestures
stage deliberately never says "this is the drop"; it says "a build of this shape
happens here". Naming stays with the section pair.

### Item 11 — rebuild `hints.json` around the human hints

The input guide has asked for this since v1.4 and it has never been done:
`reference/human/human_hints.json` merged into `hints.json` as
`source: "human"`. Four gold songs carry that file. `user_hint_count` is **0 on
all 21 songs**. The operator's hand-marked, timed, lighting-specific hints — the
highest-signal text in the repository — reach the authoring model nowhere, while
877 generated sentences drawn from ~330 templates do.

The merge machinery already exists for `human_hints_alignment.json`
(`hint_alignment.py`); this extends it to the consumer file.

In the same item, cut the generated hints to those that name a moment.
`motif_recall` (244 identical sentences) dies with item 5's symbolic layer.
Anything whose text is a shape description — "layered section with undulating
contour, dense activity" — is deleted rather than reworded: it costs tokens and
changes no cue. What survives must name a moment, a contrast, or an intent.

---

## 6. Publishing, plumbing and the record

### Item 12 — `energy.py`: keep the computation, stop publishing it

`energy_summary/features.json` is 4.0 MB per song and, once items 8 and 10 land,
has no consumer at all: `sections/segmenter.py`, `event_features/builder.py`,
`event_identifiers.py` and `unified.py` are the only readers and all four are
deleted. `extract_energy_features` keeps computing and returns its payload in
memory to `derive_energy_layer`; it stops writing the file.

`layer_c_energy.json` stays: it is small and the debugger's **Energy Profile**
lane reads it. `energy_summary/hints.json` goes with `event_identifiers.py`.

### Item 13 — `harmonic.py`: decide project-or-stop

**Decision: keep, and project a compact form.** The verdict table left this
open. `harmonic.py` is trusted DSP, but after item 8 its only remaining
consumers are `validate-chords`, the debugger's chord lane, and `ui_data.py`'s
per-beat `chord` field — and the input guide states plainly that per-beat
features are not consumed. So chords currently reach the cue-authoring model in
no file it reads. Under §1.3 that leaves two options: project it or stop
computing it.

Project it, minimally: each `sections.json` row gains a `key` and a short
`chord_progression` string (the section's dominant repeating chord sequence, or
`null` where confidence is too low to state one). That is one short field pair
per section, it is the harmonic context a cue author needs to justify a colour
choice, and it makes the existing chord validation meaningful rather than
academic. If the compact form cannot be produced honestly on the gold songs, the
fallback is to stop computing chords entirely — not to ship a field the model
cannot trust.

Note that the standing measurement is unflattering and belongs in the change
note: against Moises, exact root+quality agreement is 1.00 on `_test_song`, 0.69
on `Titanium`, 0.51 on `Armin` and 0.38 on `Hideaway`. Two models disagreeing on
~43 % of beats does not say which is wrong, but it does say the chord labels are
not settled, and the projected `confidence` must reflect that.

### Item 14 — the debugger absorbs the new shapes

Remove the lanes whose artifacts no longer exist: **ML Events**, **Machine
Events**, **Pattern Occurrences**, **Symbolic Phrases**, **Identifier Hints**,
and their `artifactPaths` entries and parsers.

Promote the experiment lanes whose stages are now production, so they read the
real artifact rather than `reference/proposals/`: **allin1 Sections** and
**allin1 Transitions** collapse into the existing **Sections** lane (which now
carries the functional label), and **Gestures** reads the rebuilt
`song_event_timeline.json`. Per constitution §3.2 an experiment's lane comes out
of the registry when the experiment is promoted — so
`experiments/allin1/` and `experiments/gestures/` lose their proposal lanes and
their `export` steps stop being part of the review loop.

The lanes belonging to experiments this release does **not** promote —
**Vocal Phrases**, **Reactive Bands**, **Phrase Grid**, **Character**, **Drop
Proposals**, **Vocal Transcription**, **Moises Lyrics** — stay exactly as they
are.

### Item 15 — documentation, in the same commits

Every doc that stops being true is deleted or corrected in the change that makes
it stale (constitution §4), not afterwards:

- **`contract-change-v3.0.md`** — new, in `docs/`. Written incrementally: each
  item that changes a projected file adds its rows as it lands.
- **`docs/reference/analysis-input-guide.md`** — the `section_character`
  vocabulary block, the `similar_sections` grouping rule, the
  `song_event_timeline.json` event vocabulary, the `hints.json` category list,
  and the `beats.json` row shape.
- **`docs/data_folder_reference.md`** — every deleted artifact's entry. It also
  still documents `data/fixtures/fixtures.json` and `data/fixtures/pois.json`,
  a folder that has never existed in this repo and is out of scope per §1.1;
  those entries go too.
- **`docs/source_files_reference.md`** — currently maps `src/` by Epic and
  describes stages this release deletes. Rewritten to the surviving tree.
- **`CLAUDE.md`** — the "Not trusted" section, the line counts, the
  known-good-direction paragraph, and the "what reaches the light show" list.
- **`docs/experiments.md`** — the `allin1`, `clap` and `gestures`
  entries move to `docs/archive/experiments.md` with their filled-in results,
  marked promoted (constitution §3.4). The wave-2 review section stays; its
  §1–§2 verdicts are now history and get a line saying which release executed
  them.
- **`experiments/allin1/README.md`** and **`experiments/gestures/README.md`** —
  status lines change from "not promoted" to naming the release that promoted
  them. The measurements stay; measured evidence does not go stale (§4).

### Item 16 — re-run the corpus and re-baseline

`validate-beats`, `validate-chords` and `validate-sections` currently report
`skipped` on 20 of 21 songs, including three of the four gold songs, because the
Moises references landed after the last full run. One run turns 1 validated song
into 4 for free.

**This runs last, and it must run after item 7.** Before item 7 lands, a re-run
would rebuild `essentia/beats.json` for `Titanium`, `Hideaway` and `Armin` out
of Moises's chord file.

---

## 7. Risks accepted

Stated once, here, rather than re-litigated per item.

- **SongFormer has not been run.** It reports HR.5F 0.703 against All-In-One's
  0.596 on the same Harmonix vocabulary. Promoting allin1 first means the
  pipeline's whole structural read may be wired to the second-best model.
  Mitigation: item 8's stage boundary is the model, not the schema — the
  contract it writes (`function`, `function_confidence`, `same_label_as`) is
  model-independent, so a later SongFormer swap is a stage replacement and not
  another contract change.
- **The gestures per-primitive precision audit by ear was not done.** A phantom
  riser fires a cue that contradicts the music, and nothing in the measurements
  above would catch it — the gold metric is impact recall, which a false riser
  does not affect. This is the single largest unmeasured risk in the release.
  Mitigation: every gesture phase carries its per-primitive evidence string, so
  the audit remains possible against shipped artifacts.
- **Seven hand-clicked impacts is a thin metric.** It separates "at chance" from
  "not at chance" and nothing finer. Everything from here on is scored against
  the Moises boundaries as well: 38 named segment boundaries, 385 downbeats and
  1,433 chord-beats, all sitting unused in `reference/`.
- **Scoring against Moises measures agreement with another vendor's model**, not
  correctness. It is 5–200× more signal than the seven impacts, and it is not
  ground truth. Item 7 exists precisely so the two never get confused again.
- **Section identity still does not reach the authoring model.** `same_label_as`
  is not identity, and this release does not pretend otherwise. The bar for the
  next attempt is MFCC pair AUC 0.73.

---

## 8. Bugs — Open

*Empty.*
