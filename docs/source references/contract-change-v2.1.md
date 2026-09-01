# Contract-change note — analyzer v2.1 → MCP server

The MCP server is **not modified in v2.1**. This note lists exactly what changed
in the top-level files it projects, for the MCP side to absorb. Compatibility
was not a constraint on the change; documenting it is.

## `artifacts/section_segmentation/sections.json`

`schema_version` → `"1.1"`; `generated_from.engine` →
`deterministic.section_segmentation.v3`.

| Change | Detail |
| --- | --- |
| **New song-level `form_family`** | Object `{ value, confidence, provenance, evidence }`. `value ∈ {dance_form, song_form, hybrid, unknown}`. Derived from audio evidence only — the inferred genre label is not an input. `provenance` is `"inferred"` or `"human-confirmed"`. |
| **New per-section `form_role`** | Primary musical-function label from `{intro, verse, pre_chorus, chorus, hook, bridge, breakdown, build, drop, post_drop, instrumental, outro, unknown}`, gated to the subset admissible for the song's `form_family`. `unknown` is a first-class, expected value. Accompanied by `form_role_confidence` and `form_role_margin`. |
| **Top-level `label` rebuilt from `form_role`** | It is no longer the energy-shape string. |
| **`energy_character`** | The former 13-value energy-shape vocabulary, retained as secondary metadata. `section_character` kept as its alias. |
| **New `repetition_group` / `variant_of` / `similarity`** | Repetition identity from combined harmonic+timbral self-similarity. `repetition_group` is `"A"`/`"B"`/… ; `variant_of` is the first occurrence's `section_id` (or `null`); `similarity` is the measured cosine. **Sections sharing a `repetition_group` — not `energy_character` equality — are the correct reusable-look pairing input.** The MCP `similar_sections` grouping should switch to this. |
| **New per-section `confidence_terms`** | Inspectable breakdown behind `confidence`. |
| **`confidence` semantics changed (B1)** | Now measures boundary + label certainty only (novelty sharpness, detector agreement, transient/bar-grid alignment, `form_role` margin). Loudness / repetition count / onset level are no longer terms. Values span the full `[0, 1]` range — a low value means "don't spend tokens corroborating", as intended. |

## Top-level `sections.json` (the UI projection, `<song>/sections.json`)

| Change | Detail |
| --- | --- |
| **New `section_id` on every row (B5)** | Join the top-level list to the segmentation list **on `section_id`**, not on array position. `build_ui_data` now fails loudly on a missing/duplicate id. |
| **New `form_role`, `energy_character`, `repetition_group`, numeric `confidence`** | Projected through so the consumer need not re-read the segmentation artifact. |

## `song_event_timeline.json`

`schema_version` → `"1.1"`; `generated_from.engine` →
`llm-friendly-event-timeline-v2`.

| Change | Detail |
| --- | --- |
| **Composite events (R5)** | A `build → drop → post_drop` run is **one** row with `composite: true`, an overall `start_time`/`end_time`/`confidence`/`intensity`, `member_event_ids[]`, and an ordered `phases[]` — each `{phase, start_time, end_time, intensity}`, `phase ∈ {approach, build, tension, impact, release, recovery}`. Phase members are **not** separate rows. A build with no resolving drop is a composite with no `impact`/`release` phase. |
| **`layer_add` / `layer_remove` removed (R6)** | No longer timeline events. Arrangement change is in the new `texture_summary[]` — per section: `{ section_id, start_time, stem_activity, stems_entering, stems_leaving }`. |
| **`intensity` is now absolute (B4)** | A fixed `[floor, ceiling]` band per event type; the raw signal only positions the event within its band. Read it as a cross-song magnitude, not a per-song normalisation. It no longer piles at `1.0`. |
| **`summary`** | Now the evidence summary (describes the musical moment) rather than the rule note. |

## New files

| File | Producer | Purpose |
| --- | --- | --- |
| `artifacts/validation/review_queue.json` | pipeline stage 5.1 | Ranked open questions the run could not settle (field, candidates+scores, evidence timestamps, reason). Includes the `form_family` / genre disagreement flag. |
| `reference/human/song_facts.json` | the debugger UI on explicit human save only | Song-level human-confirmed facts (`genre`, `form_family`, `has_drop`). Sibling of `human_hints.json`, not part of it. The analyzer never writes it. |
| `artifacts/validation/form_score.json`, `drops_score.json` | `--compare form,drops` | Advisory structural scores against `reference/human/` labels. |

## Unchanged for v2.1

`beatdrop_visual_plan.json` still reads the **flattened** event view (it is built
from sections/energy/fft, not the timeline). Moving it to composites is v2.2. The
strict internal `song_event_schema.json` for `rule_candidates.json` /
`events.machine.json` stays at `schema_version` `"1.0"` with flat member events.
