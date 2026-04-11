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

- a Python CLI such as `python -m analyzer`
- a repo-root helper such as `./analyze`
- an equivalent scripted entry point documented in the implementation repo

Current implementation status:

- the repository now includes a top-level CLI entry point at `python -m analyzer` and a repo-root helper at `./analyze`
- the module currently covers the first runnable phase-1 slice: stem separation, canonical beat extraction, harmonic inference, symbolic analysis, canonical energy derivation, pattern mining, unified feature assembly, and validation report generation

The exact command name can be chosen by the implementation team, but the interface must be documented and runnable inside Docker.

## Recommended Command Shape

Recommended baseline command:

```bash
./analyze \
  --song "/data/songs/What a Feeling - Courtney Storm.mp3" \
  --reference-root "/data/reference" \
  --compare beats,chords,sections,energy,patterns,unified,events
```

Equivalent Python module form is the supported container entry point:

```bash
python -m analyzer \
  --song "/data/songs/What a Feeling - Courtney Storm.mp3" \
  --reference-root "/data/reference" \
  --compare beats,chords,sections,energy,patterns,unified,events
```

Batch mode analyzes every `.mp3` in `/data/songs` and writes canonical validation reports under each song artifact directory:

```bash
python -m analyzer \
  --all-songs
```

The current batch implementation isolates each song run in a subprocess and reuses the repo-local Demucs cache under `models/demucs/` so long-running Docker validation does not depend on mid-run model downloads or a long-lived parent process.

## Recommended Flags

- `--song`: required absolute or container-relative path to the source song for single-song runs.
- `--all-songs`: analyze every `.mp3` under `/data/songs` or the directory supplied by `--songs-root`.
- `--songs-root`: optional directory override for batch mode. Defaults to the sibling `songs/` directory next to `--artifacts-root`.
- `--artifacts-root`: optional root directory where inferred outputs are written. Defaults to `/data/artifacts`.
- `--reference-root`: optional root directory for validation-only reference files. Defaults to `/data/reference`. If the directory or files are missing, inference must still run and validation for those targets is skipped.
- `--compare`: optional list of validation targets for phase 1. Supported values include `beats`, `chords`, `sections`, `energy`, `patterns`, `events`, and `unified`. Beat validation runs immediately after timing inference and compares inferred beat timestamps against the beat times embedded in `data/reference/<Song - Artist>/moises/chords.json` when that file is available, using only the time span covered by the reference annotation. If that strict Story 1.2 check fails and reference values exist, the pipeline preserves the inferred beat grid separately and promotes a canonical reference-derived beat grid for downstream phases. Other reference-backed targets use comparison files when available; the layer targets run internal consistency checks against generated artifacts. The `events` target validates the Epic 5 event chain across `event_inference/`, review outputs, timeline exports, and benchmark metadata.
- machine-readable and markdown validation reports are always written automatically under `data/artifacts/<Song - Artist>/validation/` as `phase_1_report.json` and `phase_1_report.md`.
- `--fail-on-mismatch`: optional flag causing the command to exit non-zero when validation thresholds are missed.
- `--beat-tolerance-seconds`: optional float for beat-timestamp comparison tolerance. The phase-1 default is `0.10` seconds.
- `--tolerance-seconds`: optional float for section change-point comparison tolerance. The phase-1 default should allow roughly one to two bars of drift.
- `--chord-min-overlap`: optional float defining minimum overlap ratio for chord-event comparison.
- `--device`: optional execution target such as `cuda` or `cpu`, but container validation should prefer GPU when available.
- `--verbose`: optional flag for detailed logging.

## Minimum Required Inputs

- song path or `--all-songs`
- output artifact root
- optional validation flag or reference-song identifier

## Minimum Required Behavior

The phase 1 analyzer must:

1. read the source song from `data/songs/`
2. generate inferred timing, harmonic, and section-related artifacts under `data/artifacts/<Song - Artist>/`
3. compare inferred beat outputs against beat timestamps embedded in `data/reference/<Song - Artist>/moises/chords.json` when that file is available
4. compare inferred chord outputs against `data/reference/<Song - Artist>/moises/chords.json` when that file is available
5. compare inferred section change points against `data/reference/<Song - Artist>/moises/segments.json` when that file is available
6. validate canonical energy, pattern, event, and unified feature artifacts for internal consistency
7. write a validation report under `data/artifacts/<Song - Artist>/validation/`
8. exit with a documented success or failure status

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
- Beat comparisons should use the inferred timing grid produced by Story 1.2, run before downstream stories consume that grid, and evaluate only the reference-covered portion of the timeline.
- If a reference-backed beat comparison fails, downstream stories should use the promoted canonical reference timing grid rather than the failed inferred timing grid, and the report should record that takeover explicitly.
- Section comparisons should use structural change-point alignment. Reference labels may be reported for review but should not control pass/fail.
- Chord comparisons should use time-aligned event comparison and label comparison.

## Recommended Report Contents

- song identifier
- execution timestamp
- tool versions or model versions used
- generated artifact paths
- beat comparison summary
- chord comparison summary
- section comparison summary
- energy-layer internal consistency summary
- pattern-layer internal consistency summary
- event-layer internal consistency summary, including review and timeline export checks
- unified-layer internal consistency summary
- mismatches and confidence notes
- pass/fail summary

## Recommended JSON Report Schema

```json
{
  "schema_version": "1.0",
  "song_name": "What a Feeling - Courtney Storm",
  "command": "python -m analyzer",
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
    "energy_layer_file": "/data/artifacts/What a Feeling - Courtney Storm/layer_c_energy.json",
    "event_machine_file": "/data/artifacts/What a Feeling - Courtney Storm/event_inference/events.machine.json",
    "event_timeline_file": "/data/output/What a Feeling - Courtney Storm/song_event_timeline.json"
  },
  "validation": {
    "beats": {
      "status": "passed",
      "matched": 412,
      "mismatched": 10,
      "match_ratio": 0.98
    },
    "chords": {
      "status": "passed",
      "matched": 42,
      "mismatched": 5,
      "match_ratio": 0.89
    },
    "sections": {
      "status": "passed",
      "matched": 7,
      "mismatched": 0,
      "match_ratio": 1.0
    },
    "events": {
      "status": "passed",
      "machine_events_present": true,
      "review_consistent": true,
      "timeline_consistent": true
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