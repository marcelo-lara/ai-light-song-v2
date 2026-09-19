# Reference — how `sections.json` picks its boundaries and labels

`sections.json`'s `start`, `end`, `label`, `description`, `function` and
`confidence` fields are fused from up to three producers, in strict
precedence order. Built by `_build_reference_override_rows` and
`build_ui_data` in [`../../src/analyzer/stages/ui_data.py`](../../src/analyzer/stages/ui_data.py).

## Precedence

| Order | Source | Confidence | Why |
| --- | --- | --- | --- |
| 1 | `reference/human/segments.json`, if it exists for the song | floor `0.8` | Human mistakes are plausible, but a human annotator is still the best available truth |
| 2 | `reference/moises/segments.json`, if it exists and no human file does | floor `0.6` | Moises.ai is also an inferred discriminator, one tier below a human |
| 3 | our own segmentation (`section_segmentation/sections.json`, allin1) | `section.confidence` as measured | See [`segmentation.py`](../../src/analyzer/stages/segmentation.py)'s docstring for the boundary F1 numbers (0.67 merged / 0.29 old segmenter) |

**Whole-song override, never per-boundary.** If tier 1 or 2's file exists for
a song, *every* row's `start`/`end`/`label`/`description`/`confidence` comes
from that one file — there is no merging of spans across tiers within a song.
A song with a human file uses it for 100% of its sections even where moises
or allin1 might have drawn a boundary the human file didn't. Do not propose
per-gap or per-boundary merging as an enhancement — it was considered and
rejected in favor of a stable, honest single producer per song.

`function_confidence`, `function_status` and `same_label_as` are **never**
overridden by tiers 1 or 2 — they always come from allin1, inherited from
whichever allin1 section overlaps the winning span most (by time overlap;
no overlap is an honest `null`/`"unknown"`, never invented). `key` always
comes from the harmonic stage regardless of tier.

## Confidence ladder — boundary corroboration

**Status: specified, not implemented.** `confidence` today is the flat tier
constant (0.8 / 0.6) or allin1's own `section.confidence`. This section
defines what it is to become.

The tier constants above are **floors**, not fixed values. A row's
`confidence` is raised when a producer *other than the winning tier*
independently places a section boundary at the same time.

### What is compared

Compare **boundary times only** — never labels, never whole rows.

- Build each producer's boundary set: every section `start`, plus the last
  section's `end`.
- Two boundaries corroborate when they fall within **one beat** at the song's
  BPM (from `beats.json`), floored at 0.25 s. Not a fixed constant: on
  *Titanium* a fixed 0.5 s found 0 of 15 corroborated rows while 1.0 s found 4,
  a systematic producer offset rather than real disagreement.
- A row has two edges. Its confidence uses the **weaker** of the two.

### The ladder

| Edge corroborated by | confidence |
| --- | --- |
| human + allin1 | 0.95 |
| human only | 0.8 (the floor, unchanged) |
| moises + allin1 | 0.75 |
| moises only | 0.6 (the floor, unchanged) |
| allin1 only | `section.confidence` as measured |

**Corroboration only ever raises; disagreement never lowers.** allin1 measures
0.67 boundary F1 and under-splits heavily, so its failure to confirm a human
boundary is weak evidence against it — and per the corpus it is the common case
(*ayuni* 5/17 human boundaries confirmed, *Cinderella* 14/21). Nothing reaches
1.0.

### Why labels are excluded

`reference/human/segments.json` is curated on top of an allin1 or moises seed:
the operator adjusts times, but may leave a label untouched. So a matching
label can be the seed agreeing with a copy of itself, while a matching *time*
means the operator saw that boundary and kept it — real ratification.

The measurement agrees. Requiring `start` **and** `end` **and** `label` to
match fires on 11 of 141 rows corpus-wide, and on **zero rows in four of eight
songs**; boundary-time corroboration alone fires on 30–70% of boundaries.
Per-row edge-pair matching is also wrong for the same under-splitting reason —
one merged allin1 span confirms its own two edges and cannot confirm any split
inside it.

### This is scoring, not merging

No span moves, no label moves, and precedence is untouched — the whole-song
override above still decides *which* producer's rows are published. The other
producers only vote on how much to trust the boundary times of the rows that
already won. The per-boundary *merging* rejected above is a different thing and
stays rejected.

## Label vocabulary

Every `function` value must be a term from
[`../segments-vocabulary.md`](../segments-vocabulary.md). Two normalizers
enforce this, in [`../../src/analyzer/section_vocabulary.py`](../../src/analyzer/section_vocabulary.py):

- **allin1 (tier 3, our own segmentation)** — `normalize_allin1_label`.
  Strict: allin1's Harmonix label set is closed and versioned, so an
  unrecognized token raises rather than passing through (a model-version
  drift, not a typo).
- **human and moises (tiers 1 and 2)** — `normalize_human_label`, shared by
  both. Permissive: casefold/whitespace correction against the canonical
  spelling, plus a small known-synonym alias table (`_HUMAN_LABEL_ALIASES`,
  e.g. `"Instrumental"` → `"Main"`). A label matching neither is passed
  through stripped, unchanged — it is that producer's own ground truth, not
  a guess this module may overwrite.

## Attribution

`sections.json`'s `field_sources` header names the winning tier per field
(`"human"` / `"moises"` / `"allin1"` / `"harmonic"`), built by `_fuse(...)` in
`ui_data.py` — see [`artifacts.md`](artifacts.md)'s `field_sources` table for
the general attribution mechanism; this file only adds the precedence order
above the existing `_fuse` candidate lists.

## Debugger lanes

Each source has its own read-only debugger lane so the three-way precedence
can be audited visually, without waiting for a song to have the fused
`sections.json`'s override tier reveal which producer actually won:

| Lane | Reads |
| --- | --- |
| Human Sections | `reference/human/segments.json` (writable — the one producer the debugger may edit) |
| Moises Sections | `reference/moises/segments.json` (read-only) |
| allin1 Segmentation | `artifacts/section_segmentation/sections.json` (read-only, pre-fusion) |
| Sections | the fused, published `sections.json` |

`docs/ui-definition.md`'s Lanes table has the one-line summary of each; this
file is the fusion logic they exist to audit.
