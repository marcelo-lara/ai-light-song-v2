# EPIC 5 — Musical Event Vocabulary, Inference, Review, and Export

## Goal

Create a repeatable pipeline that detects, annotates, reviews, and exports musically meaningful song events for AI lighting generation.

## Scope

This epic covers:

- canonical event vocabulary and schema contracts
- normalized cross-layer features for event inference
- deterministic baseline event detection and higher-level identifier inference
- ambiguity handling and human review
- benchmark validation and genre-sensitive tuning
- compact event timeline export for downstream lighting generation

## Canonical Vocabulary Seed

The initial canonical vocabulary remains:

- `build`
- `breakdown`
- `drop`
- `drop_explode`
- `drop_groove`
- `drop_punch`
- `soft_release`
- `no_drop_plateau`
- `fake_drop`
- `tension_hold`
- `pause_break`
- `anthem_call`
- `call_response`
- `hook_phrase`
- `energy_reset`
- `layer_add`
- `layer_remove`
- `impact_hit`
- `stinger`
- `groove_loop`
- `atmospheric_plateau`

## Delivery Plan

### Phase 1 — Contracts and Feature Readiness

## Story 5.1 — Event vocabulary and schema

Define the canonical event list, descriptions, categories, aliases, and validation schema so later stories can emit one stable event contract.

Primary outputs:

- `event_vocabulary.json`
- `song_event_schema.json`

## Story 5.2 — Event feature normalization and timeline alignment

Normalize loudness, onset, spectral, symbolic, and section-derived evidence onto a shared time base so event logic can combine layers deterministically.

Primary outputs:

- `data/artifacts/<Song - Artist>/event_inference/features.json`

### Phase 2 — Deterministic Event Inference

## Story 5.3 — Rule-based baseline event detection

Implement the first-pass rules engine for obvious transition and sustained-state events, with explicit threshold evidence and optional genre-aware presets.

Primary outputs:

- `data/artifacts/<Song - Artist>/event_inference/rule_candidates.json`

## Story 5.4 — Song identifier inference

Emit controlled named energy-event identifiers such as `drop` from the energy layer and section context, using documented definitions and deterministic evidence requirements.

Primary outputs:

- `data/artifacts/<Song - Artist>/energy_summary/hints.json`

## Story 5.5 — Advanced musical event classification

Refine baseline candidates into drop variants, vocal-driven events, and energy-reset mechanics while preserving parent-label fallbacks for ambiguous cases.

Primary outputs:

- `data/artifacts/<Song - Artist>/event_inference/events.machine.json`

### Phase 3 — Review and Validation

## Story 5.6 — Confidence, review, and override workflow

Expose confidence bands, alternative candidates, and human-editable overrides so event timelines can be corrected without editing raw analysis artifacts.

Primary outputs:

- `data/artifacts/<Song - Artist>/validation/song_events.review.json`
- `data/artifacts/<Song - Artist>/validation/song_events.overrides.json`

## Story 5.7 — Event benchmarking and genre-sensitive tuning

Benchmark the event pipeline on reviewed songs, measure label and timing agreement, and tune optional genre profiles without changing the schema.

Primary outputs:

- `benchmark_annotations/`
- `data/artifacts/<Song - Artist>/validation/event_benchmark.json`

### Phase 4 — Downstream Export and Optional ML

## Story 5.8 — LLM-friendly event timeline export

Export a compact JSON and markdown event timeline with confidence, intensity, short notes, evidence summaries, and optional high-level lighting hints.

Primary outputs:

- `data/output/<Song - Artist>/song_event_timeline.json`
- `data/artifacts/<Song - Artist>/validation/song_event_timeline.md`

## Story 5.9 — Optional ML event classifier and explainability

Train or tune a learned event classifier from reviewed benchmark data and preserve concise explanation artifacts for its decisions.

Primary outputs:

- `models/event_classifier/`
- `data/artifacts/<Song - Artist>/event_inference/events.ml.json`

## Definition of Done

The event system is usable when:

- the canonical vocabulary and schema are stable
- normalized event features are reproducible and aligned on a shared timeline
- obvious events and controlled identifiers can be detected deterministically
- higher-level event classification can fall back safely when evidence is ambiguous
- human review and override flows preserve machine provenance
- benchmark songs can be compared with useful evaluation reports
- the compact event timeline is usable by the lighting-planning pipeline
