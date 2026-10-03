# Reference — map of `src/`

Where each thing lives. **Update this file in the same change that moves code.**
`STAGE_PIPELINE_IDS` in [`../../src/analyzer/pipeline.py`](../../src/analyzer/pipeline.py)
is authoritative over any prose here.

Stage responsibilities and their measured quality:
[`../analysis-definition.md`](../analysis-definition.md).

## `mcp/` — the song-comprehension server

A separate top-level module beside `src/`. **`src/` never imports from `mcp/`,
and `mcp/` never imports from `src/`** — the only channel between them is the
top-level `data/analysis/{song}/*.json` files.

| File | Purpose |
| --- | --- |
| `mcp/server.py` | stdio MCP server entry point — registers the twelve tools (`list_songs`, `get_song_overview`, `get_detail`, `propose_hint`, `request_analysis`, `get_analysis_progress`, `get_watcher_status`, `get_structure_hint_brief`, `write_structure_hint`, `get_verdict_brief`, `write_verdict_pass`, `write_verdict_check`) and the `structure_hint` / `verdict_pass` prompts |
| `mcp/structure_hint.py` | v3.10 item 7 — the structure-hint brief (one text for the tool and the `structure_hint` prompt), strict schema-1.0 validator (rejects time-bearing keys) and the single bounded write of `reference/pre-analysis/structure.json` |
| `mcp/verdict.py` | v3.11 item 23 — second-pass brief (one text for `get_verdict_brief` and the `verdict_pass` prompt), the pass / check validators and the single bounded write of `verdict.json`'s `second_pass` block; the `verdict_check` queue helpers (`append_verdict_check`, `find_verdict_checks`) are in `mcp/proposals.py` |
| `mcp/loaders.py` | song discovery, top-level file access, exposure enforcement (no code path reaches an inner folder) — the *stable* half |
| `mcp/serializers.py` | response shaping for `get_song_overview` / `get_detail` — the *volatile* half; a tool-surface reshape touches this file and its snapshots only |
| `mcp/tests/run.py` | `smoke-test` / `full-regression` named entry points |
| `mcp/tests/fixtures/build_fixtures.py` | deterministic generator for the three committed regression fixtures |
| `mcp/tests/` | exposure guard, scaffold checks, tool-surface checks, committed fixtures |

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
| 1 | `fft_bands.py` | 7 spectral bands / 50 ms — five artifacts: the mix (`fft_bands.json`) plus one per Demucs stem (`fft_bands.{bass,drums,harmonic,vocals}.json`), each normalised against its own percentiles; a missing stem WAV raises `DependencyError` |
| 1 | `loudness.py` | RMS (10 ms) and envelope (200 ms), per source |
| 1 | `harmonic_spectrum.py` | `extract-harmonic-spectrum` (v3.12 item 32; port of `experiments/filter_sweep_v2`) — half-beat log-frequency spectrum of the harmonic stem (`hl_db`, `roll_hz`, `peak_hz`); runs after `publish-arrangement-state`, reads the published `beats.json` |
| 2 | `kick_attacks.py` | `detect-kick-attacks` (v3.12 item 32; port of `experiments/kick_attacks`) — kick attacks on the mix audio with echo and off-grid rules, plus `window_counts` (the `kick_present` rule); reads the published `beats.json` |
| 2 | `drums.py` | Omnizart drum transcription on the drums stem (GM 35/38/42); owns `resolve_omnizart_drum_model_path`, the beat/section alignment helpers, and the v3.4 `crash`/`hat` split on pitch 42 — reads `essentia/fft_bands.drums.json`, raises `DependencyError` if absent |
| 2 | `segmentation.py` | All-In-One named segmentation; merges 8-bar phrases into song-form runs, computes `function_confidence` from posterior entropy, flags degenerate songs `function_status: "unknown"`, sets `same_label_as` |
| 3 | `light_changes.py` | `light-changes` (v3.12 item 32; port of `experiments/bar_features`, `experiments/light_changes` and the sweep state of `filter_sweep_v2`) — per-bar table, change-point walk with roles, sweep-ramp onsets, half-beat point time snapped to the beat grid; writes `artifacts/light_changes/{bar_features,light_changes}.json`. Never reads audio: needs `kick_attacks.py` and `harmonic_spectrum.py` first |
| 3 | `gestures.py` | named primitives → gesture phases anchored on a detected impact, plus one event per section-pair transition. Reads phase-1/2 artifacts plus the PUBLISHED `sections.json` (v3.7 item 6 — was allin1's raw `artifacts/section_segmentation/sections.json`; runs after `build-ui-data` for this reason), never audio |
| 3 | `hint_alignment.py` | `find_primary_section` — the shared window→section matcher used by `hints.py` and the alignment review artifact |
| 4 | `hints.py` | `hints.json`: human hints from `reference/human/human_hints.json`, `section_id` attributed by timestamp against the PUBLISHED `sections.json` (v3.7 item 6 — was allin1's raw artifact segmentation; runs after `build-ui-data` for this reason) |
| 4 | `ui_data.py` | packs the compact top-level deliverables |
| 4 | `vocal_cadence.py` | `publish-vocal-cadence` (v3.9 item 1) — `vocal_cadence.json`: per-line bar timing, per-section `lead_in_bars`/rests/held notes/tokens-per-bar/cadence-repeats, calls. Reads `reference/human/lyrics.json` > `reference/moises/lyrics.json` (D1.1: neither present → still writes the file, `source: null` + `reason`) plus the PUBLISHED `beats.json`/`sections.json`/`info.json`. Timing only — no lyric text past parsing. Ported from `experiments/vocal_cadence/` (12/12 on Queen of Kings), never imported from it |
| 4 | `version_check.py` | `version-check` (v3.11 item 21) — runs after `info.json`; compares `reference/pre-analysis/structure.json` (`track.version_duration_s`, `genre.bpm`) with `info.json` (`duration` > 5 s apart, `bpm` > 3 % apart with half/double time equal; a null is not a mismatch) and writes the `version_check` block of `reference/pre-analysis/verdict.json`. No hint → writes nothing. Reads no audio; nothing else reads the block yet |
| 4 | `hint_verdict.py` | `hint-verdict` (v3.11 item 22) — runs right after `version-check`; judges each non-null `shape` field and `genre.bpm` of the hint against the published `sections.json` (`Drop` / `Extended Drop` runs, drop-like `Chorus` for `pop_edm`, `Build-Up`), `arrangement_state.json` (`vocals_phrase`, bass/drums `playing`), `loudness.json` and `info.json`, and writes the `verdicts` block of `reference/pre-analysis/verdict.json` (`confirmed` / `refuted` / `unresolved`, evidence = section ids and counts). No rows when `version_mismatch`, family not `edm`/`pop_edm`, or a `1.0` hint; no hint -> writes nothing. Preserves `version_check`; changes no other file; nothing reads it |

`segmentation.py`, `gestures.py` and `timing.py` carry their promotion numbers
and honest caveats **in their own module docstrings** — read those first.

## Validation

Orthogonal to the four phases (validation observes every phase; it is not a stage in the sequence).

| File | Scores |
| --- | --- |
| `validation/beats.py` | beat times and downbeat phase vs. `reference/moises/` |
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
| `_omnizart_drum_runner.py` | subprocess entry point `drums.py` runs; patches vendored omnizart's `predict()`, whose `pred[:-pad_size]` returns nothing when `pad_size == 0` (a stem whose mini-beat count fills whole batches: Charli-VonDutch, ayuni) |

## Host scripts (outside `src/`)

| File | Purpose |
| --- | --- |
| `analysis-watcher.service` (repo root) | v3.10 item 11 — systemd user unit (`Restart=on-failure`) running `./analysis-watcher --foreground`; enabling it is documented in `docker.md` |
| `analysis-watcher` (repo root) | v3.8 item 1 — bash, runs on the host (never in a container, D1.2). Polls `data/analysis/*/artifacts/_run_request.json`; on a never-analysed song runs `./analyze --stage ensure-stems` (whisperX needs the vocal stem it produces — D1.1, corrected by the host end-to-end smoke) then `whisperx` then the full `./analyze`, all via `docker compose run` on the operator's behalf, writing `_run_progress.json`, and rewriting `data/analysis-watcher.heartbeat` every poll (v3.10 item 11; `get_watcher_status` reads it). Its `KNOWN_STAGES` list must equal `STAGE_PIPELINE_IDS`' keys in `pipeline.py` — `tests/test_analysis_watcher.py` asserts this |

## Where to start

| Task | Open |
| --- | --- |
| Change CLI behaviour | `cli.py`, then `pipeline.py` |
| Fix a projected JSON shape | `stages/ui_data.py` (the packer), then `contracts/` |
| Modify an extraction stage | the single file under `stages/` |
| Add or change validation | `stages/validation/<domain>.py` |
| Understand a stage's measured quality | its module docstring, then [`../analysis-definition.md`](../analysis-definition.md) |
