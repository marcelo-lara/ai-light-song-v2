# Phase 1 Validation CLI Contract

## Purpose

Define the first executable validation target for the implementation: a CLI-style analyzer entry point that runs on a real song, generates inferred artifacts, and compares those inferred results against validation-only reference data.

## Why This Exists

The repository already defines detailed artifact contracts, but implementation also needs a concrete first checkpoint that proves the pipeline can run on a real song end to end.

For phase 1, that checkpoint should be a developer-facing entry point that can analyze `What a Feeling - Courtney Storm.mp3` and compare its inferred outputs against:

- `data/reference/What a Feeling - Courtney Storm/moises/chords.json` when available
- `data/reference/What a Feeling - Courtney Storm/moises/segments.json` when available

Current reference posture:

- the chord reference file is treated as a human-validated comparison target when present
- the segment reference file is treated as structural change-point guidance; its labels may be informative but are not authoritative for pass/fail

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

Current implementation status:

- the repository now includes an initial Python module entry point at `python -m analyzer.cli validate-phase-1`
- the module currently covers the first runnable phase-1 slice: stem separation, canonical beat extraction, harmonic inference, symbolic analysis, canonical energy derivation, pattern mining, unified feature assembly, and validation report generation

The exact command name can be chosen by the implementation team, but the interface must be documented and runnable inside Docker.

## Recommended Command Shape

Recommended baseline command:

```bash
analyzer validate-phase-1 \
  --song "/data/songs/What a Feeling - Courtney Storm.mp3" \
  --artifacts-root "/data/artifacts" \
  --reference-root "/data/reference" \
  --compare chords,sections,energy,patterns,unified \
  --report-json "/data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.json"
```

Equivalent Python module form is acceptable:

```bash
python -m analyzer.cli validate-phase-1 \
  --song "/data/songs/What a Feeling - Courtney Storm.mp3" \
  --artifacts-root "/data/artifacts" \
  --reference-root "/data/reference" \
  --compare chords,sections,energy,patterns,unified \
  --report-json "/data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.json"
```

## Recommended Flags

- `--song`: required absolute or container-relative path to the source song.
- `--artifacts-root`: required root directory where inferred outputs are written.
- `--reference-root`: optional root directory for validation-only reference files. If omitted or if files are missing, inference must still run and validation for those targets is skipped.
- `--compare`: optional list of validation targets for phase 1. Supported values include `chords`, `sections`, `energy`, `patterns`, and `unified`. Reference-backed targets use comparison files when available; the layer targets run internal consistency checks against generated artifacts.
- `--report-json`: required path for the machine-readable validation report.
- `--report-md`: optional human-readable report path.
- `--fail-on-mismatch`: optional flag causing the command to exit non-zero when validation thresholds are missed.
- `--tolerance-seconds`: optional float for section change-point comparison tolerance. The phase-1 default should allow roughly one to two bars of drift.
- `--chord-min-overlap`: optional float defining minimum overlap ratio for chord-event comparison.
- `--device`: optional execution target such as `cuda` or `cpu`, but container validation should prefer GPU when available.
- `--verbose`: optional flag for detailed logging.

## Minimum Required Inputs

- song path or song identifier
- output artifact root
- optional validation flag or reference-song identifier

## Minimum Required Behavior

The phase 1 analyzer must:

1. read the source song from `data/songs/`
2. generate inferred timing, harmonic, and section-related artifacts under `data/artifacts/<Song - Artist>/`
3. compare inferred chord outputs against `data/reference/<Song - Artist>/moises/chords.json` when that file is available
4. compare inferred section change points against `data/reference/<Song - Artist>/moises/segments.json` when that file is available
5. validate canonical energy, pattern, and unified feature artifacts for internal consistency
6. write a validation report under `data/artifacts/<Song - Artist>/validation/`
7. exit with a documented success or failure status

## Required Outputs

At minimum:

- inferred artifacts under `data/artifacts/<Song - Artist>/`
- a validation report such as:
  - `data/artifacts/<Song - Artist>/validation/phase_1_report.json`
  - or `data/artifacts/<Song - Artist>/validation/phase_1_report.md`

## Exit Codes

- `0`: analysis completed and validation passed within the configured thresholds.
- `1`: analysis completed but validation failed or mismatches exceeded configured thresholds.
- `2`: invalid CLI usage, missing required arguments, or invalid configuration.
- `3`: runtime analysis failure, dependency failure, or artifact-generation failure.

## Validation Rules

- Reference files are optional, read-only validation inputs.
- Reference values must never be copied into or overwrite generated inference artifacts.
- The analyzer must infer chord and section outputs from the pipeline even when reference files are available.
- If reference files are present, they may be used for validation, reporting, or explicit review workflows only.
- Comparisons should report agreement, disagreement, and confidence or tolerance when relevant.
- Section comparisons should use structural change-point alignment. Reference labels may be reported for review but should not control pass/fail.
- Chord comparisons should use time-aligned event comparison and label comparison.

## Recommended Report Contents

- song identifier
- execution timestamp
- tool versions or model versions used
- generated artifact paths
- chord comparison summary
- section comparison summary
- energy-layer internal consistency summary
- pattern-layer internal consistency summary
- unified-layer internal consistency summary
- mismatches and confidence notes
- pass/fail summary

## Recommended JSON Report Schema

```json
{
  "schema_version": "1.0",
  "song_id": "What a Feeling - Courtney Storm",
  "command": "analyzer validate-phase-1",
  "status": "passed",
  "exit_code": 0,
  "generated_at": "2026-04-06T00:00:00Z",
  "inputs": {
    "song_path": "/data/songs/What a Feeling - Courtney Storm.mp3",
    "reference_chords": "/data/reference/What a Feeling - Courtney Storm/moises/chords.json",
    "reference_sections": "/data/reference/What a Feeling - Courtney Storm/moises/segments.json"
  },
  "generated_artifacts": {
    "harmonic_layer_file": "/data/artifacts/What a Feeling - Courtney Storm/layer_a_harmonic.json",
    "energy_layer_file": "/data/artifacts/What a Feeling - Courtney Storm/layer_c_energy.json"
  },
  "validation": {
    "chords": {
      "status": "passed",
      "matched_events": 42,
      "mismatched_events": 5,
      "match_ratio": 0.89
    },
    "sections": {
      "status": "passed",
      "matched_sections": 7,
      "mismatched_sections": 0,
      "boundary_tolerance_seconds": 0.50
    }
  },
  "notes": []
}
```

## Phase 1 Success Criteria

Phase 1 is successful when a developer can run the analyzer in Docker against `What a Feeling - Courtney Storm.mp3` and receive:

1. generated analysis artifacts
2. a comparison report against human-validated reference chords and section change points when those files are available
3. enough detail to understand whether the current implementation is improving or regressing
4. a stable CLI command shape that can be reused in Docker-based smoke tests and automation

## Out of Scope

- full lighting generation validation
- human-quality creative lighting review
- use of reference data as fallback inference
- final performance tuning across multiple songs