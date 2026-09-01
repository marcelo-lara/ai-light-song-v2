# ai-light-song-v2

**Status:** `v2.1` code complete — all plan items implemented and committed (one
commit per item); the `v2.1` tag is held pending two host-dependent gates, the
gold-set labelling pass (D1) and the full-corpus GPU validation run (D2). The
module release line is `v2.x` to match the repo and the `UI v2` rebuild; `v2.1`
was drafted as `v1.1` and renumbered before tagging (there is no `v1.x` tag).
`v2.2` planning is now open. See
[docs/product-refinement-v2.1.md](docs/product-refinement-v2.1.md) (v2.1
worklist and the version convention),
[docs/implementation-plan-v2.1.md](docs/implementation-plan-v2.1.md) (per-item
status), [docs/source references/contract-change-v2.1.md](docs/source%20references/contract-change-v2.1.md)
(the MCP handover note), and
[docs/product-refinement-v2.2.md](docs/product-refinement-v2.2.md) (the next
release worklist).

The internal debugger UI (`ui/`) is the `UI v2` from-scratch rebuild (React +
TypeScript + Vite, the "Score Analysis DAW" design, wavesurfer.js as player and
master clock) — items 1–11 committed; the `ui-v2` tag is held pending a
live-browser parity pass. Close-out and parity sign-off:
[docs/web-ui/ui-rebuild/](docs/web-ui/ui-rebuild/).

A Docker-first pipeline that turns a source song into structured musical
analysis artifacts and fixture-aware lighting guidance. This repo is the
analysis module of a three-part stage-lighting system: its job is to work out a
song's structure and intention precisely enough that a downstream MCP server can
author a light show from the analysis alone.

This repository holds the runnable analyzer (`src/`), the artifact contracts it
emits, the validation rules that score those artifacts, the read-only artifact
debugger (`ui/`), and the Docker environment.

## Pipeline

| Epic | Stage | Key output |
| --- | --- | --- |
| 1 | Preprocessing: stems, beats, tempo, bar grid, 7-band FFT | `essentia/beats.json`, `essentia/fft_bands.json` |
| 2 | Harmonic: key, chords, HPCP, chord-pattern mining | `layer_a_harmonic.json`, `layer_d_patterns.json` |
| 3 | Structure: section segmentation, boundary audit, alignment | `section_segmentation/sections.json` |
| 4 | Symbolic: note events, energy features, event-feature layer | `layer_b_symbolic.json`, `layer_c_energy.json` |
| 5 | Events: vocabulary, rule baseline, ML classifier, review | `song_event_timeline.json` |
| 6 | Guidance: genre, section hints, LLM-friendly song map | `hints.json` |
| 7 | Lighting: feature-layer assembly, mapping, fixture score | `lighting_score.md` |
| 8 | Internal read-only artifact debugger (`ui/`) | — |

Per-epic and per-story specs live under `docs/` (see the
[Documentation map](#documentation-map)).

## Repository layout

The structure is part of the contract.

- `data/songs/` — source `.mp3` inputs.
- `data/analysis/<Song - Artist>/` — stable UI-facing deliverables. Exactly:
  `info.json`, `beats.json`, `hints.json`, `sections.json`,
  `song_event_timeline.json`, `lighting_score.md`, `beatdrop_visual_plan.json`,
  plus `artifacts/`. Do not add or remove files here without a contract change.
- `data/analysis/<Song - Artist>/artifacts/` — intermediate artifacts, grouped
  by producer (`essentia/`, `section_segmentation/`, `energy_summary/`,
  `event_inference/`, `pattern_mining/`, `validation/`, …), including
  `artifacts/stems/`.
- `data/analysis/<Song - Artist>/reference/` — validation-only truth data
  (external tools, human hints). Scoring and comparison only.
- `docs/` — canonical specs and contracts.
- `src/`, `ui/` — analyzer and debugger.

## Hard rules

Full law is in [docs/constitution.md](docs/constitution.md). Load-bearing:

- **Living docs.** A task is not done until its Story spec and docs match the
  implementation.
- **Determinism.** Same input + engine version ⇒ byte-identical artifacts. No
  silent fallbacks; fail explicitly or mark `unknown`.
- **Reference isolation.** Never copy `reference/` data into generated artifacts
  except through an explicit, confidence-gated, provenance-recorded promotion.
  `reference/` exists only directly under `data/analysis/<Song - Artist>/`.
- **Provenance.** Every generated file carries a `generated_from` block;
  schemas are versioned.
- **Time in seconds, bars 1-indexed**, all beat-aligned outputs on the EPIC 1.2
  grid.
- **Docker only.** All analysis and validation runs inside the `app`/`ui`
  services. The debugger never writes to `data/analysis/`.

## Quick start

Prerequisite: Docker with NVIDIA GPU support.

```bash
docker compose build

# one song, full pipeline + validation report
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3"

# every song under /data/songs
docker compose run --rm app ./analyze --all-songs

# one stage only (prerequisite artifacts must already exist)
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3" --stage <stage-name>

# remove generated data only (songs + reference kept)
docker compose run --rm app ./analyze --clean-generated-data
```

Each run writes artifacts under `data/analysis/<Song - Artist>/artifacts/`, the
stable deliverables under `data/analysis/<Song - Artist>/`, and validation
reports under `artifacts/validation/phase_1_report.{json,md}`. Stage progress
lines are prefixed with the story id, e.g. `[1.1] YOUR_SONG | ensure-stems`.

Full CLI reference (flags, compare targets, exit codes, validation workflow):
[docs/source references/phase_1_validation_cli.md](docs/source%20references/phase_1_validation_cli.md).

### Debugger UI

```bash
docker compose up ui
```

Open `http://localhost:9090` (Compose maps host `9090` → container `8080`) and
load a per-song directory name from `data/analysis/`. The debugger is read-only
against `data/analysis/**` except the two explicit human-save endpoints
(`PUT /api/human-hints/<song>`, `PUT /api/song-facts/<song>`). Prod build:
`docker build --target final -t ui-v2-prod ./ui` (nginx, `listen 8080`).
Helper-UI dev notes: [ui/README.HELPER_UI.md](ui/README.HELPER_UI.md).

## Documentation map

- [docs/README.md](docs/README.md) — index of all specs, grouped by kind of work.
- [docs/constitution.md](docs/constitution.md) — architecture North Star and project law.
- [docs/Implementation_Guide.md](docs/Implementation_Guide.md) — full pipeline and repository contracts.
- [docs/product-refinement-v2.2.md](docs/product-refinement-v2.2.md) — active release worklist (v2.2, planning).
- [docs/product-refinement-v2.1.md](docs/product-refinement-v2.1.md) — v2.1 worklist and the version convention.
- [docs/implementation-plan-v2.1.md](docs/implementation-plan-v2.1.md) — ordered v2.1 work, one commit per item.
- [docs/data_folder_reference.md](docs/data_folder_reference.md) — every `data/` file and its purpose.
- [docs/source references/analysis-input-guide.md](docs/source%20references/analysis-input-guide.md) — what the downstream MCP server actually consumes; the contract analysis quality is judged against.
- Story specs: [docs/audio-processing/](docs/audio-processing/), [docs/audio-inference/](docs/audio-inference/), [docs/lighting-score/](docs/lighting-score/), [docs/web-ui/](docs/web-ui/), [docs/human-curated/](docs/human-curated/).

## Development environment

Docker-first; the root `Dockerfile` and `docker-compose.yml` are the canonical
runtime. CUDA-enabled image (local dev on a GTX 1650). Demucs checkpoints are
cached under `models/demucs/` to avoid mid-run downloads. Do not rely on
host-installed Python or audio tooling. Details:
[docs/docker_development.md](docs/docker_development.md).

```bash
docker compose run --rm app        # interactive shell in the analyzer container
docker compose up                  # long-running dev service
```

Analyze all songs in the background:

```bash
mkdir -p logs && nohup docker compose run --rm -T app \
  ./analyze --all-songs --device cuda \
  > "logs/all-songs-$(date +%F_%H-%M-%S).log" 2>&1 < /dev/null & echo $!
```


## Notes

- try <https://www.relume.ai/> for UI generation.
