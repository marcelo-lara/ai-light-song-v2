# UI Development Contract

## Purpose

Define the repository and runtime contract for the internal artifact debugger UI.

This UI is an engineering tool for inspecting model, heuristic, and rule outputs under `data/artifacts/<Song - Artist>/`. It is not the production consumer UI and it must not redefine the stable downstream contract under `data/output/<Song - Artist>/`.

## Scope

Included:

- read-only visualization of generated artifacts
- timing, validation, and provenance inspection
- artifact-to-artifact comparison views
- raw JSON inspection for debugging
- audio playback for review context

Excluded:

- writing files into `data/artifacts/`
- writing files into `data/output/`
- authoring or editing production lighting outputs
- replacing `lighting_score.md`
- acting as an end-user playback product

## Repository Layout

- `ui/`: all debugger browser assets, server configuration, and UI-specific container files
- `docs/ui_development.md`: this runtime and ownership contract
- `docker-compose.yml`: Compose entry for the separate `ui` service

Do not place debugger browser code under `src/`.

## Runtime Model

The debugger runs as a separate Compose service named `ui`.

- The analyzer `app` service remains the only supported runtime for inference, validation, and GPU-backed work.
- The `ui` service serves browser assets and mounted generated data.
- The `ui` service mounts `./data` read-only.
- The `ui` service must not reuse the analyzer container.

Current implementation shape:

- server: Nginx
- browser app: static HTML, CSS, and JavaScript under `ui/`
- exposed port: `8080`

## Data Access Rules

Primary debugger inputs live under `data/artifacts/<Song - Artist>/`.

The UI should support direct reads from at least:

- `layer_a_harmonic.json`
- `layer_b_symbolic.json`
- `layer_c_energy.json`
- `layer_d_patterns.json`
- `section_segmentation/sections.json`
- `symbolic_transcription/drum_events.json`
- `event_inference/features.json`
- `event_inference/timeline_index.json`
- `event_inference/rule_candidates.json`
- `event_inference/events.machine.json`
- `pattern_mining/chord_patterns.json`
- `music_feature_layers.json`
- `validation/phase_1_report.json`

Secondary helper inputs may be read from `data/output/<Song - Artist>/` when compact projections are useful for navigation or comparison, for example:

- `info.json`
- `beats.json`
- `sections.json`
- `song_event_timeline.json`

## Read-Only Rule

The debugger is read-only against generated data.

- Do not write snapshots to `data/artifacts/`.
- Do not write caches to `data/artifacts/`.
- Do not write derived JSON to `data/artifacts/`.
- Do not write overrides or review operations to `data/artifacts/`.
- Do not write helper files to `data/output/`.

If a future workflow requires persisted review data, that workflow must be documented explicitly as a new contract rather than added implicitly to the debugger.

## Initial Implementation Slice

The current scaffold provides:

- auto-discovery of per-song artifact directories from `data/artifacts/`
- a song-directory selector keyed by discovered per-song folders
- automatic loading of the first discovered song when no explicit song selection is present
- read-only JSON fetches from mounted artifact and output paths
- an artifact availability panel
- an explicit missing-core-artifact state when a discovered song folder is partial
- summary cards for core inference surfaces
- validation and section previews
- a raw JSON inspector
- native audio playback for the matching song file when available

Future story work can layer Wavesurfer-based timeline synchronization and richer lane rendering on top of this scaffold.

## Development Commands

Build the debugger image:

```bash
docker compose build ui
```

Run the debugger service:

```bash
docker compose up ui
```

Open the debugger in a browser:

```text
http://localhost:8080
```