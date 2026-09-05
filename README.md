# ai-light-song-v2

A Docker-first pipeline that turns a song into **concrete, reliable,
precisely-timed musical facts** that a reasoning model can author a
production-quality light show from.

This is the analysis module of a three-part stage-lighting system: it works out
a song's structure and intention precisely enough that a downstream MCP server
can author the show from the analysis alone. It is the *foundation* of a light
show, not the light show — fixture orchestration, cue authoring and DMX are out
of scope.

**Start with [CLAUDE.md](CLAUDE.md)** — what the system does, which stages are
trusted, and what the measurements say is broken.

## Quick start

Prerequisite: Docker with NVIDIA GPU support.

```bash
docker compose build

# one song: full pipeline + validation report
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3"

# every song under /data/songs, each in its own subprocess
docker compose run --rm app ./analyze --all-songs --device cuda

# one stage only (prerequisite artifacts must already exist)
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3" --stage segment-sections

# remove generated data only (songs + reference kept)
docker compose run --rm app ./analyze --clean-generated-data

docker compose run --rm test     # tests
docker compose up ui             # debugger at http://localhost:9090
```

Each run writes intermediates under `data/analysis/<Song - Artist>/artifacts/`,
the stable deliverables at `data/analysis/<Song - Artist>/`, and validation
reports at `artifacts/validation/phase_1_report.{json,md}`.

## The pipeline

Four phases — measure, interpret, relate, publish. This table is the shipped
shape, **not** a quality claim; see
[docs/analysis-definition.md](docs/analysis-definition.md) for what each stage
actually measures.

| Phase | Stages | Key output |
| --- | --- | --- |
| 1 measure | stems, beat grid + downbeat phase, 7-band FFT, loudness | `essentia/beats.json`, `essentia/fft_bands.json`, `rms_loudness.json` |
| 2 interpret | harmonic (key, chords, HPCP), drum transcription, genre, named segmentation (All-In-One) | `layer_a_harmonic.json`, `symbolic_transcription/drum_events.json`, `genre.json`, `section_segmentation/sections.json` |
| 3 relate | gesture phases and section-pair transitions | `song_event_timeline.json` |
| 4 publish | section / beat / hint packing | `sections.json`, `beats.json`, `hints.json`, `info.json` |

## Layout

The structure is part of the contract.

| Path | Contents |
| --- | --- |
| `data/songs/` | source `.mp3` inputs |
| `data/analysis/<Song - Artist>/` | stable deliverables: exactly five files plus `artifacts/` |
| `…/artifacts/` | intermediates, grouped by producer (`essentia/`, `allin1/`, `section_segmentation/`, …) |
| `…/reference/` | validation-only truth (human hints, external tools). Never a generation input |
| `src/`, `ui/` | analyzer and read-only debugger |
| `experiments/` | sandbox — `src/` never imports from it |
| `docs/` | current contracts only; superseded docs are deleted, not archived |

## Documentation

| Doc | |
| --- | --- |
| [CLAUDE.md](CLAUDE.md) | entry point — state, trusted vs. suspect stages, how to run |
| [docs/product-definition.md](docs/product-definition.md) | what this is for |
| [docs/analysis-definition.md](docs/analysis-definition.md) | the pipeline, and how good each part measures |
| [docs/ui-definition.md](docs/ui-definition.md) | the artifact debugger |
| [docs/mcp-definition.md](docs/mcp-definition.md) | what the downstream server consumes |
| [docs/reference/](docs/reference/) | lookup tables: `data/` files, `src/` map, CLI flags, Docker, UI QA |
| [experiments/drop_detection/README.md](experiments/drop_detection/README.md) | measured evaluation of the structural stages |

## Development

Docker-first; the root `Dockerfile` and `docker-compose.yml` are canonical
(CUDA-enabled, local dev on a GTX 1650). Demucs checkpoints are cached under
`models/demucs/` to avoid mid-run downloads. Do not rely on host-installed
Python or audio tooling. Details and the reasoning behind every version pin:
[docs/reference/docker.md](docs/reference/docker.md).
