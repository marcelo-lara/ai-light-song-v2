# Source Files Reference (LLM Navigation Guide)

> **⚠️ AI / LLM INSTRUCTIONS:**
> - **READ:** Consult this guide to locate codebase components instead of brute-force searching the `src/` directory.
> - **UPDATE:** If you create new files, rename directories, or refactor code boundaries, you **MUST** update this file immediately to keep the codebase map 100% accurate for future interactions.

This guide provides an LLM-friendly directory and file reference for the `ai-light-song-v2` analyzer pipeline. Use this document to quickly locate logical components, core utilities, and pipeline stages without brute-force searching the `src/` directory.

---

## 1. Core Execution & Architecture

| File | Purpose |
|------|---------|
| `src/analyzer/cli.py` | Primary CLI entrypoint for the `analyze` command. Parses arguments (`--song`, `--all-songs`, etc.). |
| `src/analyzer/pipeline.py` | The Pipeline DAG. Maps the 8 Epics and orchestrates exactly when and how each `src/analyzer/stages/` function is executed. |
| `src/analyzer/models.py` | Data structures, JSON encodable utilities, and the overarching `SCHEMA_VERSION`. |
| `src/analyzer/io.py` | Disk operations (JSON read/write, file validation). |
| `src/analyzer/paths.py` | Centralized `SongPaths` resolution (managing references to `/data/songs/`, `/data/artifacts/`, `/data/reference/`, etc.). |
| `src/analyzer/exceptions.py`| Custom exceptions (`AnalysisError`). |

---

## 2. Contracts and Schemas

All formalized output schemas used by the timeline UI and lighting engines.

| Location | Purpose |
|----------|---------|
| `src/analyzer/contracts/` | Directory holding all core JSON schemas. |
| `[...]/song_event_schema.json`| Schema defining the unified abstract events. |
| `[...]/event_vocabulary.json` | Dictionary and mappings for event tags and parameters. |
| `src/analyzer/event_contracts.py`| Python validation wrappers enforcing payloads against the JSON schemas. |

---

## 3. Pipeline Stages (`src/analyzer/stages/`)

The pipeline logic is distributed across various modules mapping directly to the narrative stories in `docs/*.story.md`. 
*Note: Large monolithic stages (>300 lines) have been aggressively refactored into focused subdirectories.*

### Submodules (Refactored Stages)
These features are complex and have been broken into sub-directories to maintain the `<200` lines-per-file constraint.
Each submodule exports its main generator function out of its `__init__.py`.

* **`event_features/`** (Epic 4) 
  * `builder.py` – Constructs the dense continuous event feature layer.
  * `resampler.py` – Signal alignment and interpolation.
  * `timeline.py` / `utils.py` – Math and window utilities.
* **`event_machine/`** (Epic 5)
  * `generator.py` – Generates deterministic, pattern-based synthetic events.
* **`event_rules/`** (Epic 5)
  * `generator.py` – Generates algorithmic rule-based baseline events.
* **`sections/`** (Epic 3)
  * `segmenter.py` – Infers song structural boundaries (`intro`, `verse`, `drop`).
* **`symbolic/`** (Epic 2)
  * `generator.py` – Computes musical abstraction layers from parsed stem symbolic notes.
* **`validation/`** (Validation Epic)
  * Extensive post-pipeline verification. Split by domain to prevent large monolithic validation loops.
  * Domains: `beats.py`, `chords.py`, `drums.py`, `energy.py`, `events.py`, `patterns.py`, `sections.py`, `unified.py`.
  * `report.py` – Aggregates diagnostics into the Markdown/JSON artifact reports.

### Standard Modules (Single Files)
* `stems.py` / `fft_bands.py` / `timing.py` / `loudness.py` (Epic 1) – Audio ingestion, demux, downsampling, grid extraction.
* `drums.py` / `harmonic.py` / `genre.py` (Epics 2 & 6) – Model-based musical extraction and classifications.
* `ui_data.py` (Epic 7) – Packs intermediate JSON payloads into the finalized web deployment structure.
* `lighting.py` / `light_design.py` (Epic 7) – Maps timing, energy, and semantic events into DMX/fixture commands.

---

## 4. Machine Learning & Training
* **Subprocess execution layers**: `_basic_pitch_subprocess.py`, `_omnizart_runtime.py`, `_stem_activity.py` encapsulate isolation logic for external Python ML environments.
* **Event Classifier**: `src/analyzer/event_ml_models.py`, `event_ml_train.py` and `src/scripts/train_event_classifier.py` house the PyTorch/TensorFlow graphs and logic for training custom event recognizers.

---

## LLM Workflow Tips

1. **Changing CLI Behavior**: Start at `src/analyzer/cli.py` and `src/analyzer/pipeline.py`.
2. **Fixing JSON Shapes**: Inspect `src/analyzer/event_contracts.py` + `src/analyzer/contracts/`.
3. **Modifying an Extraction Stage**: Check `src/analyzer/stages/`. If the stage is a directory, limit cross-file imports and edit `<stage>/generator.py` and `<stage>/utils.py`.
4. **Validating Pipeline Artifacts**: Navigate directly to `src/analyzer/stages/validation/<domain>.py`.
