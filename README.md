# ai-light-song-v2

ai-light-song-v2 implements a Docker-first pipeline for turning source songs into structured musical analysis artifacts and fixture-aware lighting guidance.

This repository contains the runnable analyzer, the artifact contracts it emits, the validation rules used to score those artifacts, the internal read-only artifact debugger, and the Docker environment used to run the pipeline end to end.

## Scope

The pipeline transforms an input song into progressively richer artifacts:

1. Audio preprocessing creates stems, beats, tempo, and bar alignment.
2. Audio preprocessing also creates a seven-band FFT inspection artifact for debugger spectral review.
3. Harmonic analysis extracts key, chords, and harmonic motion.
4. Symbolic analysis extracts note events and higher-level musical descriptors.
5. Energy analysis extracts loudness, brightness, transients, and sections.
6. Pattern mining extracts repeated multi-bar chord progressions into Layer D summaries.
7. UI data projection builds compact beat and section outputs for downstream consumers.
8. Music feature layer assembly merges the upstream layers into a unified handoff artifact for lighting logic.
9. Lighting design translates those artifacts into lighting events and a human-readable lighting score.
10. An internal debugger served from `/ui/` visualizes generated inferences directly from `data/artifacts/<Song - Artist>/` without writing back into generated-data folders.

## Repository Layout

The repository structure is part of the implementation contract.

- `data/songs/`: source `.mp3` files to analyze.
- `data/stems/`: temporary stem and `.wav` work area generated during preprocessing.
- `data/artifacts/`: intermediate analysis artifacts, layer outputs, merged timeline artifacts, and validation metadata.
- `data/reference/`: validation-only truth data such as chords, sections, lyrics, or beats from external tools. These files are for scoring and comparison only.
- `data/output/`: stable UI-facing deliverables. Each per-song directory must contain exactly `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, and `lighting_score.md`.
- `docs/`: canonical implementation and contract documentation.
- `ui/`: internal artifact-debugger application and UI-specific container files.

## Hard Rules

- **Constitution:** All development must adhere to the laws defined in `docs/constitution.md`.
- **Living Documentation:** No task is "done" until the corresponding Story files and documentation are updated to reflect the final implementation.
- Reference data must never be copied into generated outputs as a fallback.
- Reference files are optional. The pipeline must infer outputs from the documented analysis stages first, then compare against reference data only when those files are available.
- The term `reference` is reserved for `/data/reference/` only.
- Generated artifacts inside `data/artifacts/` must be grouped under the producing model or tool when that provenance matters, such as `essentia/`, `moises/`, `section_segmentation/`, `energy_summary/`, or `pattern_mining/`.
- All generated artifacts must come from inference, heuristics, or rule logic.
- All development and validation must run inside the project Docker environment.
- Time values are stored in seconds.
- Bars are 1-indexed.
- Beat-aligned artifacts must use the canonical beat grid from EPIC 1.2.
- `data/output/<Song - Artist>/` is a stable UI contract, not an open-ended export area.
- Do not add or remove files under `data/output/<Song - Artist>/` unless a UI contract change makes that strictly required.
- The internal debugger is read-only against generated data and must not write files into `data/artifacts/` or `data/output/`.

## Primary Artifacts

The intended contract defines these primary artifacts:

- `info.json`: canonical song metadata, including `song_name`, `bpm`, `duration`, and generated file references, written to `data/output/<Song - Artist>/info.json`.
- `beats.json`: compact UI-facing beat timeline written to `data/output/<Song - Artist>/beats.json`.
- `essentia/fft_bands.json`: seven fixed 50 ms low-to-high spectral band levels for debugger inspection.
- `hints.json`: editable UI-facing section hints written to `data/output/<Song - Artist>/hints.json`.
- `sections.json`: compact UI-facing section timeline written to `data/output/<Song - Artist>/sections.json`.
- `layer_a_harmonic.json`: chord events, key, cadence, harmonic summaries.
- `layer_b_symbolic.json`: note events, symbolic summaries, contour and density views.
- `layer_c_energy.json`: loudness, onset, centroid, energy sections, accent candidates.
- `energy_summary/hints.json`: named energy-event identifiers such as high-confidence `drop` anchors with explicit evidence.
- `event_inference/features.json`: aligned event-inference feature timeline with normalized per-beat cross-layer features and rolling windows.
- `event_inference/rule_candidates.json`: deterministic baseline event candidates with explicit evidence for transitions and held states.
- `event_inference/events.machine.json`: refined machine event classifications with subtype fallback candidates preserved.
- `song_event_timeline.json`: compact event export for downstream prompting and planning.
- `validation/song_events.review.json`: review-friendly machine output with confidence bands and ambiguity flags.
- `validation/song_events.overrides.json`: deterministic override file for confirm, delete, retime, relabel, and annotation operations.
- `validation/song_events.review.md`: human-review markdown companion for the reviewed event payload.
- `validation/song_event_timeline.md`: human-review markdown companion for the compact event timeline.
- `layer_d_patterns.json`: repeated multi-bar chord progressions and their occurrences.
- `music_feature_layers.json`: unified cross-layer timeline and downstream lighting handoff artifact.
- `lighting_score.md`: final human-readable lighting design document.

## Documentation Map

- `docs/constitution.md`: The architectural "North Star," coding standards, and project values.
- `docs/Implementation_Guide.md`: canonical hub for the full pipeline and repository contracts.
- `docs/1.3.fft_band_extraction_story.md`: seven-band FFT artifact contract.
- `docs/phase_1_validation_cli.md`: Phase 1 analyzer CLI specification, command reference, and validation report format.
- `docs/4.1.energy_feature_schema.md`: low-level energy schema.
- `docs/4.2.section_segmentation_story.md`: section inference contract.
- `docs/event_user_stories block 5.x.md`: phased Epic 5 plan for song-event inference.
- `docs/5.1.event_vocabulary_and_schema_story.md`: canonical event vocabulary and schema contract.
- `docs/5.5.advanced_event_classification_story.md`: refined event classification contract.
- `docs/5.6.event_review_and_override_story.md`: review and override workflow contract.
- `docs/5.7.event_benchmarking_and_tuning_story.md`: benchmarking and threshold-profile tuning contract.
- `docs/5.4.song_identifier_inference_story.md`: controlled named-event inference contract.
- `docs/5.8.event_timeline_export_story.md`: compact event timeline export contract.
- `docs/6.1.find_chord_patterns_story.md`: Layer D chord-pattern detection contract.
- `docs/6.3.music_feature_layers_story.md`: unified layer assembly contract.
- `docs/6.4.energy_to_lighting_mapping.md`: feature-to-lighting mapping contract.
- `docs/6.5.fixture_aware_mapping_story.md`: fixture-aware orchestration and lighting score generation.
- `docs/ui_development.md`: internal debugger runtime, folder ownership, and read-only data-access contract.

Additional story-level specifications under `docs/` define the exact implementation contract for each Epic and story.

## Quick Start

1. **Prerequisites:** Docker with NVIDIA GPU support
2. **Build:** `docker compose build`
3. **Run the full pipeline from the host shell for one song:**
   ```bash
   docker compose run --rm app \
     ./analyze \
     --song "/data/songs/YOUR_SONG.mp3"
   ```

  This command runs the full production pipeline, writes generated artifacts under `data/artifacts/<Song - Artist>/`, preserves the stable UI output contract under `data/output/<Song - Artist>/`, and always writes validation and human-review documents under `data/artifacts/<Song - Artist>/validation/`.

  Analyze every song under `/data/songs` with the same full-pipeline flow and write per-song reports automatically:

  ```bash
  docker compose run --rm app \
    ./analyze \
    --all-songs
  ```

For detailed CLI options, see [Running the Phase 1 Analyzer](#running-the-phase-1-analyzer) below.

To run the internal debugger UI separately:

```bash
docker compose up ui
```

Then open `http://localhost:8080` and load a per-song directory name from `data/artifacts/`.

## Development Environment

The repository is Docker-first.

- Use the root `Dockerfile` and `docker-compose.yml` as the canonical local development environment.
- Use the separate `ui` service for the internal artifact debugger rather than serving debugger assets from the analyzer container.
- The Docker image is NVIDIA CUDA-enabled.
- The current local development setup uses an `NVIDIA GeForce GTX 1650`, and the container workflow is configured to take advantage of that GPU.
- Demucs checkpoints are cached explicitly under `models/demucs/` so analyzer runs do not rely on mid-run `torch.hub` downloads.
- Validate all tooling and sample-song runs inside the container.
- **Always Test in Container:** All analysis logic and UI behaviors must be verified inside their respective Docker services (`app` or `ui`).
- Do not rely on host-installed Python packages or audio tooling.
- Treat the Docker image as the authoritative developer runtime.

The detailed environment contract lives in `docs/docker_development.md`, the repo root `Dockerfile`, and `docker-compose.yml`.

### Docker Setup

- `Dockerfile`: multi-stage CUDA-based build with `python-base`, `builder`, and `runtime` stages.
- `docker-compose.yml`: defines the `app` analyzer service and the separate `ui` debugger service.
- The `app` service builds the CUDA-enabled analyzer runtime, mounts the repository at `/app`, mounts `./data` at `/data`, and requests `gpus: all`.
- The `ui` service builds from `/ui`, serves the debugger on port `8080`, and mounts `./data` read-only.

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

Inside the debugger container:

- browser assets are served from `/usr/share/nginx/html`
- generated data is mounted at `/data` in read-only mode
- the debugger may inspect generated artifacts but must not write back into `data/artifacts/` or `data/output/`

### Running the Phase 1 Analyzer

Run the Phase 1 analyzer from the host CLI with `docker compose run`. Do not invoke the analyzer directly on the host. Use the repo-root `./analyze` helper inside the container, or call `python -m analyzer` directly if you prefer. Both forms run the full end-to-end pipeline, write production artifacts and outputs, and then emit validation reports.

```bash
docker compose run --rm app \
  ./analyze \
  --song "/data/songs/Cinderella - Ella Lee.mp3" \
  --compare beats,chords,sections,energy,patterns,unified,events
```

Stage progress lines are prefixed with the pipeline story identifier when one is defined, for example `[1.1] Cinderella - Ella Lee | ensure-stems`.

When `--all-songs` is used, the same progress lines also include the batch position prefix, for example `[2/20][1.1] Cinderella - Ella Lee | ensure-stems`.

Run the same full pipeline for every song under `/data/songs`:

```bash
docker compose run --rm app \
  ./analyze \
  --all-songs
```

Run a single stage only (using existing prerequisite artifacts when needed):

```bash
docker compose run --rm app \
  ./analyze \
  --song "/data/songs/Cinderella - Ella Lee.mp3" \
  --stage extract-fft-bands
```

Analye all songs in background
```bash
mkdir -p logs && nohup docker compose run --rm -T app ./analyze --all-songs --device cuda > "logs/all-songs-$(date +%F_%H-%M-%S).log" 2>&1 < /dev/null & echo $!
```


**Available compare targets:** `beats`, `chords`, `sections`, `energy`, `patterns`, `unified`, `events`

Generated outputs from each run include the canonical artifact set under `data/artifacts/<Song - Artist>/`, Epic 5 event artifacts such as `energy_summary/hints.json`, `event_inference/events.machine.json`, `validation/event_benchmark.json`, stable UI deliverables under `data/output/<Song - Artist>/` (`info.json`, `beats.json`, `hints.json`, `sections.json`, `song_event_timeline.json`, `lighting_score.md`), and human-review support files under `data/artifacts/<Song - Artist>/validation/`.

The current Epic 5 implementation also writes `data/artifacts/<Song - Artist>/energy_summary/hints.json`, `event_inference/features.json`, `timeline_index.json`, `rule_candidates.json`, `events.machine.json`, and validation-scoped review documents such as `song_events.review.json`, `song_events.review.md`, `song_events.overrides.json`, and `song_event_timeline.md`.

Validation reports are always written automatically to `data/artifacts/<Song - Artist>/validation/phase_1_report.json` and `data/artifacts/<Song - Artist>/validation/phase_1_report.md`.

**CLI flags:**
- `--song`: Required path to source song for single-song runs
- `--all-songs`: Analyze every `.mp3` under `/data/songs` or `--songs-root`
- `--songs-root`: Optional songs directory for batch mode. Defaults to the sibling `songs/` directory next to `--artifacts-root`
- `--artifacts-root`: Optional root directory for generated artifacts. Defaults to `/data/artifacts`
- `--reference-root`: Optional root directory for validation reference files. Defaults to `/data/reference`
- `--compare`: Comma-separated list of validation targets
- `--fail-on-mismatch`: Exit non-zero when validation thresholds are missed
- `--beat-tolerance-seconds`: Beat timestamp tolerance (default: 0.10)
- `--tolerance-seconds`: Section boundary tolerance (default: 2.0)
- `--chord-min-overlap`: Minimum overlap ratio for chord comparison (default: 0.5)
- `--device`: Execution device (`cuda` or `cpu`)
- `--verbose`: Enable detailed logging
- `--stage`: Run only one pipeline stage by name. This mode expects prerequisite artifacts to already exist for stages that depend on earlier outputs.

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
4. EPIC 5.1 through EPIC 5.4: event contracts, aligned features, baseline rules, and controlled identifier inference.
5. EPIC 5.5 through EPIC 5.8: refined event classification, review, benchmarking, and compact timeline export.
6. EPIC 6.1 and EPIC 6.2: pattern mining and compact UI outputs.
7. EPIC 6.3 through EPIC 6.5: unified layer assembly, lighting mapping, and score generation.

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
- Final UI outputs live in `data/output/<Song - Artist>/` and must remain limited to `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, and `lighting_score.md`.

Examples: `data/output/<Song - Artist>/info.json`, `data/output/<Song - Artist>/song_event_timeline.json`, `data/output/<Song - Artist>/lighting_score.md`.

Inside `data/artifacts/<Song - Artist>/`, generated files should use producer-scoped folders when relevant. Examples: `data/artifacts/<Song - Artist>/essentia/beats.json`, `data/artifacts/<Song - Artist>/section_segmentation/sections.json`, `data/artifacts/<Song - Artist>/energy_summary/features.json`, `data/artifacts/<Song - Artist>/pattern_mining/chord_patterns.json`.

### Canonical Upstream Layers

- `layer_a_harmonic.json`
- `layer_b_symbolic.json`
- `layer_c_energy.json`
- `layer_d_patterns.json`

### Canonical Unified Handoff Artifact

- `music_feature_layers.json`

This file is the explicit EPIC 6.3 output and the required input to downstream lighting-mapping stories.

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

## Appendix: Visual Debugger

The internal visual debugger runs as the separate Compose `ui` service.

Start it with Docker:

```bash
docker compose up ui
```

Then open `http://localhost:8080` in a browser.

For internal LLM-oriented UI development instructions, see `ui/README.HELPER_UI.md`.
