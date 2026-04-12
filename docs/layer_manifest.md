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

Genre guidance from Story 2.5 is intentionally producer-scoped and does not extend the harmonic layer contract by default.

### `layer_b_symbolic.json`

Contains symbolic and note-event analysis outputs such as:

- note events
- density per beat and per bar
- phrase contours
- phrase anchors or phrase-group timing references when available
- symbolic summaries
- deterministic musician-readable descriptions
- bass movement events
- repeated motifs
- section-level symbolic cards

Primary source stories: EPIC 3.1 through EPIC 3.5.

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

Primary source story: EPIC 6.1.

## Supporting Artifact Files

### `genre.json`

Stores producer-scoped model-native genre or style winners, confidence, candidate predictions, and review guidance from Story 2.5. If classification is unavailable or ambiguous, the artifact should record `genres: ["unknown"]` rather than invoking a custom fallback algorithm.

### `energy_summary/features.json`

Stores base feature summaries and shared analysis signals used by higher-level layers.

### `section_segmentation/sections.json`

Stores structural section windows and optional heuristic labels used across symbolic, energy, and merged artifacts.

### `energy_summary/hints.json`

Stores producer-scoped named energy-event identifiers such as drops and other later-defined song moments that assist later aggregation and lighting mapping.

Primary source story: EPIC 5.4.

### `event_inference/features.json`

Stores normalized event-analysis feature rows aligned to the canonical timing grid and structural anchors.

Primary source story: EPIC 5.2.

### `event_inference/timeline_index.json`

Stores helper timing indices and anchor references that let later Epic 5 stages map event windows back to beats, sections, and phrases.

Primary source story: EPIC 5.2.

### `event_inference/rule_candidates.json`

Stores producer-scoped baseline rule candidates before final machine-event promotion and review merging.

Primary source story: EPIC 5.3.

### `event_inference/events.machine.json`

Stores the canonical machine-generated event set that downstream review, timeline export, and benchmarking stages consume.

Primary source story: EPIC 5.5.

### `pattern_mining/chord_patterns.json`

Stores the producer-scoped output of `find_chord_patterns(...)` before it is promoted into the canonical Layer D artifact.

### `pattern_mining/stem_patterns.json`

Stores repeated stem-aware patterns used for comparison or pattern-aware lighting logic.

### `symbolic_transcription/basic_pitch/*.json`

Stores producer-scoped raw Basic Pitch note caches, model-output summaries, and per-stem transcription metadata used to build `layer_b_symbolic.json`.

### `symbolic_transcription/validation.json`

Stores source-level symbolic validation results and promotion decisions used to assemble the final `layer_b_symbolic.json` artifact from all analyzed stems and the full mix.

### `symbolic_transcription/hints.json`

Stores deterministic section-level hint inference derived from the aligned symbolic timeline before user-authored edits are merged into the output-facing hints file.

### `validation/event_benchmark.json`

Stores event-specific benchmark status and output-surface checks for the Epic 5 review and timeline chain.

Primary source story: EPIC 5.7.

### `validation/song_events.review.json`

Stores the reviewed event payload used for human review without expanding the UI-facing `data/output/<Song - Artist>/` contract.

Primary source story: EPIC 5.6.

### `validation/song_events.review.md`

Stores the human-readable markdown companion to `validation/song_events.review.json`.

Primary source story: EPIC 5.6.

### `validation/song_events.overrides.json`

Stores persistent user-authored review operations that are re-applied when the reviewed event payload is regenerated.

Primary source story: EPIC 5.6.

### `validation/song_event_timeline.md`

Stores the human-readable markdown companion to the compact UI-facing event timeline JSON.

Primary source story: EPIC 5.8.

### `info.json`

Stores canonical song metadata and references to major generated files. This file is written to `data/output/<Song - Artist>/info.json`.

Expected top-level metadata fields are `song_name`, `bpm`, and `duration`, with file references grouped under `artifacts`, `generated_from`, and `outputs`.

## Consolidated Output Files

`data/output/<Song - Artist>/` is a stable UI contract. Each song output directory must contain exactly `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, and `lighting_score.md`. `lighting_score.md` is the only markdown file allowed there. Do not add or remove files from this directory unless a UI contract change makes that strictly required.

### `data/output/<Song - Artist>/beats.json`

Stores compact UI-facing beat rows projected from `essentia/beats.json`, aligned chord labels projected from `layer_a_harmonic.json`, and a beat-aligned bass note projected from `symbolic_transcription/basic_pitch/bass.json`.

Expected fields per row are `time`, `beat`, `bar`, `bass`, `chord`, and `type`, where `bass` is a pitch-class note name without octave suffix.

### `data/output/<Song - Artist>/sections.json`

Stores compact UI-facing section rows projected from `section_segmentation/sections.json`.

Expected fields per row are `start`, `end`, `label`, `description`, and `hints`, where `label` embeds the numeric section id prefix and a confidence suffix such as `001 Intro (0.74)`. The `hints` field remains a placeholder in this file and is not the authoritative editable hint store.

### `data/output/<Song - Artist>/hints.json`

Stores the editable merged section hints consumed by `lighting_score.md`, combining regenerated inference-authored hints with preserved user-authored hints.

### `data/output/<Song - Artist>/song_event_timeline.json`

Stores the compact reviewed event timeline exported for downstream lighting logic and prompt-friendly consumption. Each inferred entry should carry an explicit `created_by` value in the form `analyzer_{module/algorithm/model}`.

Primary source story: EPIC 5.8.

### `data/output/<Song - Artist>/lighting_score.md`

Stores the final human-readable lighting design document. This is the only markdown file allowed under `data/output/<Song - Artist>/`.

## Unified Artifact

### `music_feature_layers.json`

This is the EPIC 6.3 output. It combines:

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
- `layers.symbolic.phrase_windows[].id`
- `layers.symbolic.phrase_windows[].phrase_group_id`
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

This file is the explicit handoff artifact for EPIC 6.4 and EPIC 6.5.

### `lighting_events.json`

Stores fixture-agnostic lighting events and normalized cue anchors derived from `music_feature_layers.json`.

This file is the explicit handoff artifact for EPIC 6.5.

When Story 6.5 emits fixture-aware overlay metadata, the event records should preserve deterministic links back to the triggering music logic, for example through fields such as `event_ref`, `role_overlay`, and explicit focal targets for supported fixtures.

## Cross-File Rules

- All major artifacts should use `schema_version`.
- All major artifacts should record upstream dependencies in `generated_from`.
- Shared timing must remain consistent across all layer files.
- The term `reference` is reserved for `/data/reference/` only and must not be used for inferred artifacts under `data/artifacts/`.
- Generated artifacts should use producer-scoped subfolders when that provenance matters, such as `essentia/` for inferred beats, `section_segmentation/` for inferred sections, `energy_summary/` for derived feature summaries, and `pattern_mining/` for pattern outputs.
- Reference inputs under `data/reference/` are always read-only and may be used for validation or explicit review only.