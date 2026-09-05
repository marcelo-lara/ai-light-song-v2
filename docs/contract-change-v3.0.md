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
