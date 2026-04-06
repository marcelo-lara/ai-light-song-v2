# Audio -> Lighting Pipeline Implementation Guide

## Purpose

This document is the canonical hub for the repository. It defines the pipeline structure, repository contracts, story ordering, and the relationship between detailed story-level specifications.

It is intentionally concise. Detailed implementation rules live in the linked story files.

## Repository Contracts

### Folder semantics

- `data/songs/`: source `.mp3` files for analysis.
- `data/stems/`: temporary stem and `.wav` outputs.
- `data/artifacts/`: intermediate artifacts such as beats, chords, sections, layer outputs, merged layer files, and validation notes.
- `data/reference/`: validation-only reference data used to evaluate model quality. It must never be copied into generated outputs.
- `data/output/`: final outputs such as lighting scores and future DMX-ready event exports.
- `docs/`: implementation contracts, schemas, and developer guidance.

### Global data rules

- Generated files must include explicit `generated_from` metadata when practical.
- The term `reference` is reserved for `/data/reference/` and human-validated, read-only source-of-truth material only.
- Generated files inside `data/artifacts/` must use model- or tool-scoped namespaces when that provenance matters, such as `essentia/` or `moises/`.
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
| 3.1 | MIDI-like transcription | note events from harmonic and bass stems | `docs/3.1.midi_transcription_story.md` |
| 3.2 | Symbolic feature engineering | density, contour, range, repetition, sustain | `docs/3.2.symbolic_feature_engineering_story.md` |
| 3.3 | Temporal alignment | beat- and bar-aligned symbolic timeline | `docs/3.3.temporal_alignment_story.md` |
| 3.4 | LLM-friendly abstraction | musician-readable symbolic descriptions | `docs/3.4.llm_friendly_abstraction_story.md` |

Representative artifact: `layer_b_symbolic.json`.

## EPIC 4: Audio Energy Summary

Goal: capture physical intensity, brightness, transients, and structure.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 4.1 | Low-level energy feature extraction | frame- and beat-level loudness, centroid, flux, onset | `docs/4.1.energy_feature_schema.md` |
| 4.2 | Section segmentation | section boundaries, labels, confidence | `docs/4.2.section_segmentation_story.md` |
| 4.3 | Derived energy features | energy cards, peaks, dips, accent candidates | `docs/4.3.energy_feature_derivation_story.md` |

Representative artifact: `layer_c_energy.json`.

## EPIC 5: Unified Music Feature Assembly and Light Show Design

Goal: consolidate upstream layer outputs into a single handoff artifact, then translate that artifact into lighting behavior and a human-readable lighting score.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 5.1 | Unified music feature layer assembly | `music_feature_layers.json` and documented helper outputs | `docs/5.1.music_feature_layers_story.md` |
| 5.2 | Feature-to-lighting mapping | normalized lighting events and mapping logic | `docs/5.2.energy_to_lighting_mapping.md` |
| 5.3 | Fixture-aware orchestration | fixture-aware events and `lighting_score.md` | `docs/5.3.fixture_aware_mapping_story.md` |

Representative artifacts: `layer_d_musical.json`, `music_feature_layers.json`, `lighting_score.md`.

## Canonical Artifact Flow

The expected high-level artifact dependency chain is:

1. Source song in `data/songs/`.
2. Stem outputs in `data/stems/`.
3. Timing, harmonic, symbolic, and energy artifacts in `data/artifacts/<Song - Artist>/`.
4. Unified cross-layer handoff file `music_feature_layers.json` in `data/artifacts/<Song - Artist>/`.
5. Final outputs in `data/output/<Song - Artist>/`.

## Required Supporting Documents

- `docs/layer_manifest.md`: layer-by-layer artifact contract.
- `docs/lighting_score_template.md`: stable lighting-score structure.
- `docs/docker_development.md`: container runtime and validation contract.

## Validation Expectations

Every implementation story must define:

- exact inputs and upstream dependencies
- generated artifact paths
- schema examples
- acceptance criteria
- failure modes
- validation against sample artifacts and reference data

The final documentation set must be internally consistent with the sample artifact family already present in `data/artifacts/What a Feeling - Courtney Storm/`.
