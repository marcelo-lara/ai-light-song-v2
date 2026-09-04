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
