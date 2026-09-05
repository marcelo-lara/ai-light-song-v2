# Contract change — v2.1 → v3.0

This is the downstream handoff note for the v3.0 release
([`implementation-plan-v3.0.md`](implementation-plan-v3.0.md), executing
[`product-refinement-v3.0.md`](product-refinement-v3.0.md)). Compatibility with
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
except one gold song. Full reasoning in
[`product-refinement-v3.0.md`](product-refinement-v3.0.md) §4, "Item 7 — stop
substituting Moises inference for the canonical grid."

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
the measured numbers: [`product-refinement-v3.0.md`](product-refinement-v3.0.md)
§5, "Item 8 — `sections/` → allin1 named segmentation."

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
