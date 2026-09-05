# Reference — Docker runtime

**All analysis, validation and tests run inside Docker** (Docker only).
Never propose host-installed Python or audio tooling. The root
`Dockerfile` and `docker-compose.yml` are canonical.

## Services

| Service | Backed by | Role |
| --- | --- | --- |
| `app` | root `Dockerfile` | analyzer and validation runtime; the only supported runtime for inference and GPU work |
| `ui` | `ui/Dockerfile` | artifact debugger; never an analyzer runtime |
| `test` | root `Dockerfile` | the test suite |

## Commands

```bash
docker compose build              # build the analyzer image
docker compose build ui           # build the debugger image
docker compose run --rm app       # interactive shell in the analyzer
docker compose run --rm test      # tests
docker compose up ui              # debugger at http://localhost:9090
```

Long batch run, detached, logged:

```bash
mkdir -p logs && nohup docker compose run --rm -T app \
  ./analyze --all-songs --device cuda \
  > "logs/all-songs-$(date +%F_%H-%M-%S).log" 2>&1 < /dev/null & echo $!
```

Batch mode isolates each song in a subprocess so unstable native state does not
leak between tracks, and reuses the repo-local Demucs cache so no run depends on
a mid-run download.

## Container layout

| | |
| --- | --- |
| Repo mount | `/app` (working directory) |
| Data mount | `/data` |
| Model assets | `/app/models`; Demucs cache `/app/models/demucs` |
| UI working tree | `/srv/ui` in the `ui` container |
| Ports | `ui` container `8080` → host `9090` |

Dependencies install directly into the container Python; there is no in-container
virtualenv.

## Why the versions are pinned where they are

Base image **`nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04`**. Each pin below
exists because something breaks without it — do not bump one in isolation.

| Pin | Reason |
| --- | --- |
| `tensorflow==2.12.1` | Essentia's TensorFlow setup helper mis-detects the 2.15.x wheel layout and generates broken linker symlinks during the native build |
| CUDA 11.8 / cuDNN 8.6 base | what TensorFlow 2.12.1 GPU expects; a CUDA 12.x base stops TF loading GPU libraries at all |
| `torch==2.1.2`, `torchaudio==2.1.2` from the `cu118` index | keeps Demucs and other Torch stages on CUDA 11.8 instead of pulling default PyPI cu121 wheels |
| `numpy<2` | pinned across the TF 2.12 stack |
| Essentia **compiled from source** with `--with-tensorflow` | the plain PyPI wheel does not expose TensorFlow predictor algorithms such as `TensorflowPredictMusiCNN` |
| GPU `libtensorflow` C tarball, plus patching `_essentia` to depend on `libtensorflow.so.2` | the TF Python wheel alone does not export the C API symbols Essentia resolves at runtime |
| `resampy==0.4.3`, installed after the main requirements | `0.4.2` emits a deprecated `pkg_resources` warning during inference |
| Omnizart from the `audiohacking/omnizart` fork | legacy PyPI metadata excludes Python 3.10. The build also downloads the missing `variables.data-00000-of-00001` weight shard into the installed package tree, and exposes TF wheel shared libraries so Omnizart's direct import resolves native deps |
| `LD_LIBRARY_PATH` keeps NVIDIA container runtime paths | so TensorFlow can resolve the host-mounted `libcuda` driver |

## Runtime environment defaults

Set at Python startup by `analyzer/__init__.py`:

| Variable | Value | Why |
| --- | --- | --- |
| `TF_CPP_MIN_LOG_LEVEL` | `1` | suppress TF info-level C++ startup noise; warnings and errors stay visible |
| `TF_GPU_ALLOCATOR` | `cuda_malloc_async` | share limited GPU memory across model-backed stages |
| `TF_FORCE_GPU_ALLOW_GROWTH` | `true` | same |
| `OMNIZART_DRUM_MODEL_PATH` | unset | explicit override when testing a different drum model directory |

The pipeline also runs a best-effort GPU cleanup boundary before and after each
stage (`gc.collect`, Torch cache release, TF session clear) to limit inter-stage
memory retention on long runs.

## Smoke test

A working container can: see the GPU, import the analysis libraries, read a song
from `data/songs/`, write to `data/analysis/<Song - Artist>/artifacts/`, and emit
`artifacts/validation/phase_1_report.json`.

## Experiment images

Experiment sandboxes are **separate images** and must leave the analyzer image
untouched (experiments are a sandbox; `src/` never imports from them). Example:
`experiments/drop_detection/research/run_in_container.sh`.
