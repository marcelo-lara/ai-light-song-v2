# ai-light-song-v2

ai-light-song-v2 implements a Docker-first pipeline for turning source songs into structured musical analysis artifacts and fixture-aware lighting guidance.

This repository contains the runnable analyzer, the artifact contracts it emits, the validation rules used to score those artifacts, and the Docker environment used to run the pipeline end to end.

## Scope

The pipeline transforms an input song into progressively richer artifacts:

1. Audio preprocessing creates stems, beats, tempo, and bar alignment.
2. Harmonic analysis extracts key, chords, and harmonic motion.
3. Symbolic analysis extracts note events and higher-level musical descriptors.
4. Energy analysis extracts loudness, brightness, transients, and sections.
5. Pattern mining extracts repeated multi-bar chord progressions into Layer D summaries.
6. UI data projection builds compact beat and section outputs for downstream consumers.
7. Music feature layer assembly merges the upstream layers into a unified handoff artifact for lighting logic.
8. Lighting design translates those artifacts into lighting events and a human-readable lighting score.

## Repository Layout

The repository structure is part of the implementation contract.

- `data/songs/`: source `.mp3` files to analyze.
- `data/stems/`: temporary stem and `.wav` work area generated during preprocessing.
- `data/artifacts/`: intermediate analysis artifacts, layer outputs, merged timeline artifacts, and validation metadata.
- `data/reference/`: validation-only truth data such as chords, sections, lyrics, or beats from external tools. These files are for scoring and comparison only.
- `data/output/`: final generated deliverables such as `info.json`, `lighting_score.md`, and future DMX-ready exports.
- `docs/`: canonical implementation and contract documentation.

## Hard Rules

- Reference data must never be copied into generated outputs as a fallback.
- Reference files are optional. The pipeline must infer outputs from the documented analysis stages first, then compare against reference data only when those files are available.
- The term `reference` is reserved for `/data/reference/` only.
- Generated artifacts inside `data/artifacts/` must be grouped under the producing model or tool when that provenance matters, such as `essentia/`, `moises/`, `section_segmentation/`, `energy_summary/`, or `pattern_mining/`.
- All generated artifacts must come from inference, heuristics, or rule logic.
- All development and validation must run inside the project Docker environment.
- Time values are stored in seconds.
- Bars are 1-indexed.
- Beat-aligned artifacts must use the canonical beat grid from EPIC 1.2.

## Primary Artifacts

The intended contract defines these primary artifacts:

- `info.json`: canonical song metadata, including `song_name`, `bpm`, `duration`, and generated file references, written to `data/output/<Song - Artist>/info.json`.
- `beats.json`: compact UI-facing beat timeline written to `data/output/<Song - Artist>/beats.json`.
- `sections.json`: compact UI-facing section timeline written to `data/output/<Song - Artist>/sections.json`.
- `layer_a_harmonic.json`: chord events, key, cadence, harmonic summaries.
- `layer_b_symbolic.json`: note events, symbolic summaries, contour and density views.
- `layer_c_energy.json`: loudness, onset, centroid, energy sections, accent candidates.
- `layer_d_patterns.json`: repeated multi-bar chord progressions and their occurrences.
- `music_feature_layers.json`: unified cross-layer timeline and downstream lighting handoff artifact.
- `lighting_score.md`: final human-readable lighting design document.

## Documentation Map

- `docs/Implementation_Guide.md`: canonical hub for the full pipeline and repository contracts.
- `docs/phase_1_validation_cli.md`: Phase 1 analyzer CLI specification, command reference, and validation report format.
- `docs/4.1.energy_feature_schema.md`: low-level energy schema.
- `docs/4.2.section_segmentation_story.md`: section inference contract.
- `docs/5.1.find_chord_patterns_story.md`: Layer D chord-pattern detection contract.
- `docs/5.2.build_ui_data_story.md`: compact UI output contract.
- `docs/5.3.music_feature_layers_story.md`: unified layer assembly contract.
- `docs/5.4.energy_to_lighting_mapping.md`: feature-to-lighting mapping contract.
- `docs/5.5.fixture_aware_mapping_story.md`: fixture-aware orchestration and lighting score generation.

Additional story-level specifications under `docs/` define the exact implementation contract for each Epic and story.

## Quick Start

1. **Prerequisites:** Docker with NVIDIA GPU support
2. **Build:** `docker compose build`
3. **Run analyzer from the host shell:**
   ```bash
   docker compose run --rm app \
     python -m analyzer.cli validate-phase-1 \
     --song "/data/songs/YOUR_SONG.mp3" \
     --artifacts-root "/data/artifacts" \
     --report-json "/data/artifacts/YOUR_SONG/validation/phase_1_report.json"
   ```

For detailed CLI options, see [Running the Phase 1 Analyzer](#running-the-phase-1-analyzer) below.

## Development Environment

The repository is Docker-first.

- Use the root `Dockerfile` and `docker-compose.yml` as the canonical local development environment.
- The Docker image is NVIDIA CUDA-enabled.
- The current local development setup uses an `NVIDIA GeForce GTX 1650`, and the container workflow is configured to take advantage of that GPU.
- Validate all tooling and sample-song runs inside the container.
- Do not rely on host-installed Python packages or audio tooling.
- Treat the Docker image as the authoritative developer runtime.

The detailed environment contract lives in `docs/docker_development.md`, the repo root `Dockerfile`, and `docker-compose.yml`.

### Docker Setup

- `Dockerfile`: multi-stage CUDA-based build with `python-base`, `builder`, and `runtime` stages.
- `docker-compose.yml`: defines the `app` service used for interactive development.
- The Compose service builds the `runtime` target, mounts the repository at `/app`, mounts `./data` at `/data`, and requests `gpus: all`.

### Recommended Commands

Build the development image:

```bash
docker compose build
```

Start an interactive shell in the development container:

```bash
docker compose run --rm app
```

Start the long-running development service:

```bash
docker compose up
```

Inside the container:

- application code is available under `/app`
- song inputs and generated artifacts are available under `/data`
- all implementation validation should run from this environment

### Running the Phase 1 Analyzer

Run the Phase 1 analyzer from the host CLI with `docker compose run`. Do not invoke `python -m analyzer.cli` directly on the host.

```bash
docker compose run --rm app \
  python -m analyzer.cli validate-phase-1 \
  --song "/data/songs/What a Feeling - Courtney Storm.mp3" \
  --artifacts-root "/data/artifacts" \
  --reference-root "/data/reference" \
  --compare chords,sections,energy,patterns,unified \
  --report-json "/data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.json" \
  --report-md "/data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.md"
```

**Available compare targets:** `chords`, `sections`, `energy`, `patterns`, `unified`

**CLI flags:**
- `--song`: Required path to source song
- `--artifacts-root`: Required root directory for generated artifacts
- `--reference-root`: Optional root directory for validation reference files
- `--compare`: Comma-separated list of validation targets
- `--report-json`: Required path for machine-readable validation report
- `--report-md`: Optional path for human-readable report
- `--fail-on-mismatch`: Exit non-zero when validation thresholds are missed
- `--tolerance-seconds`: Section boundary tolerance (default: 2.0)
- `--chord-min-overlap`: Minimum overlap ratio for chord comparison (default: 0.5)
- `--device`: Execution device (`cuda` or `cpu`)
- `--verbose`: Enable detailed logging

**Exit codes:**
- `0`: Analysis completed and validation passed
- `1`: Analysis completed but validation failed
- `2`: Invalid CLI usage
- `3`: Runtime analysis failure

## Implementation Priorities

Recommended implementation order:

1. EPIC 1: preprocessing and timing grid.
2. EPIC 4: energy features and section structure.
3. EPIC 2 and EPIC 3: harmonic and symbolic refinement.
4. EPIC 5.1: chord-pattern detection for Layer D.
5. EPIC 5.2: compact UI beat and section outputs.
6. EPIC 5.3: unified music feature layer assembly.
7. EPIC 5.4 and EPIC 5.5: lighting mapping and score generation.

This ordering reduces downstream churn because lighting behavior depends on stable upstream artifact contracts.

## LLM-Friendly Summary

Use this section as the compact machine-readable contract for code-generation or agent workflows.

### System Purpose

Convert songs into structured musical analysis artifacts and then into fixture-aware lighting guidance.

### Input and Output Contract

- Input songs live in `data/songs/`.
- Temporary stems and `.wav` files live in `data/stems/`.
- Intermediate artifacts live in `data/artifacts/<Song - Artist>/`.
- Validation-only truth data lives in `data/reference/<Song - Artist>/`.
- Final outputs live in `data/output/<Song - Artist>/`.

Examples: `data/output/<Song - Artist>/info.json`, `data/output/<Song - Artist>/lighting_score.md`.

Inside `data/artifacts/<Song - Artist>/`, generated files should use producer-scoped folders when relevant. Examples: `data/artifacts/<Song - Artist>/essentia/beats.json`, `data/artifacts/<Song - Artist>/section_segmentation/sections.json`, `data/artifacts/<Song - Artist>/energy_summary/features.json`, `data/artifacts/<Song - Artist>/pattern_mining/chord_patterns.json`.

### Canonical Upstream Layers

- `layer_a_harmonic.json`
- `layer_b_symbolic.json`
- `layer_c_energy.json`
- `layer_d_patterns.json`

### Canonical Unified Handoff Artifact

- `music_feature_layers.json`

This file is the explicit EPIC 5.3 output and the required input to downstream lighting-mapping stories.

### Required Downstream Outputs

- `lighting_events.json` or equivalent DMX-ready event artifact
- `lighting_score.md`

### Non-Negotiable Rules

- Never copy from `data/reference/` into generated artifacts.
- Never create `reference/` subfolders under `data/artifacts/`.
- Do not keep future generated chord, section, or feature artifacts at flat top-level artifact paths when a producer namespace is known.
- Always align time-based outputs to the canonical beat and bar grid when the story requires it.
- Keep all artifact paths and `generated_from` metadata explicit.
- Keep schemas versioned.
- Validate all implementation inside Docker with NVIDIA GPU support available.

### Developer Intent

This repository is not a loose note dump. It is the implemented analyzer and the contract source for its emitted artifacts.
