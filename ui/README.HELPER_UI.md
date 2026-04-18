# Internal Artifact Debugger and Regression Viewer

## Purpose

This file documents the current UI implementation for LLM-assisted development.

The UI under `ui/` is an internal, read-only visual debugger for inspecting inference outputs under `data/artifacts/<Song - Artist>/`. It is not the production consumer UI.

## Non-Negotiable Rules

- Do not write files into `data/artifacts/`.
- Do not write files into `data/output/`.
- Do not turn this UI into a production-facing consumer experience.
- Treat `data/artifacts/<Song - Artist>/` as the primary source of truth.
- Treat `data/output/<Song - Artist>/` as secondary helper context only.
- Keep the debugger running in its own Compose `ui` service. Do not fold it into the analyzer container.

## Current Runtime

- Container: `ui/Dockerfile`
- Compose runtime: Vite dev server with live reload for `ui/src` edits
- Production runtime: Nginx serving the built bundle from the Dockerfile production stage
- Port: `8080`
- Data mount: `./data:/data:ro`
- Compose service: `ui`

Start the UI:

```bash
docker compose up ui
```

The helper UI service now bind-mounts `ui/` and reloads when files under `ui/src/` change.

Open:

```text
http://localhost:8080
```

## Current File Map

- `ui/index.html`: Vite entry document with the Preact mount point
- `ui/src/styles.css`: shared visual styling imported by the Preact app
- `ui/src/App.jsx`: top-level application orchestration and state
- `ui/src/components/`: panel and timeline component boundaries
- `ui/src/lib/`: artifact loading, normalization, and imperative timeline helpers
- `ui/package.json`: frontend dependencies and scripts
- `ui/vite.config.js`: Vite plus Preact build configuration
- `ui/nginx.conf`: static serving plus `/data/` alias and autoindex
- `ui/Dockerfile`: development stage for the Vite dev server plus a production Nginx build stage

## What Exists Today

The current implementation is a read-only Epic 7 debugger with these features:

- automatic discovery of song directories by reading `/data/artifacts/`
- automatic loading of the first discovered song when there is no `?song=` query parameter
- explicit song selection from a discovered dropdown
- manual refresh of the discovered song list
- read-only loading of artifact and helper JSON files
- artifact availability list with per-file load status
- summary cards for core inference surfaces
- validation preview from `validation/phase_1_report.json`
- section preview from the artifact or output projection
- audio element pointed at `data/songs/<Song - Artist>.mp3`
- shared playback cursor driven by the mounted audio file
- waveform anchor decoded in-browser when possible, with beat-pulse fallback
- fixed-label synchronized lane layout with shared zoom and horizontal scroll
- sparse lanes for sections, phrases, chords, pattern occurrences, and event windows
- dense lanes for drums, symbolic density, and energy
- regression overlay lane for beat drift and exported-event comparison
- lane-item detail hovercards opened directly from clicked timeline regions
- raw JSON inspector for any successfully loaded file
- explicit missing-core-artifacts warning card for partial song folders

## Primary Data Sources

The current UI attempts to load these files:

### Primary artifact-side files

- `data/artifacts/<Song - Artist>/layer_a_harmonic.json`
- `data/artifacts/<Song - Artist>/layer_b_symbolic.json`
- `data/artifacts/<Song - Artist>/layer_c_energy.json`
- `data/artifacts/<Song - Artist>/layer_d_patterns.json`
- `data/artifacts/<Song - Artist>/section_segmentation/sections.json`
- `data/artifacts/<Song - Artist>/symbolic_transcription/drum_events.json`
- `data/artifacts/<Song - Artist>/event_inference/features.json`
- `data/artifacts/<Song - Artist>/event_inference/timeline_index.json`
- `data/artifacts/<Song - Artist>/event_inference/rule_candidates.json`
- `data/artifacts/<Song - Artist>/event_inference/events.machine.json`
- `data/artifacts/<Song - Artist>/pattern_mining/chord_patterns.json`
- `data/artifacts/<Song - Artist>/music_feature_layers.json`
- `data/artifacts/<Song - Artist>/validation/phase_1_report.json`

### Secondary output-side helper files

- `data/output/<Song - Artist>/info.json`
- `data/output/<Song - Artist>/beats.json`
- `data/output/<Song - Artist>/sections.json`
- `data/output/<Song - Artist>/song_event_timeline.json`

## Current UI Structure

### Sidebar

- app title and purpose copy
- discovered song selector
- refresh button
- available path reference
- loaded-file status list

### Main content

- song title and metadata cards
- audio panel
- artifact summary panel
- core-artifact missing-state card when required files are absent
- validation snapshot panel
- sections preview panel
- raw JSON artifact inspector

## Current Browser Logic

The implementation now uses Preact for UI composition and state ownership, with Vite building the browser bundle during the container image build.

Key pieces:

- `artifactDefinitions`: declares the files the debugger tries to load for each song
- `fetchJson(...)`: reads JSON files from the mounted `/data` tree
- `fetchDirectoryListing(...)`: parses the Nginx autoindex HTML for `/data/artifacts/` and extracts per-song folders
- `App.jsx`: coordinates discovery, artifact loading, audio state, query string updates, and waveform decoding
- `Sidebar.jsx`, `OverviewPanels.jsx`, and `DetailPanels.jsx`: declarative panel rendering for the shell, summaries, sections, validation, and artifact inspector
- `TimelinePanel.jsx`: owns the timeline viewport and delegates dense-lane drawing to imperative helpers for parity with the previous implementation
- `lib/timeline.js`: renders sparse lane markup, draws dynamic lanes, and updates the shared now-marker positions

## Important Implementation Detail

Song discovery currently depends on Nginx `autoindex on` for `/data/` and parses the returned HTML directory listing in the browser.

That means:

- discovery works without adding a backend service
- discovery is intentionally simple and read-only
- if discovery behavior changes, check `ui/nginx.conf` and `fetchDirectoryListing(...)` together

Do not replace this with a write-capable backend unless the contract changes explicitly.

## Current Core Artifact Gate

The UI treats these keys as core surfaces for the empty-state warning:

- `harmonic`
- `symbolic`
- `energy`
- `sectionsArtifact`
- `eventMachine`
- `validation`

If these are missing, the selected song still loads, but the UI shows a warning card to make the partial state explicit.

## Known Limitations

- Discovery still relies on HTML directory parsing rather than a structured API
- Audio playback remains native HTML audio rather than a custom transport engine
- Waveform decoding is browser-side and can fall back to beat pulses on decode failure
- The debugger is intentionally internal and read-only; it does not persist review state

## Safe Extension Targets

These are the safest next implementation areas:

- improve overlay detail and hover affordances without changing data contracts
- add more artifact-first lanes when new story contracts introduce them
- improve partial-data handling for songs with incomplete artifacts
- tune dense-lane aggregation thresholds for larger generated datasets

## Unsafe Changes Unless the Contract Changes

- writing review state into `data/artifacts/validation/`
- writing snapshots into `data/output/`
- adding server-side mutation endpoints
- moving UI code into `src/`
- making the debugger depend on production-facing output files as its main source

## Suggested Validation After UI Changes

For low-risk validation, use:

```bash
docker compose up -d ui
curl -s http://localhost:8080 | head
curl -s http://localhost:8080/data/artifacts/ | head
docker compose stop ui
```

For a production bundle check, use:

```bash
docker compose build ui
```

Also check editor diagnostics for:

- `ui/src/`
- `ui/index.html`
- `ui/src/styles.css`

## Summary For LLM Agents

When extending this UI:

- keep it read-only
- prefer artifact-first views
- preserve the separate `ui` service
- document any contract-affecting change in the repo docs
- treat the current implementation as a scaffold to evolve, not as a throwaway mock

