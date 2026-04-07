# Layer Manifest

## Purpose

This document defines the role of the major artifact files under `data/artifacts/<Song - Artist>/`.

## Layer Files

### `layer_a_harmonic.json`

Contains harmonic analysis outputs such as:

- global key
- chord events
- harmonic summaries
- cadence notes
- section-level harmonic cards
- tension peaks

Primary source stories: EPIC 2.1 through EPIC 2.4.

### `layer_b_symbolic.json`

Contains symbolic and note-event analysis outputs such as:

- note events
- phrase contours
- phrase anchors or phrase-group timing references when available
- density per bar
- symbolic summaries
- bass movement events
- repeated motifs
- section-level symbolic cards

Primary source stories: EPIC 3.1 through EPIC 3.4.

### `layer_c_energy.json`

Contains energy analysis outputs such as:

- global energy summary
- loudness, onset, and spectral profiles
- section energy cards
- notable peaks and dips
- accent candidates

Primary source stories: EPIC 4.1 through EPIC 4.3.

### `layer_d_patterns.json`

Contains repeated harmonic-pattern outputs such as:

- pattern definitions
- representative bar sequences
- pattern occurrences
- mismatch counts

This layer is for repeated chord-progression structure. It complements, and does not replace, note-level or motif-level repetition summaries in `layer_b_symbolic.json`.

Primary source story: EPIC 5.1.

## Supporting Artifact Files

### `energy_summary/features.json`

Stores base feature summaries and shared analysis signals used by higher-level layers.

### `section_segmentation/sections.json`

Stores structural section windows and optional heuristic labels used across symbolic, energy, and merged artifacts.

### `energy_summary/hints.json`

Stores rises, drops, or other hint-level events that assist later aggregation.

### `pattern_mining/chord_patterns.json`

Stores the producer-scoped output of `find_chord_patterns(...)` before it is promoted into the canonical Layer D artifact.

### `pattern_mining/stem_patterns.json`

Stores repeated stem-aware patterns used for comparison or pattern-aware lighting logic.

### `symbolic_transcription/basic_pitch/*.json`

Stores producer-scoped raw Basic Pitch note caches, model-output summaries, and per-stem transcription metadata used to build `layer_b_symbolic.json`.

### `symbolic_transcription/validation.json`

Stores source-level symbolic validation results and promotion decisions used to assemble the final `layer_b_symbolic.json` artifact from all analyzed stems and the full mix.

### `info.json`

Stores canonical song metadata and references to major generated files.

## Unified Artifact

### `music_feature_layers.json`

This is the EPIC 5.2 output. It combines:

- shared metadata
- timeline objects such as beats, bars, sections, phrase anchors, and accent windows
- harmonic layer content
- symbolic layer content
- energy layer content
- pattern content
- lighting-facing cue-anchor references
- downstream mapping notes

The symbolic layer remains the owner of motif-level repetition summaries, while Layer D contributes harmonic progression-pattern structure.

For lighting-facing integration, the unified artifact should preserve these canonical cross-layer reference fields when available:

- `timeline.phrases[].id`
- `timeline.phrases[].phrase_group_id`
- `timeline.phrases[].start_s`
- `timeline.phrases[].end_s`
- `layers.symbolic.motif_summary.dominant_motif_id`
- `layers.symbolic.motif_summary.motif_groups[].id`
- `layers.patterns.occurrences[]`
- `layers.patterns.occurrences[].pattern_id`
- `layers.patterns.occurrences[].start_s`
- `layers.patterns.occurrences[].end_s`
- `lighting_context.cue_anchors[].id`
- `lighting_context.cue_anchors[].time_s`
- `lighting_context.cue_anchors[].anchor_type`
- `lighting_context.pattern_callbacks[].pattern_id`
- `lighting_context.pattern_callbacks[].callback_action`
- `lighting_context.motif_callbacks[].motif_group_id`
- `lighting_context.motif_callbacks[].callback_action`

This file is the explicit handoff artifact for EPIC 5.3 and EPIC 5.4.

## Cross-File Rules

- All major artifacts should use `schema_version`.
- All major artifacts should record upstream dependencies in `generated_from`.
- Shared timing must remain consistent across all layer files.
- The term `reference` is reserved for `/data/reference/` only and must not be used for inferred artifacts under `data/artifacts/`.
- Generated artifacts should use producer-scoped subfolders when that provenance matters, such as `essentia/` for inferred beats, `section_segmentation/` for inferred sections, `energy_summary/` for derived feature summaries, and `pattern_mining/` for pattern outputs.
- Reference inputs under `data/reference/` are always read-only and may be used for validation or explicit review only.