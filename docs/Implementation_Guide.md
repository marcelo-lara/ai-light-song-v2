# Audio -> Lighting Pipeline Implementation Guide

## Purpose

This document is the canonical hub for the repository. It defines the pipeline structure, repository contracts, story ordering, and the relationship between detailed story-level specifications.

It is intentionally concise. Detailed implementation rules live in the linked story files.

## Repository Contracts

### Folder semantics

- `src/`: implementation code. Organize it with subfolders for cohesive features or analysis phases rather than by file type.
- `data/songs/`: source `.mp3` files for analysis.
- `data/stems/`: temporary stem and `.wav` outputs.
- `data/artifacts/`: intermediate artifacts such as beats, chords, sections, layer outputs, merged layer files, and validation notes.
- `data/reference/`: validation-only reference data used to evaluate model quality. It must never be copied into generated outputs.
- `data/output/`: final outputs such as lighting scores and future DMX-ready event exports.
- `docs/`: implementation contracts, schemas, and developer guidance.

### Source layout and implementation rules

- Group code inside `src/` by pipeline phase or feature boundary, for example `src/audio_preprocessing/`, `src/harmonic/`, `src/symbolic/`, `src/energy/`, and `src/lighting/`.
- Keep `src/shared/` or similarly named common folders limited to truly cross-cutting utilities, schemas, or infrastructure code.
- Do not add silent fallbacks or substitute inference algorithms when a story specifies a primary dependency. Fail explicitly and document the failure mode.
- Remove deprecated helpers, dead code, and compatibility shims rather than preserving them by default.
- Update the relevant docs in the same change whenever contracts, artifact paths, runtime commands, or validation behavior change.

### Global data rules

- Generated files must include explicit `generated_from` metadata when practical.
- The term `reference` is reserved for `/data/reference/` and human-validated, read-only source-of-truth material only.
- Generated files inside `data/artifacts/` must use producer-scoped namespaces when that provenance matters, such as `essentia/`, `moises/`, `section_segmentation/`, `energy_summary/`, or `pattern_mining/`.
- Time values are expressed in seconds.
- Bars are 1-indexed.
- Beat and bar alignment come from the canonical EPIC 1.2 timing grid.
- Schemas must be versioned.
- Reference files are for validation only, not fallback generation.

## Containerized Development Rule

All development, validation, and sample-song execution must run inside the project Docker environment.

- Target environment: NVIDIA GPU-enabled Docker runtime.
- Do not depend on host-installed Python packages.
- Validate tool imports and sample-song runs inside the container.

See `docs/docker_development.md` and the repository `Dockerfile` for the runtime contract.

## Pipeline Overview

The pipeline is divided into five epics:

1. EPIC 1: audio preprocessing.
2. EPIC 2: harmonic summary.
3. EPIC 3: symbolic event summary.
4. EPIC 4: audio energy summary.
5. EPIC 5: unified music feature assembly and lighting design.

## EPIC 1: Audio Preprocessing Pipeline

Goal: prepare clean, aligned source material for all downstream analysis.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 1.1 | Stem separation and caching | normalized stems and stem metadata | `docs/1.1.stem_separation_story.md` |
| 1.2 | Beat, tempo, and bar grid detection | BPM, beats, bars, timing grid | `docs/1.2.beat_tempo_detection_story.md` |

## EPIC 2: Harmonic Summary

Goal: provide tonal, chordal, and harmonic-motion context.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 2.1 | HPCP extraction | beat-aligned chroma/HPCP features | `docs/2.1.hpcp_extraction_story.md` |
| 2.2 | Chord inference | chord probabilities, decoded chord events | `docs/2.2.chord_detection_story.md` |
| 2.3 | Key and tonal center detection | global key and optional section key estimates | `docs/2.3.key_tonal_center_story.md` |
| 2.4 | Harmonic feature derivation | cadence, tension, mobility, role summaries | `docs/2.4.harmonic_features_story.md` |

Representative artifact: `layer_a_harmonic.json`.

## EPIC 3: Symbolic Event Summary

Goal: translate audio into note-level and phrase-level musical behavior.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 3.1 | MIDI-like transcription | validated multi-source note events from stems and full mix | `docs/3.1.midi_transcription_story.md` |
| 3.2 | Symbolic feature engineering | density, contour, range, repetition, sustain | `docs/3.2.symbolic_feature_engineering_story.md` |
| 3.3 | Temporal alignment | beat-, bar-, and phrase-aligned symbolic timeline | `docs/3.3.temporal_alignment_story.md` |
| 3.4 | LLM-friendly abstraction | deterministic musician-readable symbolic descriptions | `docs/3.4.llm_friendly_abstraction_story.md` |

Representative artifact: `layer_b_symbolic.json`.

## EPIC 4: Audio Energy Summary

Goal: capture physical intensity, brightness, transients, and structure.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 4.1 | Low-level energy feature extraction | frame- and beat-level loudness, centroid, flux, onset | `docs/4.1.energy_feature_schema.md` |
| 4.2 | Section segmentation | structural change windows, optional labels, confidence | `docs/4.2.section_segmentation_story.md` |
| 4.3 | Derived energy features | energy cards, peaks, dips, accent candidates | `docs/4.3.energy_feature_derivation_story.md` |

Representative artifact: `layer_c_energy.json`.

## EPIC 5: Pattern Mining, Unified Music Feature Assembly, and Light Show Design

Goal: derive recurring harmonic pattern structure as Layer D, consolidate the upstream layers into a single handoff artifact, then translate that artifact into lighting behavior and a human-readable lighting score.

Layer D covers repeated harmonic progression structure. Motif-level and phrase-level repetition summaries remain part of the symbolic layer.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 5.1 | Find chord patterns | `pattern_mining/chord_patterns.json` and `layer_d_patterns.json` | `docs/5.1.find_chord_patterns_story.md` |
| 5.2 | Unified music feature layer assembly | `music_feature_layers.json` and documented helper outputs | `docs/5.2.music_feature_layers_story.md` |
| 5.3 | Feature-to-lighting mapping | normalized lighting events and mapping logic | `docs/5.3.energy_to_lighting_mapping.md` |
| 5.4 | Fixture-aware orchestration | fixture-aware events and `lighting_score.md` | `docs/5.4.fixture_aware_mapping_story.md` |

Representative artifacts: `layer_d_patterns.json`, `music_feature_layers.json`, `lighting_score.md`.

## Canonical Artifact Flow

The expected high-level artifact dependency chain is:

1. Source song in `data/songs/`.
2. Stem outputs in `data/stems/`.
3. Timing, harmonic, symbolic, and energy artifacts in `data/artifacts/<Song - Artist>/`.
4. Pattern-mining outputs in `data/artifacts/<Song - Artist>/pattern_mining/` and the Layer D file `layer_d_patterns.json` in `data/artifacts/<Song - Artist>/`.
5. Unified cross-layer handoff file `music_feature_layers.json` in `data/artifacts/<Song - Artist>/`.
6. Final outputs in `data/output/<Song - Artist>/`.

## Required Supporting Documents

- `docs/layer_manifest.md`: layer-by-layer artifact contract.
- `docs/lighting_score_template.md`: stable lighting-score structure.
- `docs/docker_development.md`: container runtime and validation contract.
- `docs/phase_1_validation_cli.md`: first-phase analyzer entry point and reference-comparison contract.

## Lighting-Score-Ready Minimum Artifact Set

Before Story 5.4 can produce a reliable `lighting_score.md`, the implementation should have at minimum:

- canonical beat and bar timing from Story 1.2 with per-beat time, 1-indexed bar, and beat-in-bar indices
- `data/artifacts/<Song - Artist>/section_segmentation/sections.json` with stable section IDs and exact section windows
- `data/artifacts/<Song - Artist>/layer_b_symbolic.json` with `motif_summary.dominant_motif_id`, `motif_summary.motif_groups[]`, and `motif_summary.repeated_phrase_groups[]`
- phrase timing anchors exposed as `phrase_windows[]` or normalized into `music_feature_layers.json.timeline.phrases[]`
- `data/artifacts/<Song - Artist>/layer_c_energy.json` with accent windows, energy transitions, peaks, and dips relevant to cue placement
- `data/artifacts/<Song - Artist>/layer_d_patterns.json` with `patterns[].id` and occurrence windows using `start_s` and `end_s`
- `data/artifacts/<Song - Artist>/music_feature_layers.json` with `timeline.phrases[]`, `lighting_context.cue_anchors[]`, `lighting_context.pattern_callbacks[]`, and `lighting_context.motif_callbacks[]`
- fixture-agnostic lighting events from Story 5.3 with `anchor_refs` that point back to section, phrase, motif, pattern, and cue-anchor IDs
- `data/fixtures/fixtures.json` so Story 5.4 can translate abstract behavior into fixture-aware instructions

If those artifacts are missing, the pipeline is not yet lighting-score-ready even if partial prose generation is possible.

## Validation Expectations

Every implementation story must define:

- exact inputs and upstream dependencies
- generated artifact paths
- schema examples
- acceptance criteria
- failure modes
- validation against documented schemas, generated outputs, and reference data when applicable

## First-Phase Validation Target

Before the full pipeline is considered ready, the implementation should expose a first-phase validation entry point, preferably a CLI analyzer, that can:

1. run against a real song such as `What a Feeling - Courtney Storm.mp3`
2. generate inferred analysis artifacts inside `data/artifacts/<Song - Artist>/`
3. compare inferred chord outputs against human-validated reference chords and compare inferred section change points against validation-only reference segments in `data/reference/<Song - Artist>/moises/` when they are available
4. emit a validation summary or report without copying reference values into generated artifacts

Reference files under `data/reference/` are optional validation inputs. The pipeline must infer chords, sections, and other generated values from the documented analysis stack first. When reference files are present, they may be used to validate or explicitly review those inferred results, but they must not silently replace generated artifact values.

This first-phase validation target is documented in `docs/phase_1_validation_cli.md`.

That supporting document defines the recommended CLI command shape, required flags, exit codes, and the expected machine-readable validation report structure.

The final documentation set must remain internally consistent across story files, schemas, runtime commands, and validation contracts.
