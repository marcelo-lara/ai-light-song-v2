# Docker Development Contract

## Purpose

Define the required container environment for all implementation and validation work in this repository.

## Rule

All development and validation must run inside Docker.

- Use NVIDIA GPU passthrough when available.
- Do not rely on host Python packages.
- Treat the container as the authoritative development runtime.

The repository's local runtime has two services:

- `app`: analyzer and validation runtime backed by the root `Dockerfile`
- `ui`: internal artifact-debugger runtime backed by `ui/Dockerfile`

## Base Image

Recommended base image:

- `nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04`

This image provides a CUDA-enabled environment that is suitable for audio ML tooling and later model-backed analysis steps.

## Required System Packages

- `python3`
- `python3-pip`
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
- `tensorflow`
- `essentia` built from source with TensorFlow support
- `demucs`
- `basic-pitch`
- `pyyaml`
- `rich`

Exact versions can be pinned later in a dedicated dependency file once the implementation repository exists.

Current compatibility note:

- the current Basic Pitch runtime in this container requires `numpy<2` because the bundled TensorFlow Lite runtime is not compatible with NumPy 2.x.
- the analyzer loads Basic Pitch through its packaged TensorFlow Lite model path so Docker runs do not emit optional backend warnings for TensorFlow, ONNX, or CoreML backends that are not used in this repository.
- the container overrides `resampy` to `0.4.3` after the main requirements install because `0.4.2` emits a deprecated `pkg_resources` warning during Basic Pitch inference.
- the plain PyPI `essentia` wheel does not expose TensorFlow predictor algorithms such as `TensorflowPredictMusiCNN`; the Docker image therefore installs TensorFlow and compiles Essentia from source with `--with-tensorflow`.
- the Docker image pins TensorFlow to `2.12.1` because the Essentia TensorFlow setup helper used by this repository mis-detects the TensorFlow `2.15.x` wheel layout and generates broken linker symlinks during the native build.
- the TensorFlow Python wheel alone does not export the TensorFlow C API symbols that Essentia resolves at runtime, so the image also installs the matching `libtensorflow` C library tarball and patches Essentia's `_essentia` extension to depend on `libtensorflow.so.2` explicitly.
- Story 3.2 installs Omnizart from the `audiohacking/omnizart` GitHub fork during the Docker build because the legacy PyPI package metadata excludes the repository's Python 3.10 runtime.
- the Docker image completes the packaged Omnizart drum checkpoint during build by downloading the missing `variables.data-00000-of-00001` weight shard into the installed package tree.
- the Docker image also exposes TensorFlow wheel shared libraries from the container runtime so Omnizart's direct Python drum import can resolve native TensorFlow dependencies.
- the Docker image installs Python dependencies directly into the container Python environment; it does not create an in-container virtual environment.
- Story 3.2 debug preservation is metadata-only: the generated drum artifact records explicit source paths for the full mix and drums stem, and the pipeline does not copy those audio files into `data/artifacts/`.

## Workspace Layout in Container

Current local container layout:

- repository mount: `/app`
- data mount: `/data`
- model assets: `/app/models`
- Demucs cache: `/app/models/demucs`
- Compose service names: `app` and `ui`
- UI assets: `/usr/share/nginx/html` inside the `ui` container

Expected working directory:

- `/app`

## Recommended Compose Commands

Build the development image:

```bash
docker compose build
```

Build only the debugger image:

```bash
docker compose build ui
```

Open an interactive shell in the development container:

```bash
docker compose run --rm app
```

Run the debugger service:

```bash
docker compose up ui
```

The debugger is served at `http://localhost:8080` and mounts `./data` read-only. It is an internal visualization tool for `data/artifacts/<Song - Artist>/` and selected compact helper files from `data/output/<Song - Artist>/`.

Run the first-phase validation entry point:

```bash
docker compose run --rm app \
  ./analyze \
  --song "/data/songs/What a Feeling - Courtney Storm.mp3" \
  --compare beats,chords,drums,sections,energy,patterns,unified,events
```

Batch mode is also supported for all mounted songs:

```bash
docker compose run --rm app \
  ./analyze \
  --all-songs
```

The current batch implementation isolates each song run in a subprocess so the long-lived parent container process does not retain unstable native analysis state between songs.

`./analyze` is the simplest container entry point. `python -m analyzer` is the equivalent module form.

The `ui` service is not an analyzer runtime. It serves the debugger assets from `/ui/` and must not write any debugger state into `data/artifacts/` or `data/output/`.

## Required Validation Inside Container

At minimum, developers should validate the following inside Docker:

1. Python starts correctly.
2. `ffmpeg` is available.
3. Core imports succeed for the selected toolchain.
4. A sample song can be analyzed end to end without relying on host dependencies.
5. Generated outputs are written to `data/artifacts/` and `data/output/`.
6. The phase-1 validation CLI can compare inferred beats, chords, and sections against validation-only files in `data/reference/`, and validate the generated energy, pattern, event, and unified artifacts for internal consistency.
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