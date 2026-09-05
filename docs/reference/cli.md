# Reference — `./analyze` CLI

`./analyze` and `python -m analyzer` are the same entry point. Everything runs
inside Docker (Docker only).

```bash
docker compose run --rm app ./analyze --song "/data/songs/_test_song.mp3"
```

## Flags

| Flag | Default | Meaning |
| --- | --- | --- |
| `--song` | — | path to the source song; required unless `--all-songs` |
| `--all-songs` | — | analyze every `.mp3` under the songs root, each in its own subprocess |
| `--songs-root` | sibling `songs/` of `--analysis-root` | batch-mode directory override |
| `--analysis-root` | `/data/analysis` | where inferred output is written |
| `--stage` | — | run one stage only; prerequisite artifacts must already exist |
| `--compare` | `beats,chords,drums,sections,drops` | validation targets (see below) |
| `--fail-on-mismatch` | off | exit non-zero when validation thresholds are missed |
| `--beat-tolerance-seconds` | `0.10` | beat-timestamp comparison tolerance |
| `--tolerance-seconds` | ~1–2 bars | section change-point tolerance |
| `--chord-min-overlap` | — | minimum overlap ratio for chord-event comparison |
| `--device` | auto | `cuda` or `cpu`; prefer GPU |
| `--verbose` | off | detailed logging |
| `--clean-generated-data` | — | delete generated per-song directories only; never touches `data/songs/` or `reference/` |

## Compare targets

Only five exist. Passing any other name (`energy`, `events`, `form`,
`patterns`, `unified` — all deleted in v3.0) **fails CLI validation** rather
than silently reporting `skipped`.

| Target | Scores | Against |
| --- | --- | --- |
| `beats` | inferred beat times, over the reference-covered span only | beat times embedded in `reference/moises/chords.json` |
| `chords` | time-aligned chord events and labels | `reference/moises/chords.json` |
| `sections` | structural change points | `reference/moises/segments.json` |
| `drums` | internal consistency: time-ordering, label set (`kick`/`snare`/`hat`/unresolved), summary-count match, MIDI preservation, recorded debug source paths, recognizable backbeat and hat pulse | itself |
| `drops` | detected drop impacts, precision/recall @ 1.0 s, plus a "fake drops don't outnumber real drops" check | timed drop hints in `reference/human/human_hints.json` |

`drops` is **advisory** and never flips the exit code. A song with no timed drop
hints reports `skipped` with a reason — three of the four gold songs today —
rather than a presence-only check that passes by construction.

Reference files are optional: inference always runs, and a missing reference
skips only that target.

## Stages

`--stage <name>`, from `STAGE_PIPELINE_IDS` in
[`../../src/analyzer/pipeline.py`](../../src/analyzer/pipeline.py) — that dict
is authoritative over this list.

| Stage | Id |
| --- | --- |
| `ensure-stems` | 1.1 |
| `extract-timing-grid` / `validate-beats` | 1.2 |
| `extract-fft-bands` | 1.3 |
| `extract-mix-stem-loudness` | 1.4 |
| `extract-hpcp-and-chords` / `validate-chords` | 2.1-2.2 |
| `extract-drum-events` | 2.5 |
| `extract-energy-features` | 2.6 |
| `segment-sections` | 3.1 |
| `derive-energy-layer` | 4.1 |
| `build-gestures` | 5.0 |
| `classify-genre` | 6.1 |
| `generate-section-hints` | 6.2 |
| `build-ui-data` | 7.2 |
| `build-human-hints-alignment` | 8.8 |
| `build-validation-report`, `write-validation-report`, `write-validation-markdown` | validation |

Batch progress lines carry both positions: `[2/20][1.1] _test_song | ensure-stems`.

## Working sequence

1. During implementation, run only the changed stage with `--stage`.
2. At the end of the task, run one full pipeline command without `--stage`.

## Outputs

Always written:

- artifacts under `data/analysis/<Song - Artist>/artifacts/`
- `artifacts/validation/phase_1_report.json` and `.md`
- `artifacts/symbolic_transcription/omnizart/drums.mid` when drums run

When `reference/human/human_hints.json` exists, also
`artifacts/validation/human_hints_alignment.{json,md}` — review-only, never a
replacement for generated output.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | analysis completed, validation within thresholds |
| `1` | analysis completed, validation failed or mismatches exceeded thresholds |
| `2` | invalid CLI usage or configuration |
| `3` | runtime, dependency or artifact-generation failure |

## Report shape

`phase_1_report.json` carries `schema_version`, `song_name`, `command`,
`status`, `exit_code`, `generated_at`, `inputs`, `generated_artifacts`, a
`validation` block per compare target, and `notes`. Each target block has
`status`, `matched`, `mismatched`, `match_ratio` and a target-specific
`diagnostics` object:

| Target | Diagnostics distinguish |
| --- | --- |
| `beats` | global offset vs. local drift vs. residual spread, and the reference beat interval used |
| `chords` | timing-overlap failures vs. label mismatches vs. no-overlap |
| `drums` | time-ordering, summary-count match, recognizable backbeat, hat pulse, over-dense regions |
| `sections` | boundary offset and direction, snap-like boundary count, dominant snap multiple in beats |
| `drops` | tolerance, detected/labelled counts, precision/recall/F1, `fake_outnumbers_drop`, or `mode: "skipped"` with a reason |

## The rule that governs all of it

**The analyzer never rebuilds a canonical artifact from `reference/`.**
`essentia/beats.json` and `layer_a_harmonic.json` are always the pipeline's own
output. The v2.1 takeover that substituted a Moises-derived grid — and its
`beats_inferred.json`, `layer_a_harmonic.inferred.json` and
`generate-timing-diagnosis` stage — is gone. `reference/` is validation-only.
