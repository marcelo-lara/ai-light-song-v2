# Contract change — v2.1 → v3.0

This is the downstream handoff note for the v3.0 release
(closed 2026-09-05; its refinement doc and implementation plan were deleted
with the release, per constitution §4 — `git log --diff-filter=D --name-only --
docs/` recovers them). Compatibility with
v2.1 is explicitly not a constraint on this release (constitution §10) —
documenting what changed for anyone consuming the analyzer's output is. Each
section below is added by the plan item that makes the change, in the order
those items land; a section is only written once its item has actually
shipped, not while it is still planned.

---

## 5. Remove the Moises takeover of the canonical grid

`artifacts/essentia/beats.json` and `artifacts/layer_a_harmonic.json` are no
longer ever rebuilt from `reference/moises/`. Previously, whenever
`reference/moises/chords.json` existed for a song, `run_phase_1` silently
discarded the pipeline's own essentia beat grid and HPCP/chord layer and
replaced them with a grid and chord sequence read out of that reference file's
`curr_beat_time`, `bar_num`, `beat_num` and chord columns — while writing the
discarded pipeline output aside as `beats_inferred.json` and
`layer_a_harmonic.inferred.json` for comparison.

That takeover is gone. A consumer that, on a previous re-run of a song with a
Moises chord reference, saw `essentia/beats.json`'s `generated_from.engine`
read `"reference.moises.chords"` will now always see
`"essentia.RhythmExtractor2013"` — the pipeline's own beat tracker — and
`layer_a_harmonic.json`'s engine will always be the pipeline's own HPCP/chord
chain, never `"reference.moises.chords.promotion"`. No `beats_inferred.json` or
`layer_a_harmonic.inferred.json` file is written any more; the
`generate-timing-diagnosis` stage that diffed the two is deleted along with
them, and no `artifacts/validation/timing_diagnosis.json` is produced.

`phase_1_report.json`'s chord-validation note no longer calls
`reference/moises/*.json` an "authoritative human-validated comparison input."
It now states plainly that `reference/moises/*.json` is Moises.ai inference,
that only `lyrics.json` carries a confidence field and only its `"0.99"` rows
are operator-curated, and that chord validation measures agreement with a
second model, not correctness.

**Why:** `reference/` is validation-only (constitution §2 and §9) — a
generated artifact may never be substituted from it outside an explicit,
confidence-gated, provenance-recorded promotion, and this takeover had none of
that. It also made chord validation circular (the harmonic layer was rebuilt
from Moises, then validated against Moises), and it contradicted the measured
verdict that essentia's own beat tracker is at or above Moises everywhere
except one gold song. The reasoning was set out in
the v3.0 refinement doc, "Item 7 — stop substituting Moises inference for the
canonical grid" (recoverable from git history).

**Nothing else in this file's shape changed.** `beats.json` and
`layer_a_harmonic.json` keep their existing field shapes; only which engine
produces them, always, changed.

---

## 6. Delete symbolic note transcription

`data/analysis/<Song - Artist>/beats.json` rows lose their `bass` field:

**Before:**

```json
{ "time": 12.34, "beat": 1, "bar": 4, "bass": "D#", "chord": "D#m", "type": "downbeat" }
```

**After:**

```json
{ "time": 12.34, "beat": 1, "bar": 4, "chord": "D#m", "type": "downbeat" }
```

`time`, `type`, `bar`, `beat` and `chord` are unchanged; `chord` still comes
from `layer_a_harmonic.json`, not from the deleted symbolic layer.

`bass` was the beat-aligned note name nearest each beat, derived from Basic
Pitch's transcription of the bass stem
(`artifacts/symbolic_transcription/basic_pitch/bass.json`). Its only route to
the authoring model was `beats.json` itself — the field is not in the
projected `beats.json` contract in
[`docs/reference/analysis-input-guide.md`](reference/analysis-input-guide.md),
and per-beat symbolic features were never consumed downstream — so this is a
contract narrowing, not a replacement.

The symbolic note-transcription layer this fed from is gone entirely:
`artifacts/layer_b_symbolic.json`, `artifacts/symbolic_transcription/basic_pitch/`
(8 files), `artifacts/symbolic_transcription/validation.json` and
`artifacts/symbolic_transcription/hints.json` are no longer produced, and the
`symbolic_layer`, `symbolic_hints` and `symbolic_validation` rows are gone from
`info.json`'s `artifacts` block. `artifacts/symbolic_transcription/drum_events.json`
and `artifacts/symbolic_transcription/omnizart/drums.mid` are unaffected —
`drums.py` never depended on the symbolic layer and keeps its own Omnizart
transcription path.

`hints.json`'s inference categories narrow to `transition_role` only;
`section_shape`, `phrase_boundaries`, `motif_recall` and `variation_rule` (all
derived from the deleted symbolic layer) are gone. `transition_role` depended
only on section labels, not the symbolic layer, so it is unaffected. This is a
partial cut — plan item 11 rebuilds `hints.json` around the human hints — so no
new hint categories were added here.

**Why:** refinement §3, "Item 5 — delete symbolic note transcription." The
1,341-line `symbolic/` module's only route to the authoring model was the
templated `motif_recall` hint sentence (244 of 877 generated hints, all
identical), which item 11 deletes anyway; projected drum events come from
`drums.py`, which keeps its own Omnizart path and is unaffected.

---

## 7. Replace `sections/` with allin1 named segmentation

**The MCP server's `get_song_brief` `similar_sections` grouping — owned by the
separate `ai-dmx-light-render` repo, not this one — must move from
`section_character` equality to `function` + `same_label_as` grouping.** That
field no longer exists once this lands, so the current grouping code will
either error or silently stop grouping anything; it needs to read the new
fields instead. `same_label_as` means label repetition — "the third thing
allin1 called a chorus" — **not** acoustic identity ("the same music as the
first chorus"); grouping on it must not be described to an operator or a cue
author as identity.

Both `data/analysis/<Song - Artist>/sections.json` (the projected file) and
`artifacts/section_segmentation/sections.json` (the artifact it is built from)
change shape. The segmenter itself changes too: `stages/sections/`
(`segmenter.py`, `form.py`, `utils.py` — 1,403 lines of deterministic-DSP phrase
detection plus a 13-value invented `section_character` mood vocabulary) is
replaced by `stages/segmentation.py`, which runs All-In-One (Kim & Nam, ISMIR
2023) seeded with the pipeline's own stems and merges its 8-bar phrase
segments into song-form section runs. Full rationale, the merge strategy and
the measured numbers: [`../experiments/allin1/README.md`](../experiments/allin1/README.md),
and the v3.0 refinement doc's "Item 8 — `sections/` → allin1 named
segmentation" in git history.

**`artifacts/section_segmentation/sections.json` row fields:**

| field | change |
| --- | --- |
| `section_character` | **removed** — a 13-value invented vocabulary (`ambient_opening`, `vocal_spotlight`, `groove_plateau`, …) derived from a segmenter that measured 0.29 F1 against `reference/moises/segments.json`, worse than an evenly spaced grid at the same boundary budget |
| `form_role`, `form_role_confidence`, `form_role_margin` | **removed** — the same deterministic-DSP role classifier the boundaries came from |
| `energy_character`, `repetition_group`, `variant_of`, `similarity` | **removed** — `repetition_group` in particular was `null` on every section of all 21 shipped songs; nothing downstream ever read a real value out of it |
| `function` | **added** — the Harmonix functional label allin1 predicts: `intro`, `verse`, `chorus`, `bridge`, `inst`, `solo`, `break`, `outro` |
| `function_confidence` | **added** — `1 −` normalised Shannon entropy of allin1's frame-level label posterior across the section's own time span |
| `function_status` | **added** — `"known"` or `"unknown"`; `"unknown"` on every row of a song where allin1 gives fewer than 3 distinct labels or one label covers more than 90% of the track (the model is outside the distribution it can reliably name — see the module docstring in `stages/segmentation.py`). The boundary stays as measured; only the name is untrusted |
| `same_label_as` | **added** — the `section_id` of the first section carrying this same `function` label, or `null` for a first occurrence. **Label repetition, not acoustic identity** |
| `section_id`, `start`, `end`, `confidence` | unchanged in name and meaning; `section_id` remains the join key to the projected `sections.json` |

**Before** (`artifacts/section_segmentation/sections.json` row):

```json
{
  "section_id": "section-003",
  "start": 64.0,
  "end": 96.0,
  "label": "chorus",
  "section_character": "focal_lift",
  "confidence": 0.62,
  "form_role": "chorus",
  "form_role_confidence": 0.71,
  "form_role_margin": 0.18,
  "energy_character": "focal_lift",
  "repetition_group": null,
  "variant_of": null,
  "similarity": null
}
```

**After:**

```json
{
  "section_id": "section-003",
  "start": 64.0,
  "end": 96.0,
  "function": "chorus",
  "function_confidence": 0.81,
  "function_status": "known",
  "same_label_as": null,
  "confidence": 0.81
}
```

**Top-level `data/analysis/<Song - Artist>/sections.json` row fields:** the
`form_role`, `energy_character` and `repetition_group` passthrough fields and
the `hints` array are gone from this row shape; `label` and `description` are
now generated from `function` and the section's own measured shape instead of
the deleted `SECTION_DESCRIPTIONS` 13-value lookup table.

**Before:**

```json
{
  "section_id": "section-003",
  "start": 64.0,
  "end": 96.0,
  "label": "3 Focal Lift (0.62)",
  "form_role": "chorus",
  "energy_character": "focal_lift",
  "repetition_group": null,
  "confidence": 0.62,
  "description": "Payoff section where energy, repetition, or phrasing converge into the strongest focal state.",
  "hints": []
}
```

**After:**

```json
{
  "section_id": "section-003",
  "start": 64.0,
  "end": 96.0,
  "label": "003 Chorus (0.81)",
  "description": "The 2nd chorus, 32.0s long, same label as the first chorus.",
  "confidence": 0.81
}
```

A song where allin1's labelling is degenerate (`function_status: "unknown"`)
shows the raw label token with an explicit marker instead of a polished,
confident-looking name, e.g. `"003 inst [unverified] (0.24)"` — never a
plausible-sounding name coined for a label the pipeline has already flagged
untrustworthy.

**Why:** refinement §5, "Item 8 — `sections/` → allin1 named segmentation."
Measured against `reference/moises/segments.json` across the four gold songs,
the merged allin1 section runs land 0.53 recall / 0.91 precision / 0.67 F1 at
±1.0s, against the old segmenter's 0.32 / 0.27 / 0.29 — worse than an evenly
spaced grid at the same boundary budget. `section_character` and
`repetition_group` carried no ground truth and, in `repetition_group`'s case,
no real value on any shipped song; `function` is the named part constitution
§1.2 asks the structural read to carry.

---

## 8. Downbeat phase from allin1, with per-downbeat confidence

**Bar numbers change on most songs.** This is the line a downstream consumer
most needs to see: `beats.json`'s `bar` field is no longer
`((index - 1) // 4) + 1` counted off array position — it now counts off
*measured* downbeats, so any consumer caching or diffing against a
previously-generated `beats.json` should expect the whole bar grid to shift,
not just gain a field. `time` and `beat` (`beat_in_bar`) values for beats that
were already correctly phased are unaffected; only which beat of every four is
called `"downbeat"`, and therefore how bars are numbered, can move.

**Before** (`beats.json` row):

```json
{ "time": 12.34, "beat": 1, "bar": 4, "chord": "D#m", "type": "downbeat" }
```

**After:**

```json
{ "time": 12.34, "beat": 1, "bar": 4, "chord": "D#m", "type": "downbeat", "confidence": 0.81 }
```

`confidence` is new on every row. It is `null` on `type: "beat"` rows always.
On a `type: "downbeat"` row it is allin1's downbeat-activation strength
(`[0, 1]`) at that beat time, **except** where essentia's beat grid and
allin1's downbeat activation disagree by a whole beat or more for that bar —
there it is `null` too, rather than a number that would look as trustworthy as
a real measurement.

**Unknown-span encoding decision:** a per-downbeat `confidence: null` was
chosen over a separate `bar_phase_confidence` header block in `beats.json` —
the smallest honest encoding; it reuses the field this item already adds
instead of introducing a second, header-level marker for the same fact.
`validate_beats`'s downbeat F1 scoring excludes `confidence: null` rows from
the predicted set entirely — an abstention is not a claim, so it is scored
only as a potential recall miss on the reference side, never as a right-or-
wrong prediction. Scoring an honest "we don't know" as if it were a confident
guess would let a correct-but-unmarked-unknown inflate precision and a
wrong-but-unmarked-unknown deflate it, for a row that never claimed to be
right either way.

**Why:** refinement §5, "Item 9 — downbeat phase from allin1, with honest
confidence." The old `beat_in_bar` assignment was pure modulo — there was no
downbeat *detection* in this pipeline at all — and measured 0.16 F1 @±70 ms
against 385 Moises-labelled downbeats across the four gold songs, with only 1
of 4 songs landing a correct phase. Taking the phase (never the beat times)
from allin1's own `downbeat` frame activation — already computed once per song
by the `segment-sections` stage (item 7) and read here from the shared
`analyzer.allin1_cache`, never re-run — reaches **0.226 combined F1** measured
against this implementation, not the 0.59 the refinement doc projected from an
earlier exploratory measurement. A single song-wide phase offset (a magnitude
sum across the whole song) was tried first and scored worse than the shipped
modulo baseline on more than one gold song — a region of generally elevated
activation out-voted the region that actually peaks at the true downbeat — so
the phase is instead chosen by a majority vote of local arg-maxes inside
16-bar windows, letting it drift or reset across a song rather than committing
to one global answer (`stages/timing.py` module docstring has the full
algorithm).

Two of the four gold songs individually clear the 0.50 target —
`_test_song` (0.604) and `Armin - Revolution` (0.593). The other two are
capped by problems this item does not touch, not by the phase algorithm or a
scoring bug — both were verified by direct inspection, not assumed:
`Titanium - David Guetta ft Sia` scores 0 (0 true positives) because allin1's
own downbeat activation confidently disagrees with the reference phase. Its
beat grid was confirmed correctly aligned to the reference first (each
essentia beat lands within ~10 ms of the corresponding Moises beat, so this is
not a beat-time or frame-indexing bug); sampling allin1's `downbeat` activation
at those same times shows it consistently peaking (0.24–0.47) at the position
the reference calls beat 3 and sitting near zero (~0.001–0.02) at the true
downbeat, beat 1 — a reproducible ~two-beat disagreement, matching refinement
§4's independent note that three trackers give three different phases on this
song ("allin1 +1.96" beats off). `Hideaway - Kiesza` scores 0.050 because
essentia's own beat *tracking* — unchanged by this item — finds a different
underlying tempo than the reference on that song (~0.66 s intervals against
the reference's ~0.48 s), the one gold song where essentia's beat tracker
under-performs Moises's (`CLAUDE.md`, "Trusted"). No downbeat-phase choice on
top of a wrong-tempo grid can land within ±70 ms. Beat *times* are unaffected
everywhere: essentia's tracker remains the trusted one (7/7 human-marked drop
impacts land within 0.25 s of an essentia beat), and allin1's own beat grid
sits a clean half-beat off essentia's on 4 of 21 corpus songs and halves the
tempo on a 5th, so it is never used.

**Ordering note.** `extract-timing-grid` (1.2) now runs allin1 (via the shared
cache) before `segment-sections` (3.1) does, reversing which of the two stages
first pays the model's runtime cost — `extract-timing-grid` already runs after
`ensure-stems` in `run_phase_1`, so seeded stems are available in time. Both
stages' own outputs are otherwise unaffected; see
the v3.0 plan's item 8 (in git history) for the full resolution note.

## 9. Replace the `event_*` stack with the gestures stage

**`song_event_timeline.json` is a different shape.** The whole Epic-5
`event_*` chain (`event_rules/`, `event_machine/`, `event_features/`,
`event_timeline.py`, `event_review.py`, `event_identifiers.py`,
`review_queue.py`, `event_contracts.py`, `_stem_activity.py`) is deleted —
measured at chance against the gold set (CLAUDE.md) — and replaced by one
phase-3 stage, `src/analyzer/stages/gestures.py`, ported from
`experiments/gestures/primitives.py` + `assembly.py`. It reads only trusted
phase-1/2 artifacts (`fft_bands.json`, `rms_loudness.json`, `drum_events.json`,
the canonical timing grid, `section_segmentation/sections.json`) and never
opens the audio (constitution §5.2).

**Removed event types.** The entire Epic-5 vocabulary is gone: `drop`,
`drop_explode`, `drop_groove`, `drop_punch`, `soft_release`,
`no_drop_plateau`, `fake_drop`, `tension_hold`, `pause_break`, `anthem_call`,
`call_response`, `hook_phrase`, `vocal_spotlight`, `vocal_tail`,
`energy_reset`, `layer_add`, `layer_remove`, `impact_hit`, `stinger`,
`groove_loop`, `atmospheric_plateau`, `percussion_break`, `instrumental_bed`,
`heartbeat_pattern`, `four_on_the_floor` — along with the composite-row shape
(`composite`, `phases[]`, `member_event_ids`, `evidence_ref`, `lighting_hint`,
`created_by`) and `texture_summary[]`.

**New phase vocabulary.** Every event is now a **flat** row — `type`,
`start_time`, `end_time`, `confidence`, `intensity`, `section_id`,
`section_name`, `provenance`, `summary`, `evidence_summary` — and `type` is
one of two shapes:

1. A gesture phase: `approach`, `build`, `tension`, `impact`, `release`.
   Anchored on a detected impact (simultaneous sub-band + transient spike);
   the other phases are filled from whichever named sound-design primitive
   (riser, downlifter, reverse cymbal, snare roll, pre-drop gap) falls in the
   preceding window. **A phase absent for a gesture means no supporting
   primitive was found — never guessed** (constitution §2).
2. A section-pair transition, `"<from_label> → <to_label>"` — one per
   boundary already present in `section_segmentation/sections.json` (that
   stage already merges consecutive equal-labelled runs, so every remaining
   boundary is already a change in `function`). The transition carries that
   boundary's own `confidence` unchanged; this stage adds no independent
   opinion about whether the boundary is real.

**A drop is never named directly.** Constitution §5.2 — the vocabulary can
only say "a build of this shape happens here," never "this is the drop."

**Removed file set.** `artifacts/event_inference/` (`features.json`,
`timeline_index.json`, `rule_candidates.json`, `events.machine.json`),
`artifacts/energy_summary/hints.json`, `artifacts/validation/song_events.review.json`
(+ `.md`), `artifacts/validation/song_events.overrides.json`, and
`artifacts/validation/review_queue.json` are no longer produced.
`song_event_timeline.md` is also no longer produced (the old export stage
wrote it; the new stage does not). `info.json`'s `artifacts` block drops the
corresponding rows (`event_features`, `event_timeline_index`,
`event_rule_candidates`, `event_machine`, `event_review`, `event_overrides`,
`event_timeline_markdown`, `review_queue`, `energy_identifiers`).

**Contracts.** `src/analyzer/contracts/event_vocabulary.json` and
`song_event_schema.json` are rewritten to the phase/transition vocabulary
above; `event_threshold_profiles.json` and `contracts/song_event_timeline.json`
(the example-payload contract file, not the generated per-song deliverable of
the same base name) are deleted. Nothing in `src/` loads these contract files
at runtime any more — `event_contracts.py`, their only reader, is deleted with
the rest of the stack — so they now serve as documentation only.

**Validation.** `validation/events.py`'s `_validate_event_outputs` check is
retired to `skipped_result()` in `build_validation_report` — its inputs
(`event_inference/*`, `song_events.review.json`, `song_events.overrides.json`)
no longer exist. Cutting the validation surface down properly to what the
gestures stage actually produces is plan item 10's job, not this one's.

**Acceptance metric.** Impact-phase recall of the 7 hand-marked drop impacts
across the four gold songs: **4/7 @ ±1.0 s, 2/7 @ ±0.25 s** (3 hits from
`Titanium - David Guetta ft Sia`, 1 from `Hideaway - Kiesza`, at ±1.0 s;
1 of each at ±0.25 s), against the incumbent `event_*` stack's measured
**2/7 @ ±1.0 s, 0/7 @ ±0.25 s** (`experiments/drop_detection/README.md`).
`events/min` (all event types combined) is 9.5-18.6/min across the four gold
songs, under the 20/min input-guide ceiling.

**UI.** The **Machine Events** and **Identifier Hints** debugger lanes are
removed. The existing **Gestures** lane (previously an `experiments/gestures`
sandbox lane reading `reference/proposals/gestures.json`) is promoted: its
`experiment` tag is removed and it now reads the production
`song_event_timeline.json` deliverable directly.

---

## 10. Cut validation to what has labels

**`--compare` supports five targets, not eight.** `beats`, `chords`,
`sections`, `drums`, `drops`. `energy`, `events`, `form`, `patterns` and
`unified` are gone from `--compare`'s accepted values and from the default
(`beats,chords,drums,sections,drops`); passing any of the removed names now
fails CLI argument validation instead of silently returning `skipped`.
`validation/events.py` and `validation/energy.py` are deleted outright —
`validation/patterns.py` and `validation/unified.py` were already deleted in
items 4 and 3. Neither had a real subject left: `events.py` validated the
Epic-5 `event_*` outputs item 9 deleted, and `energy.py`'s internal-consistency
check was never a musical claim.

**The `form` target is deleted, not just skipped.** It scored section
boundaries, `form_role` and `form_family` against
`reference/human/human_hints.json` boundary labels, but those labels never
landed: `mode: "unlabelled"`, `labelled_boundary_count: 0` on all four gold
songs. `validate-sections` against `reference/moises/segments.json` covers the
same ground with 38 real labelled interior boundaries across the same four
songs — 5× the evidence the `form` target ever had. `score_form`,
`labelled_boundaries`, `confidence_calibration`, `validate_form` and
`load_song_facts`'s `form_family` reader are deleted with it, along with
`artifacts/validation/form_score.json`.

**The `drops` target survives, timed-only.** It still scores detected drops
in `song_event_timeline.json` against timed drop hints in
`reference/human/human_hints.json` (precision/recall at a 1.0 s tolerance,
plus the "fake drops don't outnumber real drops" symmetry check). What it lost
is the `presence` fallback: when a song had no timed drop hints but did have a
song-level `has_drop` fact, the old code reported `presence_ok` — true whenever
the detector fired at least once on a `has_drop: true` song, regardless of
*when*. That passes by construction and asserted nothing about timing, so it
is gone. A song with no timed drop hints (three of the four gold songs today)
now reports `skipped` with `diagnostics.reason: "no timed human drop hints"`,
same as a song with no reference file at all — never a check that cannot fail.
The module is renamed `validation/drops.py` (was `form_drops.py`), and
`_write_score_artifact` no longer writes `form_score.json`, only
`drops_score.json`.

**`validate-chords` no longer crashes on a real Moises chord reference.** The
bug (`docs/issues.md`, closed in this change): `chords.py` read `row["bar_num"]`
and `row["beat_num"]` from `reference/moises/chords.json` rows, which carry
neither field — the real schema is `curr_beat_time`, `curr_beat`,
`prev_chord`, `chord_complex_jazz`, `chord_simple_jazz`, `chord_complex_pop`,
`chord_simple_pop` — raising `KeyError: 'bar_num'` on every one of Titanium's
487 rows. `_validate_chords` (and the public `validate_chords`) now take the
pipeline's own `essentia/beats.json` timing grid as an added parameter and
derive each reference row's `bar` / `beat` by snapping `curr_beat_time` to the
nearest beat in that grid (`bar`, `beat_in_bar`), the same nearest-beat
convention `stages/drums.py::_nearest_beat_alignment` already uses. When the
nearest beat is more than 0.2 s away — or the grid is empty — the position is
reported as `None`/`None`, never a guessed `bar: 0` (constitution §2); nothing
in the actual chord-matching logic depends on this field, since chords are
matched by time overlap, so an unknown position only affects the diagnostic
`bar`/`beat` recorded on each reference event, not the pass/fail outcome.

**`report.py`'s `generated_artifacts` block is unchanged** — `energy_layer_file`
and `event_timeline_file` are still generated artifacts (by `energy.py` and
`gestures.py` respectively) and still listed there; only the `validation`
block's target set shrank. `ADVISORY_TARGETS` (advisory scores that never flip
the pipeline exit code under `--fail-on-mismatch`) is now `{"drops"}`, was
`{"form", "drops"}`.

**Contracts.** None of the projected deliverables change shape —
`validation/` is not projected to the authoring model (§7 of CLAUDE.md's "what
actually reaches the light show" list omits it entirely). This item only
changes `phase_1_report.json`'s own shape (five `validation` keys instead of
eight) and the `--compare`/CLI surface.

---

## 11. Rebuild `hints.json` around the human hints

**`hints.json` now merges in `source: "human"` hints.** Each entry in
`reference/human/human_hints.json` is matched to a section via the same
window→section overlap logic `hint_alignment.py` already used for
`human_hints_alignment.json` — now extracted into a single public function,
`find_primary_section`, that both call. A human hint with no overlapping
section lands under a synthetic `section_id: "unsectioned"` section rather
than being dropped.

**The one surviving inference category is renamed.** `transition_role` (the
only inference category item 6 left standing) is now `transition` — one of
the six allowed tags (`strobe`, `movement`, `intensity`, `transition`,
`color`, `phrase_boundary`). No further categories were cut in this item;
`transition`/`transition_role` already named a moment and an intent and
passed this item's own bar.

**`summary.user_hint_count` now counts `source: "user"` or `source: "human"`
hints** — was `source: "user"` only, which meant it read `0` on every song
because no code path ever wrote a human hint into `hints.json`. It is now
`> 0` on every song carrying `reference/human/human_hints.json` (four of the
21 gold-set songs today). No new `human_hint_count` key was added;
`user_hint_count` broadens to mean "not machine-generated."

**New per-hint fields, human hints only:** `title` (always present, verbatim
from the source), `lighting_hint` (verbatim, only when the operator supplied
a non-empty one), `start_time` / `end_time` (verbatim, rounded to the same
6-digit precision as section boundaries elsewhere in this file). `category`
is **absent**, not `null`, on every human hint — a drop impact and a calm
vocal passage ("Breath") cannot both honestly take one of the six inference
tags, and constitution §2 forbids inventing a plausible one.

**`text`** for a human hint is its `summary`, verbatim, falling back to
`title` when `summary` is empty; the hint is dropped only when both are
empty. Note this is a stricter drop condition than the old
"empty `lighting_hint` / `text`" language in the input guide — a human hint
is never dropped for having no `lighting_hint`, nor for landing outside every
detected section.

**Why:** v3.0 plan item 11. The human hints in
`reference/human/human_hints.json` are timed, specific and hand-authored —
exactly the signal `hints.json` exists to carry to the authoring model — but
no code path ever merged them in, so `user_hint_count` measured `0` on all 21
songs. This closes that gap without inventing a category the source data
doesn't honestly support.

---

## 13. `harmonic.py` — project a compact form

**Top-level `sections.json` gains two fields: `key` and `chord_progression`.**
Both are derived purely from `artifacts/layer_a_harmonic.json`, which
`harmonic.py` already computed and which previously reached no projected
file at all — `validate-chords`, the debugger's chord lane and the per-beat
`chord` field in `beats.json` were its only consumers, and the input guide
already states per-beat features are not consumed. No new model, no new
dependency, no change to chord detection itself.

`key` is the whole-song key label from essentia's HPCP estimate
(`global_key.label`, e.g. `"C# major"`), gated on `global_key.confidence`
against a floor of **0.70**. It is one value for the whole song — every
section row carries the same string, or the same `null`. `chord_progression`
is a section's dominant repeating chord sequence, e.g. `"Am–F–C–G"`: every
essentia chord event overlapping the section's `[start, end)` window is
collected, and if every one of them clears a per-event confidence floor of
**0.70**, the distinct-consecutive chord labels are reduced to their shortest
clean repeating cycle (falling back to the first 8 distinct chords when no
clean cycle exists) and joined with an en dash. If a section has no
overlapping chord events, or even one of them falls below the floor, the
whole progression is `null` — a weakest-link gate, not an average, because a
single unreliable chord inside an otherwise-clean run makes the whole stated
sequence untrustworthy.

**The two fields are gated independently and on different scales.** Whole-song
`global_key.confidence` and per-song *mean* chord-event confidence both
cluster tightly (0.75–0.85 and 0.73–0.80 respectively) across all four gold
songs regardless of how well those songs' chords actually agree with an
independent reference — so neither a key-confidence threshold nor a
per-song-mean chord threshold would produce a sensible split. What does
separate them is the *minimum* per-chord-event confidence within a song:
Hideaway dips to 0.459, Armin to 0.531, while `_test_song`'s minimum is 0.850
and Titanium's (0.685) sits in between. 0.70 was chosen as the per-chord-event
floor because it sits in that gap. `key`'s 0.70 floor is real (it would null
out a genuinely weak future estimate) but is not tied to the per-chord floor:
a global key estimate is a single, more robust measurement aggregated over
the whole track, not a per-beat label, so a section's shaky local chords do
not automatically make the song's key claim unsupported.

**Measured, and stated here because it is unflattering:** exact root+quality
chord agreement against Moises is **1.00** on `_test_song`, **0.69** on
`Titanium - David Guetta ft Sia`, **0.51** on `Armin - Revolution`, and
**0.38** on `Hideaway - Kiesza`. Two independent chord estimates disagreeing
on that much of a track does not say which one is wrong, but it does say the
labels are not settled, and the 0.70 per-event floor is what keeps that
uncertainty from reaching the authoring model as false confidence. Verified
on the four gold songs after landing: `chord_progression` is non-null on
100% of `_test_song`'s sections, ~50% of Titanium's, and a meaningfully lower
share of Armin's and Hideaway's (both well under `_test_song`'s rate) — the
null-rate ordering tracks the measured agreement ordering. `key` is non-null
on all four gold songs (their `global_key.confidence` values, 0.749–0.851,
all clear the 0.70 floor); the floor exists to null out a future song whose
key estimate is weaker, not to discriminate among these four.

**Why:** v3.0 plan item 13, decided in refinement
§6 item 13: keep `harmonic.py` and project a compact form rather than delete
chord computation outright. Harmonic context is exactly the kind of fact a
cue author needs to justify a colour choice, and an honest `null` where
agreement is weak is worth more than a confident chord label the reference
data contradicts on over 40% of a song (constitution §2).

---

## 14. Consolidate the debugger lanes

**No analyzer output changes.** This item only touches `ui/` — the debugger's
lane registry — not `src/analyzer` or any projected file.

**UI.** The **allin1 Sections** and **allin1 Transitions** experiment lanes are
removed from the debugger entirely (constitution §3.2: a lane comes out of the
registry once its experiment is promoted). Their content already lives
elsewhere: the functional labels are the production **Sections** lane from
item 7, and the section-change events are the transition rows in
`song_event_timeline.json` from item 9. `artifactPaths.allin1` and its parser
are removed along with them, so the debugger no longer reads
`reference/proposals/allin1.json` at all.

The **Gestures** lane now reads the production `song_event_timeline.json`
deliverable and is no longer marked as an experiment — it lost its
`experiment` tag and flask badge when item 9 promoted the gestures stage;
`artifactPaths.gestures` (the old `reference/proposals/gestures.json` path) is
removed as dead weight in this change.

**Left untouched.** `Drop Proposals`, `Vocal Phrases`, `Reactive Bands`,
`Phrase Grid`, `Character`, `Vocal Transcription` and `Moises Lyrics` all keep
their experiment badges and artifact paths — none of those experiments are
promoted by this release.

**Why:** v3.0 plan item 14. Once an experiment's
output is promoted into a production deliverable, keeping its old debugger
lane around invites the two to drift apart and confuses which one the
authoring model actually receives (constitution §3.2).

---

## 15. Documentation sweep and experiment archival

No consumer-facing artifact changes in this item — it is the documentation
catch-up for items 1-14. Two things worth a downstream consumer's attention
anyway:

### New files

| File | Introduced by | What it is |
| --- | --- | --- |
| `artifacts/allin1/raw.json` | item 8 (`analyzer.allin1_cache`) | allin1's raw segment list plus its `downbeat` and `label` frame activations at 100 Hz, cached once per song so `extract-timing-grid` (1.2) and `segment-sections` (3.1) share one model invocation instead of each running it. **Not a stable contract file** — internal to the shared cache module; no other stage and no UI lane reads it. |

No other new top-level or `artifacts/` file was introduced across items 1-14;
every other change in this document either removes a file, reshapes an
existing one in place, or changes which engine produces an unchanged shape.

### Unchanged for v3.0

Four files a consumer might reasonably expect to have moved, given how much of
the pipeline underneath them changed, and did not:

- **`info.json`** — same top-level shape (`bpm`, `duration`, `artifacts`,
  `outputs`) throughout the release. Its `artifacts` block lost rows as items
  1-9 deleted their producing stages (`events.ml.json`, `event_benchmark`,
  `music_feature_layers`, `patterns_layer`/`pattern_mining`,
  `symbolic_layer`/`symbolic_hints`/`symbolic_validation`, the eight
  `event_*`/`review_queue`/`energy_identifiers` rows, `energy_features`), but
  the file's own schema and the meaning of every surviving key are unchanged.
- **`artifacts/genre.json`** — untouched by every item in this release.
  `genre.py` was never a deletion, replacement, or publishing target this
  wave; it keeps its `genres`, `confidence`, `top_predictions[]`, `guidance[]`
  shape from v2.1.
- **`artifacts/essentia/rms_loudness.json`** — untouched. `loudness.py` was
  not in scope for any item 1-14; the one MCP `get_analysis_detail` dense
  artifact keeps its `metadata.interval_ms` / `sources[]` / `frames[]` shape.
- **`artifacts/symbolic_transcription/drum_events.json`** — untouched, and
  deliberately survived the item-6 deletion of the rest of the
  `symbolic_transcription/` tree: `drums.py` never depended on Basic Pitch or
  the deleted `symbolic/` package, and keeps its own Omnizart transcription
  path with the same `events[] {time, event_type, confidence}` shape plus
  summary counts.

**Why call these out:** items 1-14 together touched `sections.json`,
`beats.json`, `hints.json` and `song_event_timeline.json` — four of the seven
files a consumer reads — which is most of the projected surface. A consumer
diffing this release against v2.1 should not have to independently verify that
the other three kept their shape; this section is that verification, done
once, here.
