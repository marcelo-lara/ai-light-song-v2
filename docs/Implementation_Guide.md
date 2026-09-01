# Audio -> Lighting Pipeline Implementation Guide

## Purpose

This document is the canonical hub for the repository. It defines the pipeline structure, repository contracts, story ordering, and the relationship between detailed story-level specifications.

It is intentionally concise. Detailed implementation rules live in the linked story files.

## Repository Contracts

### Folder semantics

- `src/`: implementation code. Organize it with subfolders for cohesive features or analysis phases rather than by file type.
- `ui/`: internal artifact-debugger web application and UI-specific container files. Keep browser assets and UI server configuration here rather than under `src/`.
- `data/songs/`: source `.mp3` files for analysis.
- `data/analysis/<Song - Artist>/artifacts/stems/`: temporary stem and `.wav` outputs.
- `data/analysis/<Song - Artist>/artifacts/`: intermediate artifacts such as beats, chords, sections, layer outputs, merged layer files, and validation notes.
- `data/analysis/<Song - Artist>/reference/`: validation and curated reference data used to evaluate model quality. It must never be copied into generated outputs.
- `data/analysis/<Song - Artist>/`: stable UI-facing outputs, alongside (but outside) the nested `artifacts/` folder. Each per-song directory must contain `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, `lighting_score.md`, and `beatdrop_visual_plan.json`. `beatdrop_visual_plan.md` is an optional companion narrative export.
- `docs/`: implementation contracts, schemas, and developer guidance.

### Source layout and implementation rules

- Group code inside `src/` by pipeline phase or feature boundary, for example `src/audio_preprocessing/`, `src/harmonic/`, `src/symbolic/`, `src/energy/`, and `src/lighting/`.
- Keep `src/shared/` or similarly named common folders limited to truly cross-cutting utilities, schemas, or infrastructure code.
- Do not add silent fallbacks or substitute inference algorithms when a story specifies a primary dependency. Fail explicitly and document the failure mode.
- Remove deprecated helpers, dead code, and compatibility shims rather than preserving them by default.
- **Synchronization Rule:** Update the relevant docs and Story files in the same change whenever implementation details, contracts, artifact paths, or validation behavior change. The Story is the implementation's reflection.

### Global data rules

- Generated files must include explicit `generated_from` metadata when practical.
- The term `reference` is reserved for `data/analysis/<Song - Artist>/reference/` and human-validated source-of-truth material. Story 8.8 allows explicit editing only for `data/analysis/<Song - Artist>/reference/human/human_hints.json`.
- Generated files inside `data/analysis/` must use producer-scoped namespaces when that provenance matters, such as `essentia/`, `moises/`, `section_segmentation/`, `energy_summary/`, or `pattern_mining/`.
- Time values are expressed in seconds.
- Bars are 1-indexed.
- **Timeline Totality:** All layers must cover the timeline from `0.0`. For structural boundaries (Sections/Events), prioritize the **Physical Onset** (transient) over the beat grid to ensure zero-latency synchronization.
- Beat and bar alignment come from the canonical EPIC 1.2 timing grid.
- Schemas must be versioned.
- Reference files are validation-only by default. A Story may explicitly allow confidence-gated reference promotion for a named artifact when the inferred result falls below a documented quality threshold. That promotion must preserve the inferred artifact, must not hide the failure, and must record the reference source and promotion reason in provenance and validation output.
- Do not add or remove files under `data/analysis/<Song - Artist>/` unless a UI contract change makes that strictly required.
- The internal debugger may read directly from `data/analysis/<Song - Artist>/artifacts/` and selected `data/analysis/<Song - Artist>/` helper files. It must not write files into either tree. The only persisted debugger edit paths are `data/analysis/<Song - Artist>/reference/human/human_hints.json` and, as of v2.1, `data/analysis/<Song - Artist>/reference/human/song_facts.json` — both on explicit save only.
- **v2.1 module release.** Two-axis section labelling (`form_family` + `form_role`, with `energy_character` as secondary), repetition identity (`repetition_group`), honest boundary `confidence`, stem-relative drop detection on weighted evidence, composite events with typed `phases[]`, an absolute `intensity` scale, and the `review_queue.json` → `song_facts.json` human loop. Full per-item detail in `docs/implementation-plan-v2.1.md`; the MCP handover is `docs/source references/contract-change-v2.1.md`.

## Containerized Development Rule

All development, validation, and sample-song execution must run inside the project Docker environment.

- Target environment: NVIDIA GPU-enabled Docker runtime.
- Do not depend on host-installed Python packages.
- Validate tool imports and sample-song runs inside the container.
- During implementation, validate only the updated stage(s) with `--stage` where possible.
- At the end of each implementation task, run one full pipeline command (no `--stage`) and treat that report as the final end-to-end validation gate.
- Use `./analyze` or `python -m analyzer` as the supported container entry points.
- The analyzer runtime is the Compose `app` service. The internal debugger UI runs as a separate Compose `ui` service backed by the `/ui` folder, with generated data mounted read-write and only `data/analysis/<Song - Artist>/reference/human/human_hints.json` writable in practice, enforced by the helper UI's own Story 8.8 save flow.
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
| 1.1 | Stem separation and High-Res Preprocessing | normalized stems, downsampling, stem metadata | `docs/audio-inference/1.1.stem_separation_story.md` |
| 1.2 | Beat, tempo, and bar grid detection | BPM, beats, bars, timing grid | `docs/audio-processing/1.2.beat_tempo_detection_story.md` |
| 1.3 | Seven-band FFT extraction | `essentia/fft_bands.json` for debugger spectral inspection | `docs/audio-processing/1.3.fft_band_extraction_story.md` |
| 1.4 | Mix and per-stem loudness with History Buffers | `rms_loudness.json` with 2-5s rolling history | `docs/audio-processing/1.4.mix_and_per_stem_loudness_story.md` |

## EPIC 2: Harmonic Summary

Goal: provide tonal, chordal, and harmonic-motion context.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 2.1 | HPCP extraction | beat-aligned chroma/HPCP features | `docs/audio-processing/2.1.hpcp_extraction_story.md` |
| 2.2 | Chord inference | chord probabilities, decoded chord events | `docs/audio-inference/2.2.chord_detection_story.md` |
| 3.3 | Key and tonal center detection | global key and optional section key estimates | `docs/audio-processing/3.3.key_tonal_center_story.md` |
| 4.2 | Harmonic feature derivation | cadence, tension, mobility, role summaries | `docs/audio-processing/4.2.harmonic_features_story.md` |
| 6.1 | Song genre guidance | producer-scoped coarse genre label and review guidance | `docs/audio-inference/6.1.song_genre_guidance_story.md` |

Representative artifact: `layer_a_harmonic.json`.

## EPIC 3: Energy & Structure

Goal: capture physical intensity, brightness, transients, and structure.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 2.6 | Low-level energy feature extraction | frame- and beat-level loudness, centroid, flux, onset | `docs/audio-processing/2.6.energy_feature_schema.md` |
| 3.1 | Section segmentation | structural change windows, optional labels, confidence | `docs/audio-inference/3.1.section_segmentation_story.md` |
| 4.1 | Derived energy features | energy cards, peaks, dips, accent candidates | `docs/audio-processing/4.1.energy_feature_derivation_story.md` |
| 3.2 | Structural integrity audit | confidence scores and transient-locking metadata | `docs/audio-inference/3.2.structural_integrity_audit_story.md` |
| 6.3 | LLM-friendly song map abstraction | unified deterministic song map for prompt-based consumers | `docs/audio-inference/6.3.unified_llm_friendly_abstraction_story.md` |

Representative artifact: `layer_c_energy.json`.

## EPIC 4: Symbolic Event Summary

Goal: translate audio into note-level, drum-hit, and phrase-level musical behavior.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 2.4 | MIDI-like transcription | validated multi-source note events from stems and full mix | `docs/audio-inference/2.4.midi_transcription_story.md` |
| 2.5 | Drums transcription | reviewable kick, snare, and hat event artifact | `docs/audio-inference/2.5.drums_transcription_story.md` |
| 4.3 | Symbolic feature engineering | density, contour, range, repetition, sustain | `docs/audio-processing/4.3.symbolic_feature_engineering_story.md` |
| 3.4 | Temporal alignment | beat-, bar-, and phrase-aligned symbolic timeline | `docs/audio-processing/3.4.temporal_alignment_story.md` |
| 6.2 | Section hint inference | deterministic symbolic and structural section hints with editable output merge | `docs/audio-inference/6.2.section_hints_story.md` |
| 6.3 | Unified LLM-friendly abstraction | deterministic prompt-facing song map with symbolic, structural, and identifier context | `docs/audio-inference/6.3.unified_llm_friendly_abstraction_story.md` |

Representative artifact: `layer_b_symbolic.json`.

## EPIC 5: Rule-Based Event Detection

Goal: define the canonical event contract, infer musically meaningful event windows, support review and benchmarking, and export compact event timelines for downstream lighting logic.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 5.1 | Event vocabulary and schema | `event_vocabulary.json` and `song_event_schema.json` | `docs/audio-inference/5.1.event_vocabulary_and_schema_story.md` |
| 4.4 | Event feature normalization and timeline alignment | `event_inference/features.json` and helper indices such as `event_inference/timeline_index.json` | `docs/audio-processing/4.4.event_feature_normalization_story.md` |
| 5.2 | Rule-based baseline event detection | `event_inference/rule_candidates.json` | `docs/audio-inference/5.2.rule_based_event_detection_story.md` |
| 4.5 | Song identifier inference and physical transient audit | `energy_summary/hints.json` with event-level audit metadata | `docs/audio-inference/4.5.song_identifier_inference_story.md` |
| 5.4 | Advanced musical event classification | `event_inference/events.machine.json` | `docs/audio-inference/5.4.advanced_event_classification_story.md` |
| 5.5 | Confidence, review, and override workflow | `validation/song_events.review.json`, `validation/song_events.review.md`, and `validation/song_events.overrides.json` | `docs/human-curated/5.5.event_review_and_benchmark_story.md` |
| 5.5 | Event benchmarking and genre-sensitive tuning | `validation/event_benchmark.json`, benchmark annotations, and threshold profiles | `docs/human-curated/5.5.event_review_and_benchmark_story.md` |
| 5.6 | LLM-friendly event timeline export | `data/analysis/<Song - Artist>/song_event_timeline.json` and `validation/song_event_timeline.md` | `docs/audio-inference/5.6.event_timeline_export_story.md` |

Representative artifacts: `energy_summary/hints.json`, `event_inference/features.json`, `event_inference/rule_candidates.json`, `event_inference/events.machine.json`, `data/analysis/<Song - Artist>/artifacts/validation/song_events.review.json`, `data/analysis/<Song - Artist>/song_event_timeline.json`, `validation/event_benchmark.json`.

## EPIC 6: ML-Based Event Classification

Goal: Classify events from multi-modal feature streams with explainability.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 5.3 | 1D-CNN Event Classifier with Penalty Logic | `1d_cnn_v1.pth` trained with physical constraints | `docs/audio-inference/5.3.ml_event_classifier_and_training_story.md` |
| 5.9 | ML classification with physical-constraint penalty logic | training and inference penalty metadata with reproducibility controls | `docs/audio-inference/5.9.ml_classification_penalty_logic_story.md` |
| 5.3 | 1D-CNN training and dataset generation | `models/event_classifier/1d_cnn_v1.pth` and `models/event_classifier/metadata.json` | `docs/audio-inference/5.3.ml_event_classifier_and_training_story.md` |
| 1.5 | Unified perceptual embedding | `layer_perceptual_embedding.json` and `layer_musical_signature.json` | `docs/audio-inference/1.5.unified_perceptual_embedding_story.md` |

## EPIC 7: Lighting Score Generation

Goal: derive recurring harmonic pattern structure as Layer D, project compact UI-facing beat and section outputs, consolidate the upstream layers into a single handoff artifact, then translate that artifact into lighting behavior and a human-readable lighting score.

Layer D covers repeated harmonic progression structure. Motif-level and phrase-level repetition summaries remain part of the symbolic layer.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 2.3 | Find chord patterns | `pattern_mining/chord_patterns.json` and `layer_d_patterns.json` | `docs/audio-processing/2.3.find_chord_patterns_story.md` |
| 7.2 | Build UI data | `data/analysis/<Song - Artist>/beats.json` and `data/analysis/<Song - Artist>/sections.json` | `docs/web-ui/7.2.build_ui_data_story.md` |
| 7.1 | Unified music feature layer assembly | `music_feature_layers.json` and documented helper outputs | `docs/lighting-score/7.1.music_feature_layers_story.md` |
| 7.3 | Feature-to-lighting mapping | fixture-agnostic `lighting_events.json` and mapping logic | `docs/lighting-score/7.3.energy_to_lighting_mapping.md` |
| 7.4 | Fixture-aware orchestration | fixture-aware events with stable-role and event-overlay logic, plus `lighting_score.md` | `docs/lighting-score/7.4.fixture_aware_mapping_story.md` |
| 7.5 | BeatDrop offline visualizer export | deterministic offline preset windows and transition schedule in `beatdrop_visual_plan.json` | `docs/web-ui/7.5.beatdrop_offline_visualizer_export_story.md` |

Representative artifacts: `layer_d_patterns.json`, `data/analysis/<Song - Artist>/beats.json`, `data/analysis/<Song - Artist>/sections.json`, `music_feature_layers.json`, `lighting_events.json`, `lighting_score.md`, `data/analysis/<Song - Artist>/beatdrop_visual_plan.json`.

## EPIC 8: Internal Artifact Debugger and Regression Viewer

Goal: provide an internal web debugger for inspecting generated inferences, timing alignment, and validation surfaces without changing the stable downstream output contract. Generated artifacts and outputs remain read-only; Story 8.8 adds an explicit reference-human-hints editing surface.

The debugger is an internal engineering and review tool. Its primary inspection surface is `data/analysis/<Song - Artist>/artifacts/`. It may also read compact helper projections from `data/analysis/<Song - Artist>/`, but it must not write debugger state or exported files into either tree. The only allowed persisted edit is `data/analysis/<Song - Artist>/reference/human/human_hints.json`.

| Story | Intent | Primary outputs | Detailed spec |
| --- | --- | --- | --- |
| 8.1 | Song auto-discovery and artifact entry | discovered song-directory selection and artifact entry shell | `docs/web-ui/8.1.song_auto_discovery_and_artifact_entry_story.md` |
| 8.2 | Master sync and waveform anchor | debugger playback shell and shared timeline clock | `docs/web-ui/8.2.master_sync_and_waveform_anchor_story.md` |
| 8.3 | DAW-style lane architecture | shared lane layout, zoom, filtering, and scroll sync | `docs/web-ui/8.3.daw_style_lane_architecture_story.md` |
| 8.4 | Sparse data lanes | section, chord, pattern, and event-region lanes | `docs/web-ui/8.4.sparse_data_lanes_story.md` |
| 8.5 | High-density lanes | drum, density, and energy renderers | `docs/web-ui/8.5.high_density_lanes_story.md` |
| 8.6 | Semantic zoom and performance guardrails | clustering, zoom floors, and viewport-limited rendering | `docs/web-ui/8.6.semantic_zoom_and_performance_story.md` |
| 8.7 | Regression validation overlay | beat-grid, drift, and validation comparison overlays | `docs/web-ui/8.7.regression_validation_overlay_story.md` |
| 8.8 | Human hint editor | explicit editing of reference human hints in the helper UI | `docs/web-ui/8.8.human_hint_editor_story.md` |
| 8.9 | Identifier and ML event lanes | read-only debugger lanes for rule identifier hints and ML event predictions | `docs/web-ui/8.9.identifier_and_ml_event_lanes_story.md` |

Representative implementation assets: `/ui/`, the Compose `ui` service, debugger access to `layer_a_harmonic.json`, `layer_b_symbolic.json`, `layer_c_energy.json`, `layer_d_patterns.json`, `event_inference/*.json`, `validation/phase_1_report.json`, `music_feature_layers.json`, and the editable reference file `data/analysis/<Song - Artist>/reference/human/human_hints.json`.

## Canonical Artifact Flow

The expected high-level artifact dependency chain is:

1. Source song in `data/songs/`.
2. Stem outputs in `data/analysis/<Song - Artist>/artifacts/stems/`.
3. Timing, harmonic, symbolic, and energy artifacts in `data/analysis/<Song - Artist>/artifacts/`.
4. Event-inference artifacts in `data/analysis/<Song - Artist>/artifacts/event_inference/` and identifier hints in `data/analysis/<Song - Artist>/artifacts/energy_summary/hints.json`.
5. Review, override, timeline-markdown, and benchmark outputs in `data/analysis/<Song - Artist>/artifacts/validation/`, plus the UI timeline JSON in `data/analysis/<Song - Artist>/song_event_timeline.json`.
6. Pattern-mining outputs in `data/analysis/<Song - Artist>/artifacts/pattern_mining/` and the Layer D file `layer_d_patterns.json` in `data/analysis/<Song - Artist>/artifacts/`.
7. UI-facing `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, `lighting_score.md`, and `beatdrop_visual_plan.json` in `data/analysis/<Song - Artist>/`, plus optional `beatdrop_visual_plan.md`.
8. Unified cross-layer handoff file `music_feature_layers.json` in `data/analysis/<Song - Artist>/artifacts/`.
9. No additional routine files are added to `data/analysis/<Song - Artist>/` beyond the stable UI contract unless a UI contract change makes that strictly required.
10. The internal debugger served from `/ui/` reads `data/analysis/<Song - Artist>/artifacts/` and selected output helper files without writing any new files back into those generated-data directories.

## Required Supporting Documents

- `docs/constitution.md`: high-level project values, coding standards, and architectural principles.
- `docs/layer_manifest.md`: layer-by-layer artifact contract.
- `docs/human-curated/lighting_score_template.md`: stable lighting-score structure.
- `docs/docker_development.md`: container runtime and validation contract.
- `docs/ui_development.md`: internal debugger runtime, folder ownership, and read-only data-access contract.
- `docs/phase_1_validation_cli.md`: first-phase analyzer entry point and reference-comparison contract.

## Lighting-Score-Ready Minimum Artifact Set

Before Story 7.4 can produce a reliable `lighting_score.md`, the implementation should have at minimum:

- canonical beat and bar timing from Story 1.2 with per-beat time, 1-indexed bar, and beat-in-bar indices
- `data/analysis/<Song - Artist>/artifacts/section_segmentation/sections.json` with stable section IDs and exact section windows
- `data/analysis/<Song - Artist>/artifacts/layer_b_symbolic.json` with `motif_summary.dominant_motif_id`, `motif_summary.motif_groups[]`, and `motif_summary.repeated_phrase_groups[]`
- phrase timing anchors exposed as `phrase_windows[]` or normalized into `music_feature_layers.json.timeline.phrases[]`
- `data/analysis/<Song - Artist>/artifacts/layer_c_energy.json` with accent windows, energy transitions, peaks, and dips relevant to cue placement
- `data/analysis/<Song - Artist>/song_event_timeline.json` or equivalent reviewed event export when event-aware lighting logic is enabled, with canonical event IDs and exact event windows preserved
- `data/analysis/<Song - Artist>/artifacts/layer_d_patterns.json` with `patterns[].id` and occurrence windows using `start_s` and `end_s`
- `data/analysis/<Song - Artist>/artifacts/music_feature_layers.json` with `timeline.phrases[]`, `lighting_context.cue_anchors[]`, `lighting_context.pattern_callbacks[]`, and `lighting_context.motif_callbacks[]`
- fixture-agnostic lighting events from Story 7.3 with `anchor_refs` that point back to section, phrase, motif, pattern, and cue-anchor IDs
- fixture-aware events from Story 7.4, when exported separately, with exact `event_ref`, `role_overlay`, and explicit target metadata for dynamic regroupings such as moving-head unison focus
- `data/fixtures/fixtures.json` so Story 7.4 can translate abstract behavior into fixture-aware instructions

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

1. run against a real song such as `_test_song.mp3`
2. generate inferred analysis artifacts inside `data/analysis/<Song - Artist>/artifacts/`
3. compare inferred chord outputs against human-validated reference chords and compare inferred section change points against validation-only reference segments in `data/analysis/<Song - Artist>/reference/moises/` when they are available
4. validate the generated Story 2.5 drum review artifact for recognizable kick, snare, and hat behavior on `_test_song.mp3` without treating reference data as generation fallback
5. emit a validation summary or report without copying reference values into generated artifacts

Reference files under `data/analysis/<Song - Artist>/reference/` are optional validation inputs. The pipeline must infer chords, sections, and other generated values from the documented analysis stack first. When reference files are present, they may be used to validate or explicitly review those inferred results, but they must not silently replace generated artifact values.

This first-phase validation target is documented in `docs/phase_1_validation_cli.md`.

That supporting document defines the recommended CLI command shape, required flags, exit codes, and the expected machine-readable validation report structure.

The final documentation set must remain internally consistent across story files, schemas, runtime commands, and validation contracts.

## Workspace Cleanup
- Never leave temporary scripts, patching code, or scaffolded one-off files laying around in the workspace. Always clean up after yourself.
