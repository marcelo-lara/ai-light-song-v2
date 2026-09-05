# ai-light-song-v2

A Docker-first pipeline that turns a source song into **concrete, reliable,
precisely-timed musical facts** that a reasoning model can author a
production-quality light show from. This repo is the analysis module of a
three-part stage-lighting system: it works out a song's structure and intention
precisely enough that a downstream MCP server can author the show from the
analysis alone.

It is the *foundation* of a light show, not the light show. **Fixture-aware
orchestration, cue authoring and DMX are out of scope** — see
[docs/constitution.md](docs/constitution.md) §1.

**If you are an LLM, or new here, start with [CLAUDE.md](CLAUDE.md)** — what the
system does, which stages are trusted, what the measurements say is broken, and
which docs are current versus historical.

This repository holds the runnable analyzer (`src/`), the artifact contracts it
emits, the validation rules that score those artifacts, the read-only artifact
debugger (`ui/`), and the Docker environment.

## Pipeline

| Epic | Stage | Key output |
| --- | --- | --- |
| 1 | Preprocessing: stems, beats, tempo, bar grid, 7-band FFT | `essentia/beats.json`, `essentia/fft_bands.json` |
| 2 | Harmonic: key, chords, HPCP | `layer_a_harmonic.json` |
| 3 | Structure: section segmentation, boundary audit, alignment | `section_segmentation/sections.json` |
| 4 | Symbolic: note events, energy features, event-feature layer | `layer_b_symbolic.json`, `layer_c_energy.json` |
| 5 | Events: vocabulary, rule baseline, ML classifier, review | `song_event_timeline.json` |
| 6 | Guidance: genre, section hints, LLM-friendly song map | `hints.json` |
| 7 | Feature-layer assembly (`music_feature_layers.json`); ~~fixture score~~ removed | Lighting/fixture output is out of scope — constitution §1.1 |
| 8 | Internal read-only artifact debugger (`ui/`) | — |

The stage list above is the shipped shape, not a quality claim — see
[CLAUDE.md](CLAUDE.md) for which stages are trusted and which are measured as
not working.

## Repository layout

The structure is part of the contract.

- `data/songs/` — source `.mp3` inputs.
- `data/analysis/<Song - Artist>/` — stable UI-facing deliverables. Exactly:
  `info.json`, `beats.json`, `hints.json`, `sections.json`,
  `song_event_timeline.json`,
  plus `artifacts/`. Do not add or remove files here without a contract change.
- `data/analysis/<Song - Artist>/artifacts/` — intermediate artifacts, grouped
  by producer (`essentia/`, `section_segmentation/`,
  `event_inference/`, `validation/`, …), including
  `artifacts/stems/`.
- `data/analysis/<Song - Artist>/reference/` — validation-only truth data
  (external tools, human hints). Scoring and comparison only.
- `docs/` — current contracts and reference, and nothing else. Superseded
  documents are deleted, not archived; git history is the archive.
- `src/`, `ui/` — analyzer and debugger.

## Hard rules

Full law is in [docs/constitution.md](docs/constitution.md). Load-bearing:

- **Scope.** Musical facts with times and confidences. Not fixture
  orchestration, cue authoring or DMX.
- **Living docs.** A task is not done until the docs match the implementation,
  and a document that has stopped being true is deleted in the same change.
- **Experiments are first-class**, live in `experiments/`, and must be measured
  against the incumbent. Negative results get written down, not deleted.
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
[docs/reference/phase_1_validation_cli.md](docs/reference/phase_1_validation_cli.md).

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

- [CLAUDE.md](CLAUDE.md) — entry point: current state, trusted vs. suspect stages, doc conventions.
- [docs/README.md](docs/README.md) — index of current documents.
- [docs/constitution.md](docs/constitution.md) — project law.
- [docs/data_folder_reference.md](docs/data_folder_reference.md) — every `data/` file and its purpose.
- [docs/source_files_reference.md](docs/source_files_reference.md) — map of `src/`.
- [docs/reference/analysis-input-guide.md](docs/reference/analysis-input-guide.md) — what the downstream MCP server actually consumes; the contract analysis quality is judged against.
- [experiments/drop_detection/README.md](experiments/drop_detection/README.md) — measured evaluation of the structural stages and of pretrained alternatives.

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
