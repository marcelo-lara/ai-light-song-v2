# CLAUDE.md — orientation for `ai-light-song-v2`

Read this before anything else in the repo. It says what the system does, which
parts are trustworthy, which parts are measured as broken, and which documents
are current versus historical.

## What this is

The **analysis module** of a three-part stage-lighting system. It turns a song
into structured musical analysis under `data/analysis/<Song - Artist>/`. A
separate MCP server projects small, token-budgeted views of that analysis to a
model that authors the light show. The show targets **moving-head fixtures**.

> **Scope.** This repo produces *concrete, reliable, precisely-timed musical
> facts that a reasoning model can author a production-quality light show from.*
> That is the whole job. It is the **foundation** of a light show, not the light
> show. **Fixture-aware orchestration, cue authoring, lighting-design documents
> and DMX are out of scope** and are handled downstream — see
> [`docs/constitution.md`](docs/constitution.md) §1.

The pipeline's job is therefore not "extract many features". It is to work out
**where the song changes, what each part is, and how the parts relate** —
precisely enough that a model reading only a compact projection can author cues.
Two things carry the show:

1. **Named structural parts and their transitions.** `intro → verse`, part A →
   part B. Knowing something is *different* at a given instant is what defines a
   cue.
2. **Composite gestures with internal phases.** A drop has an approach, a build,
   a tension span, an impact and a release; each maps to a different scene. A
   flat list of independent events loses the thing that matters.

## Standing priority: musical correctness over compatibility

Improving the quality of the musical read outranks preserving the current
artifact schema, field names, file set, or the MCP server's exact projection
shape. **Compatibility is explicitly not a priority.** When the existing shape
gets in the way of a more correct interpretation, propose changing the shape —
do not build a workaround. Judge a proposal by whether it makes the structural
read more correct and more honestly-confident, not by whether it adds signals or
preserves a contract.

## Current state — what to trust

Measured against hand-labelled ground truth on the gold set (`Titanium - David
Guetta ft Sia`, `Armin - Revolution`, `Hideaway - Kiesza`, `_test_song`; 7
human-marked drop impacts), full write-up and reproduction in
[`experiments/drop_detection/README.md`](experiments/drop_detection/README.md).

### Trusted — deterministic DSP, roughly 3,900 lines

Stems (`stems.py`), timing grid (`timing.py`), FFT bands, loudness, HPCP and
chords (`harmonic.py`), chord patterns (`patterns.py`), drums (`drums.py`),
symbolic features (`symbolic/`), energy features (`energy.py`). Byte-reproducible
and independently checked. Beat tracking is good — **7/7 human impacts land
within 0.25 s of an essentia beat**.

### Not trusted — structure and everything downstream, roughly 5,900 lines

`stages/sections/` plus the whole `event_*` stack (`event_rules/`,
`event_machine/`, `event_ml*`, `event_features/`, `event_timeline`,
`event_review`, `event_identifiers`, `event_benchmark`).

> The shipped `sections.json` boundaries land near a human-marked impact
> **0/7 within ±1.0 s and 1/7 within ±2.0 s** — worse than a 20-line librosa CQT
> baseline scored with the identical peak-picker (1/7 and 4/7). At the same
> boundary budget, `allin1` gets 4/7 and 6/7, and MERT layer 2 gets 5/7 and 7/7.

Whatever the current segmenter finds, it is not song form. Every event stage
downstream inherits those boundaries. Treat their outputs, and the story specs
describing them, as unvalidated.

**Bar grid caveat:** beat tracking is reliable, *downbeats are not*. Three
independent trackers (essentia, beat-this, allin1) hit 3/7, 3/7 and 4/7 and
disagree with each other in different places. Do not assume a correct bar grid.

### Legacy — no consumer

`stages/lighting.py`, `stages/light_design.py`, `stages/beatdrop_visualizer.py`
(~1,066 lines). Neither `lighting_score.md` nor `beatdrop_visual_plan.json`
appears in the MCP input contract, and `data/fixtures/` does not exist. Out of
scope per constitution §1.1. Do not extend them.

### Known-good direction (researched, not yet implemented)

`allin1` for named functional segments on an 8-bar phrase grid, plus MERT-v1-95M
self-similarity for section *identity* (which other sections are "the same
one"). On Titanium the two models independently agree on every segment. A
**drop should be derived from a named section-pair transition, not detected
directly** — CLAP ranks *"the drop, the beat slams back in"* near the bottom of
26 probes while *"the chorus, the biggest and catchiest part"* ranks top.
Nothing from this is in `src/` yet.

## Documentation conventions

| Location | Status | How to treat it |
| --- | --- | --- |
| `CLAUDE.md`, `README.md`, `docs/README.md`, `docs/constitution.md`, `docs/data_folder_reference.md`, `docs/source_files_reference.md`, `docs/docker_development.md`, `docs/reference/` | **Current** | Contracts. Keep in sync with code. |
| `docs/issues.md`, `docs/product-refinement-v2.2.md` | **Open** | Intent, not behaviour. `issues.md` holds **pending issues only** — solving one means moving it to `docs/archive/issues-solved.md` in the same change (§4.2). **Exactly one `product-refinement-*.md` lives in `docs/` at a time**, covering core, `ui/`, MCP and experiments together — constitution §4.1. Do not open a second one, and do not create per-component refinements or plans. |
| `docs/archive/` | **Historical** | 45 story specs, release plans, close-outs. **Not specifications.** Do not implement from them. Inside `archive/`, the code wins over the doc. |
| `experiments/` | **Measured evidence** | Reproducible experiments and their outputs. The best available statement of what actually works. |

`docs/constitution.md` was rewritten on 2026-09-02. Its former rules — *"if the
code and the documentation disagree, the documentation is assumed correct"* and
*"every new feature must be introduced via a Story file"* — are what produced 45
story specs for behaviour that had since changed. Both are gone. **Do not create
a new numbered story file**; document a change where a future reader will look
for it.

## Rules that are load-bearing

- **Docker only.** All analysis, validation and tests run inside the Compose
  services. Never propose host-installed Python or audio tooling.
- **Determinism.** Same input + engine version ⇒ byte-identical artifacts.
- **No silent fallbacks.** Fail explicitly, or emit `unknown`. Never invent a
  plausible default (a generic C-major chord, a guessed section label) to keep a
  run green. An honest `unknown` is worth more to the cue-authoring model than a
  confident wrong answer.
- **The reach test.** A feature is only real if it reaches the authoring model.
  Before building, say which projected file the signal lands in.
- **Experiments are first-class.** They live in `experiments/<topic>/`, state a
  question and a measurement up front, are scored against the incumbent *and* a
  cheap baseline, and a negative result gets written down rather than deleted.
  Constitution §3.
- **`reference/` is validation-only.** Never copy `data/analysis/<song>/reference/`
  into a generated artifact except through an explicit, confidence-gated,
  provenance-recorded promotion.
- **Time in seconds, bars 1-indexed**, beat-aligned outputs on the stage-1.2 grid.
- **Provenance.** Every generated file carries `generated_from`; schemas are versioned.
- Clean up temporary scripts and scaffolding; use the session scratchpad, not the repo.

## Running things

```bash
docker compose build

# full pipeline + validation report for one song
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3"

# whole corpus (21 songs), each in its own subprocess
docker compose run --rm app ./analyze --all-songs --device cuda

# a single stage (prerequisite artifacts must already exist)
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3" --stage segment-sections

# tests
docker compose run --rm test

# debugger UI at http://localhost:9090
docker compose up ui
```

Stage names come from `STAGE_PIPELINE_IDS` in
[`src/analyzer/pipeline.py`](src/analyzer/pipeline.py) — that dict is the
authoritative stage list, ahead of any prose. CLI reference:
[`docs/reference/phase_1_validation_cli.md`](docs/reference/phase_1_validation_cli.md).

Research sandboxes for the model survey are separate images and do not touch the
analyzer image: `experiments/drop_detection/research/run_in_container.sh`.

## Where things live

| Path | Contents |
| --- | --- |
| `src/analyzer/pipeline.py` | Stage registry and orchestration. Start here to understand execution order. |
| `src/analyzer/stages/` | One module or package per stage. |
| `src/analyzer/stages/validation/` | Scoring of generated artifacts against `reference/`. |
| `data/analysis/<Song - Artist>/` | Stable deliverables — exactly the seven top-level files, plus `artifacts/`. |
| `data/analysis/<Song - Artist>/artifacts/` | Intermediates, producer-scoped (`essentia/`, `section_segmentation/`, …). |
| `data/analysis/<Song - Artist>/reference/` | Human and external ground truth. Read-only to the pipeline. |
| `ui/` | Read-only artifact debugger (React + TS + Vite). Never writes to `data/analysis/`. |
| `experiments/drop_detection/` | Drop-detector experiment and the pretrained-model survey. |

## What actually reaches the light show

Only a handful of files are ever projected to the cue-authoring model:
`info.json`, `beats.json`, `sections.json` (+ `artifacts/section_segmentation/sections.json`),
`hints.json`, `song_event_timeline.json`, `artifacts/genre.json`, and — for
sub-section detail only — `artifacts/essentia/rms_loudness.json` and
`artifacts/symbolic_transcription/drum_events.json`.

**Everything else under `artifacts/` is invisible to cue authoring.** Polishing
a layer file's schema or prose changes nothing unless the signal is promoted
into one of the files above. Full contract:
[`docs/reference/analysis-input-guide.md`](docs/reference/analysis-input-guide.md).
