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
- `ui/src/App.jsx`: thin top-level composition layer that wires app hooks into the view
- `ui/src/app/`: app-owned state, song loading, playback control, and prop-builder helpers
- `ui/src/components/`: folderized panel and timeline components with colocated submodules
- `ui/src/components/TimelinePanel/`: timeline shell, header, viewport, interaction hooks, and transport helpers
- `ui/src/lib/config/`: artifact definitions, lane definitions, and shared UI constants
- `ui/src/lib/data/`: directory fetch helpers, data normalization, and timeline-model assembly
- `ui/src/lib/timeline/`: imperative timeline markup, selection, viewport, and lane renderers
- `ui/src/lib/config.js`: stable re-export surface for config consumers
- `ui/src/lib/data.js`: stable re-export surface for data-loading consumers
- `ui/src/lib/timeline.js`: stable re-export surface for timeline consumers
- `ui/package.json`: frontend dependencies and scripts
- `ui/vite.config.js`: Vite plus Preact build configuration
- `ui/nginx.conf`: static serving plus `/data/` alias and autoindex
- `ui/Dockerfile`: development stage for the Vite dev server plus a production Nginx build stage

## Helper UI Architecture

The helper UI is intentionally split into three layers so behavior stays local and future edits do not rebuild monoliths.

### App layer

Files under `ui/src/app/` own cross-panel state and side effects.

- `useSongData.js`: song discovery, artifact loading, timeline-model creation, waveform-preview coordination
- `useShellState.js`: sidebar state and lane visibility state
- `usePlaybackState.js`: current playback cursor, follow-playhead state, and audio-driven timing state
- `usePlaybackActions.js`: transport actions and playback-side event handlers
- `createAppViewProps.js` and related prop builders: assemble stable component props instead of pushing business logic back into JSX

Keep shared state here when it is consumed by multiple panels. Do not move shell state into timeline-only components just to shorten prop lists.

### Component layer

Files under `ui/src/components/` render the UI and stay close to the parent they support.

- `Sidebar/`: shell controls, path hints, file-status list, and lane toggles
- `OverviewPanels/`: hero metadata, audio anchor, artifact summary, validation snapshot, and sections preview
- `DetailPanels/`: selection detail plus raw artifact inspector
- `OverlayPanel/`: anchored overlay behavior and dismissal logic
- `SelectionDetailCard/`: selection field formatting and display
- `TimelinePanel/`: timeline header, viewport, song menu, playback indicators, and interaction hooks

Component folders should keep small helpers next to their parent component. If a helper exists only to support one component folder, keep it inside that folder instead of promoting it into `ui/src/lib/`.

### Library layer

Files under `ui/src/lib/` are browser-side infrastructure, not app state.

- `config/`: lane and artifact definitions plus constants shared by the UI
- `data/`: fetch helpers and normalization utilities that turn loaded JSON into a timeline-friendly model
- `timeline/`: imperative drawing, markup, viewport math, and selection lookup for the synchronized lane renderer

The files `ui/src/lib/config.js`, `ui/src/lib/data.js`, and `ui/src/lib/timeline.js` are public entrypoints for the rest of the UI. Prefer adding new submodules behind those entrypoints instead of spreading deep import paths through the app.

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
- dense lanes for FFT bands, per-source RMS loudness, per-source loudness envelope, drums, symbolic density, and energy
- regression overlay lane for beat drift and exported-event comparison
- lane-item detail hovercards opened directly from clicked timeline regions
- raw JSON inspector for any successfully loaded file
- explicit missing-core-artifacts warning card for partial song folders

## Primary Data Sources

The current UI attempts to load these files:

### Primary artifact-side files

- `data/artifacts/<Song - Artist>/essentia/fft_bands.json`
- `data/artifacts/<Song - Artist>/essentia/rms_loudness.json`
- `data/artifacts/<Song - Artist>/essentia/loudness_envelope.json`
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

- `ui/src/lib/config/artifactDefinitions.js`: declares the files the debugger tries to load for each song
- `ui/src/lib/data/fetch.js`: reads JSON files from the mounted `/data` tree and parses directory listings
- `fetchDirectoryListing(...)`: parses the Nginx autoindex HTML for `/data/artifacts/` and extracts per-song folders
- `App.jsx`: keeps root composition thin and delegates real work to app hooks and view helpers
- `ui/src/app/useSongData.js`: coordinates discovery, artifact loading, query-string song selection, and waveform decoding setup
- `ui/src/app/usePlaybackState.js` and `ui/src/app/usePlaybackActions.js`: keep audio timing and transport actions out of the render tree
- `ui/src/components/Sidebar/`, `ui/src/components/OverviewPanels/`, `ui/src/components/DetailPanels/`, `ui/src/components/OverlayPanel/`, and `ui/src/components/SelectionDetailCard/`: declarative panel rendering with local helper modules kept close to the parent component
- `ui/src/components/TimelinePanel/`: owns viewport composition, transport header wiring, song-menu behavior, and interaction hooks while delegating lane rendering to `ui/src/lib/timeline/`
- `ui/src/lib/timeline/`: renders sparse lane markup, draws dynamic lanes, and updates shared now-marker positions

The timeline now also reads optional human reference hints from `data/reference/<Song - Artist>/human/human_hints.json` and renders them as a sparse lane between the waveform anchor and sections. Missing reference hints stay explicit in the file list and simply leave that lane empty.

## LLM Update Guidelines

Use these rules when making helper UI changes with an LLM agent.

### Preserve the layer boundaries

- Put shared state and side effects in `ui/src/app/`.
- Put rendering-only component helpers beside the component they support.
- Put reusable browser infrastructure in `ui/src/lib/`.
- Do not move app state into `ui/src/lib/`.
- Do not put canvas drawing or DOM math into `App.jsx` or overview/sidebar components.

### Prefer colocated, non-recursive helpers

- Keep functions near the closest parent that owns the behavior.
- Do not create helper chains that only forward props through multiple files without adding real separation.
- Do not create recursive component trees or recursive render helpers for lanes, panels, or menu structures.
- Do not reintroduce giant "manager" files that both load data and render markup and handle DOM events.
- If a file grows past roughly 100 lines, first look for a natural split by responsibility inside the same parent folder.

"Avoid recursion" here means more than avoiding literal self-calls. It also means avoiding architectural recursion where a component delegates to a helper that delegates to another helper that eventually just reconstructs the same parent concerns in a harder-to-follow shape.

### Keep entrypoints stable

- Prefer importing config/data/timeline helpers through `ui/src/lib/config.js`, `ui/src/lib/data.js`, and `ui/src/lib/timeline.js`.
- Add new submodules behind those entrypoints instead of scattering deep imports across the app.
- Keep top-level files such as `App.jsx` and `TimelinePanel/index.jsx` as composition layers, not logic dumps.

### Preserve read-only and artifact-first behavior

- Do not add write paths, mutation endpoints, or client-side persistence for review data.
- Keep artifact-side files as the primary source of truth.
- Keep output-side files as helper context only.
- Treat `data/reference/` as optional read-only context.

### Validate after edits

After UI changes, validate all of the following:

- editor diagnostics for `ui/src/`
- line-count pressure if a refactor was part of the change
- `docker compose up -d --build ui`
- browser load against a real song such as `?song=ayuni`
- lane/file status behavior when optional files like human hints are present or absent

For structural refactors, also confirm that:

- `ui/src/lib/config.js`, `ui/src/lib/data.js`, and `ui/src/lib/timeline.js` still work as stable import surfaces
- component-local helpers stay inside the closest component folder instead of drifting into unrelated shared modules
- app-owned hooks in `ui/src/app/` still own shared state rather than pushing it down into timeline-only files

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
docker compose up -d --build ui
curl -s http://localhost:8080 | head
curl -s http://localhost:8080/data/artifacts/ | head
```

For a live browser verification pass, also load a real song:

```text
http://localhost:8080/?song=ayuni
```

For a smoke check after a larger refactor, verify all of the following in the running page:

- the song dropdown populates from `/data/artifacts/`
- the selected song loads without console/runtime errors
- `Reference Human Hints` appears in the file list when available
- `Human Hints` appears between `Waveform Anchor` and `Sections`
- timeline controls still respond and the viewport still scrolls and updates markers

For shutdown or clean rebuild cycles, use:

```bash
docker compose up -d ui
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
