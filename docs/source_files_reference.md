# Source Files Reference (LLM Navigation Guide)

> **AI / LLM INSTRUCTIONS:**
> - **READ:** Consult this guide to locate codebase components instead of brute-force searching the `src/` directory.
> - **UPDATE:** If you create new files, rename directories, or refactor code boundaries, you **MUST** update this file immediately to keep the codebase map accurate for future interactions.

This guide maps `src/` for the `ai-light-song-v2` analyzer pipeline as it
stands after the v3.0 cleanup
([`implementation-plan-v3.0.md`](implementation-plan-v3.0.md)). It describes
the surviving tree only — this release deleted roughly 6,000 lines (the ML
event stack, `event_benchmark.py`, `unified.py`, `patterns.py`, symbolic note
transcription, the old `sections/` segmenter, and the whole `event_*` chain).
See [`CLAUDE.md`](../CLAUDE.md) "Current state" for what replaced them and how
each replacement is measured, and `git log --diff-filter=D --name-only` for
the deleted files themselves.

There is no epic numbering here any more — the four-phase model in
[`constitution.md`](constitution.md) §5 (measure / interpret / relate /
publish) is the organizing idea, not a list of historical epics.

---

## 1. Core execution & architecture

| File | Purpose |
| --- | --- |
| `src/analyzer/cli.py` | CLI entrypoint for `analyze` / `python -m analyzer`. Parses `--song`, `--all-songs`, `--stage`, `--compare`, etc. |
| `src/analyzer/pipeline.py` | The pipeline DAG. `STAGE_PIPELINE_IDS` is the **authoritative** stage list — start here, ahead of any prose, to understand execution order. |
| `src/analyzer/allin1_cache.py` | Shared, cache-aware All-In-One invocation. `stages/segmentation.py` (3.1) and `stages/timing.py`'s downbeat-phase derivation (1.2) both need allin1's output; this module runs it once per song, seeded with the pipeline's own stems, and persists it to `artifacts/allin1/raw.json` so neither caller re-runs the model. |
| `src/analyzer/__init__.py` | Analyzer package runtime defaults (TensorFlow allocator, GPU growth env settings). |
| `src/analyzer/models.py` | Data structures, JSON-encodable utilities, `SCHEMA_VERSION`. |
| `src/analyzer/io.py` | Disk operations (JSON read/write, file validation). |
| `src/analyzer/paths.py` | `SongPaths` — centralized resolution of `/data/songs/`, `/data/analysis/`, per-song `reference/`, `artifacts/`, etc. |
| `src/analyzer/exceptions.py` | `AnalysisError`, `DependencyError`. |
| `src/analyzer/config.py` | CLI-facing configuration (compare targets, defaults). |

---

## 2. Contracts and schemas

| Location | Purpose |
| --- | --- |
| `src/analyzer/contracts/` | JSON schema/vocabulary documentation. Nothing in `src/` loads these at runtime any more — `event_contracts.py`, their only reader, was deleted with the rest of the Epic-5 event stack — so they now serve as documentation only. |
| `contracts/song_event_schema.json` | The gesture-phase / section-transition event shape (`type`, `start_time`, `end_time`, `confidence`, `intensity`, `section_id`, `section_name`, `provenance`, `summary`, `evidence_summary`). |
| `contracts/event_vocabulary.json` | The current event vocabulary: gesture phases (`approach`, `build`, `tension`, `impact`, `release`) plus section-pair transitions. |

---

## 3. Pipeline stages (`src/analyzer/stages/`)

No stage lives in a subdirectory any more — every stage that used to be
refactored into a submodule for line-count reasons was either deleted with its
subject or is now a single file. `validation/` is the one surviving package,
split by validation domain.

### Phase 1 — measure (audio in, facts that cannot be musically wrong)

| File | Purpose |
| --- | --- |
| `stems.py` | Demucs stem separation (bass, drums, harmonic, vocals), seeded for determinism. Feeds every later stage. |
| `timing.py` | The canonical beat grid: essentia beat *times* (trusted, unchanged since before v3.0) plus, as of v3.0 item 8, the downbeat *phase* derived from allin1's `downbeat` frame activation (via `allin1_cache`) instead of a fixed modulo. Per-downbeat `confidence`, `null` where the two trackers disagree by a whole beat or more. See the module's own docstring for the phase-selection algorithm and `CLAUDE.md` for the honest F1 shortfall. |
| `fft_bands.py` | Seven fixed spectral bands sampled every 50 ms. |
| `loudness.py` | RMS loudness (10 ms) and the slower loudness envelope (200 ms), per source (mix + stems). |

### Phase 2 — interpret (phase 1 + audio, claims that can be musically wrong)

| File | Purpose |
| --- | --- |
| `harmonic.py` | HPCP extraction, global key estimate, chord decoding. Trusted DSP; as of v3.0 item 13 it also projects a compact `key` / `chord_progression` pair into top-level `sections.json`, confidence-gated. |
| `drums.py` | Omnizart drum-hit transcription on the isolated drums stem → `symbolic_transcription/drum_events.json`. Owns `resolve_omnizart_drum_model_path` and the beat/section alignment helpers moved in from the deleted `symbolic/` package in item 6. |
| `genre.py` | Genre/style classification with honest confidences and `guidance` prose. |
| `segmentation.py` | **New in v3.0 (item 7).** Named functional segmentation from All-In-One, seeded with the pipeline's own stems via `allin1_cache`. Replaces the deleted `stages/sections/`. Merges 8-bar phrase segments into song-form section runs, computes `function_confidence` from posterior entropy, flags degenerate songs `function_status: "unknown"`, and sets `same_label_as` for label repetition. See the module docstring for the merge algorithm and measured numbers. |
| `energy.py` | Energy-feature computation and `layer_c_energy.json`. As of v3.0 item 12 the 4 MB/song `energy_summary/features.json` intermediate is computed in memory and never written to disk — only the small, debugger-facing `layer_c_energy.json` is. |

### Phase 3 — relate (phase 2 only, never audio)

| File | Purpose |
| --- | --- |
| `gestures.py` | **New in v3.0 (item 9).** Replaces the whole Epic-5 `event_*` chain. Reads only phase-1/2 artifacts (`fft_bands.json`, `rms_loudness.json`, `drum_events.json`, `beats.json`, `section_segmentation/sections.json`) and assembles named sound-design primitives (riser, downlifter, reverse cymbal, snare roll, pre-drop gap, impact) into gesture phases (`approach`/`build`/`tension`/`impact`/`release`) anchored on a detected impact, plus one event per section-pair transition. Never names a drop directly (constitution §5.2). |
| `hint_alignment.py` | `find_primary_section` — the shared window→section overlap matcher used by both `hints.py` (merging human hints) and the human-hints alignment review artifact. |

### Phase 4 — publish

| File | Purpose |
| --- | --- |
| `hints.py` | Builds `hints.json`: generated inference hints (a handful of concrete categories only) merged with `reference/human/human_hints.json` as `source: "human"` hints, keyed by `section_id` via `hint_alignment.find_primary_section`. |
| `ui_data.py` | Packs the artifact-level payloads into the compact top-level deliverables (`sections.json`, `beats.json`, …) that the debugger and, via the MCP server, the authoring model actually read. |

### Validation (orthogonal to the four phases — constitution §5.5)

`validation/` — scoring generated artifacts against `reference/`. Cut to the
targets that compare against real labels or perform a real internal-consistency
check (v3.0 item 10):

| File | Purpose |
| --- | --- |
| `validation/beats.py` | Beat-time and downbeat-phase scoring against `reference/moises/`. |
| `validation/chords.py` | Chord agreement scoring against `reference/moises/chords.json`. |
| `validation/sections.py` | Structural boundary scoring against `reference/moises/segments.json`. |
| `validation/drums.py` | Internal-consistency and plausibility checks on `drum_events.json`. |
| `validation/drops.py` | Timed-only drop-impact scoring against `reference/human/human_hints.json` (renamed from `form_drops.py`; the label-less `form` target was deleted with it). |
| `validation/report.py` | Aggregates the above into `phase_1_report.json` / `.md`. |
| `validation/utils.py` | Shared helpers (bar/beat snapping, `skipped_result()`, …). |

`validation/events.py`, `validation/energy.py`, `validation/unified.py` and
`validation/patterns.py` were deleted with the stages they validated (items 3,
4, 9, 10) — none had a real subject left.

---

## 4. External model runtimes

| File | Purpose |
| --- | --- |
| `_omnizart_runtime.py` | Subprocess isolation for Omnizart drum transcription (`drums.py`'s only consumer). |

Basic Pitch, its runtime/subprocess wrappers, and the `symbolic/` package that
consumed them were deleted in item 6 — `basic-pitch` is also gone from
`requirements.txt`.

---

## LLM workflow tips

1. **Changing CLI behaviour:** start at `src/analyzer/cli.py` and `src/analyzer/pipeline.py`.
2. **Fixing a projected JSON shape:** check `src/analyzer/stages/ui_data.py` (the packer) and `src/analyzer/contracts/` (documentation of the shape, not an enforced schema).
3. **Modifying an extraction stage:** every stage is a single file under `src/analyzer/stages/` now; open it directly.
4. **Validating pipeline artifacts:** `src/analyzer/stages/validation/<domain>.py`.
5. **Understanding a stage's own measured numbers:** read its module docstring first — `segmentation.py`, `gestures.py` and `timing.py` all carry their promotion numbers and honest caveats inline, not just in `docs/`.
