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
docker compose build app mcp ui   # `build` alone builds only `ui` (the rest are on-demand)

# one song: full pipeline + validation report
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3"

# every song under /data/songs, each in its own subprocess
docker compose run --rm app ./analyze --all-songs --device cuda

# one stage only (prerequisite artifacts must already exist)
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3" --stage segment-sections

# remove generated data only (songs + reference kept)
docker compose run --rm app ./analyze --clean-generated-data

docker compose run --rm test     # tests
docker compose up                # debugger only (the sole service `up` starts)

# song-comprehension MCP server — a stdio server its client spawns (-T is mandatory)
docker compose build mcp
docker compose run --rm -T mcp
```

Each run writes intermediates under `data/analysis/{song}/artifacts/`,
the stable deliverables at `data/analysis/{song}/`, and validation
reports at `artifacts/validation/phase_1_report.{json,md}`.

### Analysis watcher

The debugger's **Run analysis** button and the MCP `request_analysis` tool only
queue a run (`data/analysis/{song}/artifacts/_run_request.json`). Nothing runs
until the host-side watcher picks it up. The watcher runs on the host, not in
a container, and calls `docker compose run` itself.

```bash
./analysis-watcher               # start in the background and return (same as --start)
./analysis-watcher --stop        # stop it; a run in progress is marked failed ("interrupted")
./analysis-watcher --foreground  # run the polling loop in this terminal instead
./analysis-watcher --once        # work through the queue, then exit
```

If a watcher is already running, `./analysis-watcher` shows its pid and asks
whether to stop it. Its log and pid file are `data/analysis-watcher.log` and
`data/analysis-watcher.pid`. A request that no watcher picks up within 2 minutes
shows as "no watcher running" in the debugger, and as `not_started` from
`get_analysis_progress`.

## The pipeline

Four phases — measure, interpret, relate, publish. This table is the shipped
shape, **not** a quality claim; see
[docs/analysis-definition.md](docs/analysis-definition.md) for what each stage
actually measures.

| Phase | Stages | Key output |
| --- | --- | --- |
| 1 measure | stems, beat grid + downbeat phase, 7-band FFT, loudness | `essentia/beats.json`, `essentia/fft_bands.json`, `rms_loudness.json` |
| 2 interpret | drum transcription, named segmentation (All-In-One) | `symbolic_transcription/drum_events.json`, `section_segmentation/sections.json` |
| 3 relate | gesture phases and section-pair transitions | `song_event_timeline.json` |
| 4 publish | fuse + pack the top-level deliverables | `info.json`, `beats.json`, `sections.json`, `hints.json`, `drum_events.json`, `loudness.json`, `arrangement_state.json`, `vocal_cadence.json` |

The nine top-level files per song — the eight above plus phase 3's
`song_event_timeline.json` — are the delivery surface the `mcp/` server reads.

## Layout

The structure is part of the contract.

| Path | Contents |
| --- | --- |
| `data/songs/` | source `.mp3` inputs |
| `data/analysis/{song}/` | stable deliverables: top-level JSON plus `artifacts/` and `reference/` |
| `…/artifacts/` | intermediates, grouped by producer (`essentia/`, `allin1/`, `section_segmentation/`, …) |
| `…/reference/` | validation-only truth (human hints, external tools). Never a generation input |
| `src/`, `ui/`, `mcp/` | analyzer, read-only debugger, song-comprehension MCP server |
| `experiments/` | sandbox — `src/` never imports from it |
| `docs/` | current contracts only; superseded docs are deleted, not archived |

## Documentation

| Doc | |
| --- | --- |
| [CLAUDE.md](CLAUDE.md) | entry point — state, trusted vs. suspect stages, how to run |
| [docs/product-definition.md](docs/product-definition.md) | what this is for |
| [docs/analysis-definition.md](docs/analysis-definition.md) | the pipeline, and how good each part measures |
| [docs/ui-definition.md](docs/ui-definition.md) | the artifact debugger |
| [docs/mcp-definition.md](docs/mcp-definition.md) | the in-repo `mcp/` song-comprehension server |
| [docs/reference/downstream-contract.md](docs/reference/downstream-contract.md) | what the external cue-authoring server consumes |
| [docs/reference/](docs/reference/) | lookup tables: `data/` files, `src/` map, CLI flags, Docker, UI QA, MCP regression |
| [experiments/drop_detection/README.md](experiments/drop_detection/README.md) | measured evaluation of the structural stages |

## Development

Docker-first; the root `Dockerfile` and `docker-compose.yml` are canonical
(CUDA-enabled, local dev on a GTX 1650). Demucs checkpoints are cached under
`models/demucs/` to avoid mid-run downloads. Do not rely on host-installed
Python or audio tooling. Details and the reasoning behind every version pin:
[docs/reference/docker.md](docs/reference/docker.md).
