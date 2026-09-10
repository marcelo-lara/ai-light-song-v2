# Contract changes — v3.4 delivery surface

TLDR for the downstream cue-authoring consumer (`ai-dmx-light-render`). Format
matches the archived `contract-change-v3.1.md`. **One change reaches the
delivery surface in v3.4. Nothing else does** — the per-stem FFT bands, the
drum `crash` split's artifacts, and the three experiment lanes all stay in
`artifacts/` / `experiments/`, unpublished (refinement doc, "What this release
does not do").

## What changed, shortest form

- **`sections.json` `function_status` gains a third value: `"contested"`**
  (beside `"known"` / `"unknown"`). A consumer that treats `function_status` as
  a two-value field **must add the third** — else a contested row reads as an
  unrecognised status.
- A `function_status: "contested"` row also carries **`contested_by: "energy"`**
  (a new key, present only on contested rows). Absent on every other row.
- `function` and `function_confidence` are **unchanged** on a contested row —
  allin1's label is *kept*, only flagged. The row is not dropped, not relabelled.
- `drum_events.json` `event_type` gains `"crash"` — a brilliance-gated split of
  pitch-42 `hat` events. `supported_event_types` lists it. (Shipped by v3.4
  item 2; listed here for completeness — a consumer that switches on
  `event_type` should handle `crash` as a distinct, brighter cue than `hat`.)

## `function_status: "contested"` — meaning

A phase-3 stage (`contest-section-function`) cross-checks each allin1 `function`
against the published `loudness.json` + `arrangement_state.json`. Where a
`chorus` is quieter and thinner than the `verse` / `bridge` that follows it, the
label is **kept and flagged**, not flipped (refinement `D5`: flipping asserts a
fresh claim from a thin heuristic; a confident wrong answer costs the show).

```json
{ "section_id": "section-002", "function": "chorus", "function_confidence": 0.544,
  "function_status": "contested", "contested_by": "energy",
  "confidence": 0.544, "key": "...", "chord_progression": "..." }
```

**Consumer action:** on a `contested` row, do not light the section from its
`function` label alone — its measured energy contradicts the label. Treat it
like `unknown` for pacing purposes (fall back to `loudness.json` /
`arrangement_state.json`), but note the label may still be structurally correct.

Measured (`experiments/section_function_contest/measurement.md`): the contest
flags **4 sections across 2 of 23 songs** — it is deliberately conservative,
concentrated on Eurovision-shaped songs. On a normal song `sections.json` is
byte-identical to v3.3.

## `field_sources`

`sections.json`'s `field_sources` header adds a `contested_by` entry and sets
`function_status` to `section_function` **only on a song that has a contested
row**; on every other song the header is byte-identical to v3.3
(`function_status: "allin1"`, no `contested_by`). The producer vocabulary gains
`section_function`.
