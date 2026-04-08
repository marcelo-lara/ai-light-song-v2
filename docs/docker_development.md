# Docker Development Contract

## Purpose

Define the required container environment for all implementation and validation work in this repository.

## Rule

All development and validation must run inside Docker.

- Use NVIDIA GPU passthrough when available.
- Do not rely on host Python packages.
- Treat the container as the authoritative development runtime.

The repository's primary local runtime is the Compose `app` service backed by the root `Dockerfile`.

## Base Image

Recommended base image:

- `nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04`

This image provides a CUDA-enabled environment that is suitable for audio ML tooling and later model-backed analysis steps.

## Required System Packages

- `python3`
- `python3-pip`
- `python3-venv`
- `ffmpeg`
- `libsndfile1`
- `git`
- `curl`
- `build-essential`
- `pkg-config`

## Required Python Tooling

The container should provide a baseline environment capable of supporting:

- `numpy`
- `scipy`
- `pandas`
- `soundfile`
- `librosa`
- `essentia`
- `demucs`
- `basic-pitch`
- `pyyaml`
- `rich`

Exact versions can be pinned later in a dedicated dependency file once the implementation repository exists.

Current compatibility note:

- the current Basic Pitch runtime in this container requires `numpy<2` because the bundled TensorFlow Lite runtime is not compatible with NumPy 2.x.
- the analyzer loads Basic Pitch through its packaged TensorFlow Lite model path so Docker runs do not emit optional backend warnings for TensorFlow, ONNX, or CoreML backends that are not used in this repository.
- the container overrides `resampy` to `0.4.3` after the main requirements install because `0.4.2` emits a deprecated `pkg_resources` warning during Basic Pitch inference.

## Workspace Layout in Container

Current local container layout:

- repository mount: `/app`
- data mount: `/data`
- Compose service name: `app`

Expected working directory:

- `/app`

## Recommended Compose Commands

Build the development image:

```bash
docker compose build
```

Open an interactive shell in the development container:

```bash
docker compose run --rm app
```

Run the first-phase validation entry point:

```bash
docker compose run --rm app \
  python -m analyzer.cli validate-phase-1 \
  --song "/data/songs/What a Feeling - Courtney Storm.mp3" \
  --artifacts-root "/data/artifacts" \
  --reference-root "/data/reference" \
  --compare chords,sections \
  --report-json "/data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.json"
```

Batch mode is also supported for all mounted songs:

```bash
docker compose run --rm app \
  python -m analyzer.cli validate-phase-1 \
  --all-songs \
  --artifacts-root "/data/artifacts" \
  --reference-root "/data/reference"
```

An equivalent `python -m analyzer.cli` form is also acceptable if that becomes the chosen entry point.

## Required Validation Inside Container

At minimum, developers should validate the following inside Docker:

1. Python starts correctly.
2. `ffmpeg` is available.
3. Core imports succeed for the selected toolchain.
4. A sample song can be analyzed end to end without relying on host dependencies.
5. Generated outputs are written to `data/artifacts/` and `data/output/`.
6. The phase-1 validation CLI can compare inferred chords and sections against validation-only files in `data/reference/`.
7. Inference still runs when those reference files are missing; comparison is optional and only happens when the relevant files are available.

## Smoke Test Expectations

The first smoke test should verify:

- GPU visibility when GPU-dependent tooling is enabled
- successful import of the chosen analysis libraries
- ability to read a sample song from `data/songs/`
- ability to write outputs into the mounted workspace
- ability to emit a machine-readable validation report under `data/artifacts/<Song - Artist>/validation/`

## Deferred Items

These are intentionally deferred until the implementation repo exists:

- pinned Python lockfile
- CI-oriented container variants
- editor-specific devcontainer configuration
- production runtime optimization