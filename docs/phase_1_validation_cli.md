# Phase 1 Validation CLI Contract

## Purpose

Define the first executable validation target for the implementation: a CLI-style analyzer entry point that runs on a real song, generates inferred artifacts, and compares those inferred results against validation-only reference data.

## Why This Exists

The repository already defines detailed artifact contracts, but implementation also needs a concrete first checkpoint that proves the pipeline can run on a real song end to end.

For phase 1, that checkpoint should be a developer-facing entry point that can analyze `What a Feeling - Courtney Storm.mp3` and compare its inferred outputs against:

- `data/reference/What a Feeling - Courtney Storm/moises/chords.json`
- `data/reference/What a Feeling - Courtney Storm/moises/segments.json`

## Scope

This first-phase validation target is not the final full product.

Its job is to prove that the pipeline can:

1. accept a real song as input
2. run the required analysis stages in Docker
3. generate inferred artifacts under `data/artifacts/<Song - Artist>/`
4. compare inferred outputs against reference truth sets
5. produce a validation report that developers can inspect

## Entry Point Form

Preferred form: a CLI analyzer.

Acceptable implementations include:

- a Python CLI such as `python -m analyzer.cli`
- an installed command such as `analyzer`
- an equivalent scripted entry point documented in the implementation repo

The exact command name can be chosen by the implementation team, but the interface must be documented and runnable inside Docker.

## Minimum Required Inputs

- song path or song identifier
- output artifact root
- optional validation flag or reference-song identifier

## Minimum Required Behavior

The phase 1 analyzer must:

1. read the source song from `data/songs/`
2. generate inferred timing, harmonic, and section-related artifacts under `data/artifacts/<Song - Artist>/`
3. compare inferred chord outputs against `data/reference/<Song - Artist>/moises/chords.json`
4. compare inferred section outputs against `data/reference/<Song - Artist>/moises/segments.json`
5. write a validation report under `data/artifacts/<Song - Artist>/validation/`
6. exit with a documented success or failure status

## Required Outputs

At minimum:

- inferred artifacts under `data/artifacts/<Song - Artist>/`
- a validation report such as:
  - `data/artifacts/<Song - Artist>/validation/phase_1_report.json`
  - or `data/artifacts/<Song - Artist>/validation/phase_1_report.md`

## Validation Rules

- Reference files must be read-only inputs.
- Reference values must never be copied into generated inference artifacts.
- Comparisons should report agreement, disagreement, and confidence or tolerance when relevant.
- Section comparisons should use time-window overlap and label comparison.
- Chord comparisons should use time-aligned event comparison and label comparison.

## Recommended Report Contents

- song identifier
- execution timestamp
- tool versions or model versions used
- generated artifact paths
- chord comparison summary
- section comparison summary
- mismatches and confidence notes
- pass/fail summary

## Phase 1 Success Criteria

Phase 1 is successful when a developer can run the analyzer in Docker against `What a Feeling - Courtney Storm.mp3` and receive:

1. generated analysis artifacts
2. a comparison report against reference chords and segments
3. enough detail to understand whether the current implementation is improving or regressing

## Out of Scope

- full lighting generation validation
- human-quality creative lighting review
- use of reference data as fallback inference
- final performance tuning across multiple songs