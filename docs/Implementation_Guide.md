# Audio -> Lighting Pipeline Implementation Guide

## Purpose

This document is the canonical hub for the repository. It defines the pipeline structure, repository contracts, story ordering, and the relationship between detailed story-level specifications.

It is intentionally concise. Detailed implementation rules live in the linked story files.

## Repository Contracts

### Folder semantics

- `src/`: implementation code. Organize it with subfolders for cohesive features or analysis phases rather than by file type.
- `ui/`: internal artifact-debugger web application and UI-specific container files. Keep browser assets and UI server configuration here rather than under `src/`.
- `data/songs/`: source `.mp3` files for analysis.
- `data/stems/`: temporary stem and `.wav` outputs.
- `data/artifacts/`: intermediate artifacts such as beats, chords, sections, layer outputs, merged layer files, and validation notes.
- `data/reference/`: validation and curated reference data used to evaluate model quality. It must never be copied into generated outputs.
- `data/output/`: stable UI-facing outputs. Each per-song directory must contain exactly `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, and `lighting_score.md`.
- `docs/`: implementation contracts, schemas, and developer guidance.

### Source layout and implementation rules

- Group code inside `src/` by pipeline phase or feature boundary, for example `src/audio_preprocessing/`, `src/harmonic/`, `src/symbolic/`, `src/energy/`, and `src/lighting/`.
- Keep `src/shared/` or similarly named common folders limited to truly cross-cutting utilities, schemas, or infrastructure code.
- Do not add silent fallbacks or substitute inference algorithms when a story specifies a primary dependency. Fail explicitly and document the failure mode.
- Remove deprecated helpers, dead code, and compatibility shims rather than preserving them by default.
- **Synchronization Rule:** Update the relevant docs and Story files in the same change whenever implementation details, contracts, artifact paths, or validation behavior change. The Story is the implementation's reflection.

### Global data rules

- Generated files must include explicit `generated_from` metadata when practical.
- The term `reference` is reserved for `/data/reference/` and human-validated source-of-truth material. Story 8.8 allows explicit editing only for `data/reference/<Song - Artist>/human/human_hints.json`.
- Generated files inside `data/artifacts/` must use producer-scoped namespaces when that provenance matters, such as `essentia/`, `moises/`, `section_segmentation/`, `energy_summary/`, or `pattern_mining/`.
- Time values are expressed in seconds.
- Bars are 1-indexed.
- **Timeline Totality:** All layers must cover the timeline from `0.0`. For structural boundaries (Sections/Events), prioritize the **Physical Onset** (transient) over the beat grid to ensure zero-latency synchronization.
- Beat and bar alignment come from the canonical EPIC 1.2 timing grid.
- Schemas must be versioned.
- Reference files are for validation only, not fallback generation.
- Do not add or remove files under `data/output/<Song - Artist>/` unless a UI contract change makes that strictly required.
- The internal debugger may read directly from `data/artifacts/<Song - Artist>/` and selected `data/output/<Song - Artist>/` helper files. It must not write files into either tree. The only persisted debugger edit path is `data/reference/<Song - Artist>/human/human_hints.json` on explicit save.

## Containerized Development Rule

All development, validation, and sample-song execution must run inside the project Docker environment.

- Target environment: NVIDIA GPU-enabled Docker runtime.
- Do not depend on host-installed Python packages.
- Validate tool imports and sample-song runs inside the container.
- Use `./analyze` or `python -m analyzer` as the supported container entry points.
- The analyzer runtime is the Compose `app` service. The internal debugger UI runs as a separate Compose `ui` service backed by the `/ui` folder, with generated data mounted read-only and only `data/reference/<Song - Artist>/human/human_hints.json` writable through the Story 8.8 helper UI flow.
- Batch runs via `--all-songs` must isolate each song in a subprocess because the long-lived parent process is not treated as a stable execution model for the native analysis stack.
- Demucs model weights must resolve through the repo-local cache under `models/demucs/` rather than opportunistic mid-run downloads.

See `docs/docker_development.md`, `docs/ui_development.md`, and the repository `Dockerfile` for the runtime contract.

## Pipeline Overview

The pipeline is divided into eight epics:

1. EPIC 1: audio preprocessing.
2. EPIC 2: harmonic summary.
3. EPIC 3: energy and structure.
4. EPIC 4: symbolic event summary.
5. EPIC 5: rule-based event detection.
6. EPIC 6: ML-based event classification.
7. EPIC 7: lighting score generation.
8. EPIC 8: internal artifact debugger and regression viewer.

## EPIC 1: Audio Preprocessing Pipeline

Goal: prepare clean, aligned source material for all downstream analysis.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 1.1 | Stem separation and caching | normalized stems and stem metadata | `docs/1.1.stem_separation_story.md` |
| 1.2 | Beat, tempo, and bar grid detection | BPM, beats, bars, timing grid | `docs/1.2.beat_tempo_detection_story.md` |
| 1.3 | Seven-band FFT extraction | `essentia/fft_bands.json` for debugger spectral inspection | `docs/1.3.fft_band_extraction_story.md` |
| 1.4 | Mix and per-stem loudness | `essentia/rms_loudness.json` and `essentia/loudness_envelope.json` for debugger loudness inspection | `docs/1.4.mix_and_per_stem_loudness_story.md` |

## EPIC 2: Harmonic Summary

Goal: provide tonal, chordal, and harmonic-motion context.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 2.1 | HPCP extraction | beat-aligned chroma/HPCP features | `docs/2.1.hpcp_extraction_story.md` |
| 2.2 | Chord inference | chord probabilities, decoded chord events | `docs/2.2.chord_detection_story.md` |
| 2.3 | Key and tonal center detection | global key and optional section key estimates | `docs/2.3.key_tonal_center_story.md` |
| 2.4 | Harmonic feature derivation | cadence, tension, mobility, role summaries | `docs/2.4.harmonic_features_story.md` |
| 2.5 | Song genre guidance | producer-scoped coarse genre label and review guidance | `docs/2.5.song_genre_guidance_story.md` |

Representative artifact: `layer_a_harmonic.json`.

## EPIC 3: Energy & Structure

Goal: capture physical intensity, brightness, transients, and structure.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 3.1 | Low-level energy feature extraction | frame- and beat-level loudness, centroid, flux, onset | `docs/3.1.energy_feature_schema.md` |
| 3.2 | Section segmentation | structural change windows, optional labels, confidence | `docs/3.2.section_segmentation_story.md` |
| 3.3 | Derived energy features | energy cards, peaks, dips, accent candidates | `docs/3.3.energy_feature_derivation_story.md` |
| 3.4 | Structural integrity audit | confidence scores and transient-locking metadata | `docs/3.4.structural_integrity_audit_story.md` |
| 3.5 | LLM-friendly song map | unified "Song Map" for LLM consumption | `docs/3.5.llm-friendly_song_map_abstraction.md` |

Representative artifact: `layer_c_energy.json`.

## EPIC 4: Symbolic Event Summary

Goal: translate audio into note-level, drum-hit, and phrase-level musical behavior.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 4.1 | MIDI-like transcription | validated multi-source note events from stems and full mix | `docs/4.1.midi_transcription_story.md` |
| 4.2 | Drums transcription | reviewable kick, snare, and hat event artifact | `docs/4.2.drums_transcription_story.md` |
| 4.3 | Symbolic feature engineering | density, contour, range, repetition, sustain | `docs/4.3.symbolic_feature_engineering_story.md` |
| 4.4 | Temporal alignment | beat-, bar-, and phrase-aligned symbolic timeline | `docs/4.4.temporal_alignment_story.md` |
| 4.5 | Section hint inference | deterministic symbolic and structural section hints with editable output merge | `docs/4.5.section_hints_story.md` |
| 4.6 | LLM-friendly abstraction | deterministic musician-readable symbolic descriptions | `docs/4.6.llm_friendly_abstraction_story.md` |

Representative artifact: `layer_b_symbolic.json`.

## EPIC 5: Rule-Based Event Detection

Goal: define the canonical event contract, infer musically meaningful event windows, support review and benchmarking, and export compact event timelines for downstream lighting logic.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 5.1 | Event vocabulary and schema | `event_vocabulary.json` and `song_event_schema.json` | `docs/5.1.event_vocabulary_and_schema_story.md` |
| 5.2 | Event feature normalization and timeline alignment | `event_inference/features.json` and helper indices such as `event_inference/timeline_index.json` | `docs/5.2.event_feature_normalization_story.md` |
| 5.3 | Rule-based baseline event detection | `event_inference/rule_candidates.json` | `docs/5.3.rule_based_event_detection_story.md` |
| 5.4 | Song identifier inference | `energy_summary/hints.json` | `docs/5.4.song_identifier_inference_story.md` |
| 5.5 | Advanced musical event classification | `event_inference/events.machine.json` | `docs/5.5.advanced_event_classification_story.md` |
| 5.6 | Confidence, review, and override workflow | `validation/song_events.review.json`, `validation/song_events.review.md`, and `validation/song_events.overrides.json` | `docs/5.6.event_review_and_override_story.md` |
| 5.7 | Event benchmarking and genre-sensitive tuning | `validation/event_benchmark.json`, benchmark annotations, and threshold profiles | `docs/5.7.event_benchmarking_and_tuning_story.md` |
| 5.8 | LLM-friendly event timeline export | `data/output/<Song - Artist>/song_event_timeline.json` and `validation/song_event_timeline.md` | `docs/5.8.event_timeline_export_story.md` |

Representative artifacts: `energy_summary/hints.json`, `event_inference/features.json`, `event_inference/rule_candidates.json`, `event_inference/events.machine.json`, `data/artifacts/<Song - Artist>/validation/song_events.review.json`, `data/output/<Song - Artist>/song_event_timeline.json`, `validation/event_benchmark.json`.

## EPIC 6: ML-Based Event Classification

Goal: Classify events from multi-modal feature streams with explainability.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 6.1 | Optional ML event classifier and explainability | classifier artifacts and explanation outputs | `docs/6.1.event_ml_classifier_story.md` |
| 6.2 | Unified perceptual embedding | `layer_perceptual_embedding.json` and `layer_musical_signature.json` | `docs/6.2.unified_perceptual_embedding_story.md` |

## EPIC 7: Lighting Score Generation

Goal: derive recurring harmonic pattern structure as Layer D, project compact UI-facing beat and section outputs, consolidate the upstream layers into a single handoff artifact, then translate that artifact into lighting behavior and a human-readable lighting score.

Layer D covers repeated harmonic progression structure. Motif-level and phrase-level repetition summaries remain part of the symbolic layer.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 7.1 | Find chord patterns | `pattern_mining/chord_patterns.json` and `layer_d_patterns.json` | `docs/7.1.find_chord_patterns_story.md` |
| 7.2 | Build UI data | `data/output/<Song - Artist>/beats.json` and `data/output/<Song - Artist>/sections.json` | `docs/7.2.build_ui_data_story.md` |
| 7.3 | Unified music feature layer assembly | `music_feature_layers.json` and documented helper outputs | `docs/7.3.music_feature_layers_story.md` |
| 7.4 | Feature-to-lighting mapping | fixture-agnostic `lighting_events.json` and mapping logic | `docs/7.4.energy_to_lighting_mapping.md` |
| 7.5 | Fixture-aware orchestration | fixture-aware events with stable-role and event-overlay logic, plus `lighting_score.md` | `docs/7.5.fixture_aware_mapping_story.md` |

Representative artifacts: `layer_d_patterns.json`, `data/output/<Song - Artist>/beats.json`, `data/output/<Song - Artist>/sections.json`, `music_feature_layers.json`, `lighting_events.json`, `lighting_score.md`.

## EPIC 8: Internal Artifact Debugger and Regression Viewer

Goal: provide an internal web debugger for inspecting generated inferences, timing alignment, and validation surfaces without changing the stable downstream output contract. Generated artifacts and outputs remain read-only; Story 8.8 adds an explicit reference-human-hints editing surface.

The debugger is an internal engineering and review tool. Its primary inspection surface is `data/artifacts/<Song - Artist>/`. It may also read compact helper projections from `data/output/<Song - Artist>/`, but it must not write debugger state or exported files into either tree. The only allowed persisted edit is `data/reference/<Song - Artist>/human/human_hints.json`.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 8.1 | Song auto-discovery and artifact entry | discovered song-directory selection and artifact entry shell | `docs/8.1.song_auto_discovery_and_artifact_entry_story.md` |
| 8.2 | Master sync and waveform anchor | debugger playback shell and shared timeline clock | `docs/8.2.master_sync_and_waveform_anchor_story.md` |
| 8.3 | DAW-style lane architecture | shared lane layout, zoom, filtering, and scroll sync | `docs/8.3.daw_style_lane_architecture_story.md` |
| 8.4 | Sparse data lanes | section, chord, pattern, and event-region lanes | `docs/8.4.sparse_data_lanes_story.md` |
| 8.5 | High-density lanes | drum, density, and energy renderers | `docs/8.5.high_density_lanes_story.md` |
| 8.6 | Semantic zoom and performance guardrails | clustering, zoom floors, and viewport-limited rendering | `docs/8.6.semantic_zoom_and_performance_story.md` |
| 8.7 | Regression validation overlay | beat-grid, drift, and validation comparison overlays | `docs/8.7.regression_validation_overlay_story.md` |
| 8.8 | Human hint editor | explicit editing of reference human hints in the helper UI | `docs/8.8.human_hint_editor_story.md` |
| 8.9 | Identifier and ML event lanes | read-only debugger lanes for rule identifier hints and ML event predictions | `docs/8.9.identifier_and_ml_event_lanes_story.md` |

Representative implementation assets: `/ui/`, the Compose `ui` service, debugger access to `layer_a_harmonic.json`, `layer_b_symbolic.json`, `layer_c_energy.json`, `layer_d_patterns.json`, `event_inference/*.json`, `validation/phase_1_report.json`, `music_feature_layers.json`, and the editable reference file `data/reference/<Song - Artist>/human/human_hints.json`.

## Canonical Artifact Flow

The expected high-level artifact dependency chain is:

1. Source song in `data/songs/`.
2. Stem outputs in `data/stems/`.
3. Timing, harmonic, symbolic, and energy artifacts in `data/artifacts/<Song - Artist>/`.
4. Event-inference artifacts in `data/artifacts/<Song - Artist>/event_inference/` and identifier hints in `data/artifacts/<Song - Artist>/energy_summary/hints.json`.
5. Review, override, timeline-markdown, and benchmark outputs in `data/artifacts/<Song - Artist>/validation/`, plus the UI timeline JSON in `data/output/<Song - Artist>/song_event_timeline.json`.
6. Pattern-mining outputs in `data/artifacts/<Song - Artist>/pattern_mining/` and the Layer D file `layer_d_patterns.json` in `data/artifacts/<Song - Artist>/`.
7. UI-facing `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, and `lighting_score.md` in `data/output/<Song - Artist>/`.
8. Unified cross-layer handoff file `music_feature_layers.json` in `data/artifacts/<Song - Artist>/`.
9. No additional routine files are added to `data/output/<Song - Artist>/` beyond the stable UI contract unless a UI contract change makes that strictly required.
10. The internal debugger served from `/ui/` reads `data/artifacts/<Song - Artist>/` and selected output helper files without writing any new files back into those generated-data directories.

## Required Supporting Documents

- `docs/constitution.md`: high-level project values, coding standards, and architectural principles.
- `docs/layer_manifest.md`: layer-by-layer artifact contract.
- `docs/lighting_score_template.md`: stable lighting-score structure.
- `docs/docker_development.md`: container runtime and validation contract.
- `docs/ui_development.md`: internal debugger runtime, folder ownership, and read-only data-access contract.
- `docs/phase_1_validation_cli.md`: first-phase analyzer entry point and reference-comparison contract.

## Lighting-Score-Ready Minimum Artifact Set

Before Story 7.5 can produce a reliable `lighting_score.md`, the implementation should have at minimum:

- canonical beat and bar timing from Story 1.2 with per-beat time, 1-indexed bar, and beat-in-bar indices
- `data/artifacts/<Song - Artist>/section_segmentation/sections.json` with stable section IDs and exact section windows
- `data/artifacts/<Song - Artist>/layer_b_symbolic.json` with `motif_summary.dominant_motif_id`, `motif_summary.motif_groups[]`, and `motif_summary.repeated_phrase_groups[]`
- phrase timing anchors exposed as `phrase_windows[]` or normalized into `music_feature_layers.json.timeline.phrases[]`
- `data/artifacts/<Song - Artist>/layer_c_energy.json` with accent windows, energy transitions, peaks, and dips relevant to cue placement
- `data/output/<Song - Artist>/song_event_timeline.json` or equivalent reviewed event export when event-aware lighting logic is enabled, with canonical event IDs and exact event windows preserved
- `data/artifacts/<Song - Artist>/layer_d_patterns.json` with `patterns[].id` and occurrence windows using `start_s` and `end_s`
- `data/artifacts/<Song - Artist>/music_feature_layers.json` with `timeline.phrases[]`, `lighting_context.cue_anchors[]`, `lighting_context.pattern_callbacks[]`, and `lighting_context.motif_callbacks[]`
- fixture-agnostic lighting events from Story 7.4 with `anchor_refs` that point back to section, phrase, motif, pattern, and cue-anchor IDs
- fixture-aware events from Story 7.5, when exported separately, with exact `event_ref`, `role_overlay`, and explicit target metadata for dynamic regroupings such as moving-head unison focus
- `data/fixtures/fixtures.json` so Story 7.5 can translate abstract behavior into fixture-aware instructions

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
4. validate the generated Story 4.2 drum review artifact for recognizable kick, snare, and hat behavior on `What a Feeling - Courtney Storm.mp3` without treating reference data as generation fallback
5. emit a validation summary or report without copying reference values into generated artifacts

Reference files under `data/reference/` are optional validation inputs. The pipeline must infer chords, sections, and other generated values from the documented analysis stack first. When reference files are present, they may be used to validate or explicitly review those inferred results, but they must not silently replace generated artifact values.

This first-phase validation target is documented in `docs/phase_1_validation_cli.md`.

That supporting document defines the recommended CLI command shape, required flags, exit codes, and the expected machine-readable validation report structure.

The final documentation set must remain internally consistent across story files, schemas, runtime commands, and validation contracts.

## Workspace Cleanup
- Never leave temporary scripts, patching code, or scaffolded one-off files laying around in the workspace. Always clean up after yourself.
