# Reference — map of `src/`

Where each thing lives. **Update this file in the same change that moves code.**
`STAGE_PIPELINE_IDS` in [`../../src/analyzer/pipeline.py`](../../src/analyzer/pipeline.py)
is authoritative over any prose here.

Stage responsibilities and their measured quality:
[`../analysis-definition.md`](../analysis-definition.md).

## Core

| File | Purpose |
| --- | --- |
| `analyzer/cli.py` | CLI entry for `analyze` / `python -m analyzer` |
| `analyzer/pipeline.py` | the stage DAG; `STAGE_PIPELINE_IDS` is the authoritative stage list — **start here** to understand execution order |
| `analyzer/allin1_cache.py` | one cache-aware All-In-One invocation per song, seeded with the pipeline's own stems, persisted to `artifacts/allin1/raw.json`. Both `stages/segmentation.py` (3.1) and `stages/timing.py`'s downbeat phase (1.2) read it, so neither re-runs the model |
| `analyzer/models.py` | data structures, JSON encoding, `SCHEMA_VERSION` |
| `analyzer/io.py` | JSON read/write, file validation |
| `analyzer/paths.py` | `SongPaths` — all `/data/` path resolution |
| `analyzer/config.py` | CLI-facing configuration and compare targets |
| `analyzer/exceptions.py` | `AnalysisError`, `DependencyError`, `UsageError` |
| `analyzer/__init__.py` | runtime defaults (TF allocator, GPU growth) |

## Stages

Every stage is a **single file** under `analyzer/stages/`. `validation/` is the
only surviving package.

| Phase | File | Produces |
| --- | --- | --- |
| 1 | `stems.py` | Demucs separation, seeded |
| 1 | `timing.py` | canonical beat grid; essentia beat *times* plus allin1-derived downbeat *phase* with per-downbeat confidence. Module docstring carries the phase-selection algorithm |
| 1 | `fft_bands.py` | 7 spectral bands / 50 ms |
| 1 | `loudness.py` | RMS (10 ms) and envelope (200 ms), per source |
| 2 | `harmonic.py` | HPCP, global key, chord decoding; projects `key` / `chord_progression` into `sections.json`, confidence-gated |
| 2 | `drums.py` | Omnizart drum transcription on the drums stem; owns `resolve_omnizart_drum_model_path` and the beat/section alignment helpers |
| 2 | `genre.py` | genre classification with honest confidences and `guidance` prose |
| 2 | `segmentation.py` | All-In-One named segmentation; merges 8-bar phrases into song-form runs, computes `function_confidence` from posterior entropy, flags degenerate songs `function_status: "unknown"`, sets `same_label_as` |
| 2 | `energy.py` | `layer_c_energy.json`. Its 4 MB/song feature intermediate is computed in memory and never written |
| 3 | `gestures.py` | named primitives → gesture phases anchored on a detected impact, plus one event per section-pair transition. Reads phase-1/2 artifacts only, never audio |
| 3 | `hint_alignment.py` | `find_primary_section` — the shared window→section matcher used by `hints.py` and the alignment review artifact |
| 4 | `hints.py` | `hints.json`: inference hints merged with `reference/human/human_hints.json` by `section_id` |
| 4 | `ui_data.py` | packs the compact top-level deliverables |

`segmentation.py`, `gestures.py` and `timing.py` carry their promotion numbers
and honest caveats **in their own module docstrings** — read those first.

## Validation

Orthogonal to the four phases (validation observes every phase; it is not a stage in the sequence).

| File | Scores |
| --- | --- |
| `validation/beats.py` | beat times and downbeat phase vs. `reference/moises/` |
| `validation/chords.py` | chord agreement vs. `reference/moises/chords.json` |
| `validation/sections.py` | boundaries vs. `reference/moises/segments.json` |
| `validation/drums.py` | internal consistency and plausibility of `drum_events.json` |
| `validation/drops.py` | timed drop impacts vs. `reference/human/human_hints.json` |
| `validation/report.py` | aggregates into `phase_1_report.{json,md}` |
| `validation/utils.py` | bar/beat snapping, `skipped_result()`, … |

## Contracts

`analyzer/contracts/` is **documentation only** — nothing in `src/` loads it at
runtime since `event_contracts.py` was deleted.

| File | Describes |
| --- | --- |
| `contracts/song_event_schema.json` | the gesture-phase / section-transition event shape |
| `contracts/event_vocabulary.json` | gesture phases (`approach`, `build`, `tension`, `impact`, `release`) plus section-pair transitions |

## External model runtimes

| File | Purpose |
| --- | --- |
| `_omnizart_runtime.py` | subprocess isolation for Omnizart, `drums.py`'s only consumer |

## Where to start

| Task | Open |
| --- | --- |
| Change CLI behaviour | `cli.py`, then `pipeline.py` |
| Fix a projected JSON shape | `stages/ui_data.py` (the packer), then `contracts/` |
| Modify an extraction stage | the single file under `stages/` |
| Add or change validation | `stages/validation/<domain>.py` |
| Understand a stage's measured quality | its module docstring, then [`../analysis-definition.md`](../analysis-definition.md) |
