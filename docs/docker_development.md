# Docker Development Contract

## Purpose

Define the required container environment for all implementation and validation work in this repository.

## Rule

All development and validation must run inside Docker.

- Use NVIDIA GPU passthrough when available.
- Do not rely on host Python packages.
- Treat the container as the authoritative development runtime.

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

## Workspace Layout in Container

Recommended mount point:

- `/workspace`

Expected working directory:

- `/workspace`

## Example Run Command

```bash
docker run --rm -it \
  --gpus all \
  -v "$PWD":/workspace \
  -w /workspace \
  ai-light-song-v2:dev
```

## Required Validation Inside Container

At minimum, developers should validate the following inside Docker:

1. Python starts correctly.
2. `ffmpeg` is available.
3. Core imports succeed for the selected toolchain.
4. A sample song can be analyzed end to end without relying on host dependencies.
5. Generated outputs are written to `data/artifacts/` and `data/output/`.

## Smoke Test Expectations

The first smoke test should verify:

- GPU visibility when GPU-dependent tooling is enabled
- successful import of the chosen analysis libraries
- ability to read a sample song from `data/songs/`
- ability to write outputs into the mounted workspace

## Deferred Items

These are intentionally deferred until the implementation repo exists:

- pinned Python lockfile
- CI-oriented container variants
- editor-specific devcontainer configuration
- production runtime optimization