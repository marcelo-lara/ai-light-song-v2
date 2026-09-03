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

## The four phases

The pipeline is layered so that §2's honesty rules are enforceable — there is a
line past which everything is a claim that can be wrong
([`docs/constitution.md`](docs/constitution.md) §5).

| Phase | Reads | Produces |
| --- | --- | --- |
| 1 **measure** | audio | facts that cannot be musically wrong — beat grid, loudness, spectra, chroma, stems |
| 2 **interpret** | phase 1 + audio | claims — chords, key, sections and their names, note/drum events, genre |
| 3 **relate** | phase 2 only, **never audio** | identity, repetition, transitions, phrase structure, composite gestures |
| 4 **publish** | phases 1-3 | the projected deliverables, and nothing else |

The 1/2 line is **not** DSP vs. ML (stems, beats and transcription all use
models); it is *does this stage assert something that could be musically wrong?*
Phase 1 carries no confidence field; phase 2 onward always does. Phase 3 may
refine phase 2 but writes a new artifact — never mutates. Validation and the
human/reference loop are orthogonal to all four, not stages within them.

The current code does not yet follow this. Adopt it as the shape of the
segmentation rewrite rather than as a re-filing pass (§5.6).

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

### Removed — Epic 7 is gone

`light_design.py`, `lighting.py` and `beatdrop_visualizer.py` (~1,066 lines) and
their outputs `lighting_score.md`, `lighting_events.json` and
`beatdrop_visual_plan.json` were deleted on 2026-09-02. None appeared in the MCP
input contract; `data/fixtures/` never existed; and the lighting-score stage had
been throwing on every run with its failure swallowed by a bare `except`. Out of
scope per constitution §1.1 — do not reintroduce them.

### Known-good direction (researched, not yet implemented)

`allin1` for named functional segments on an 8-bar phrase grid, plus MERT-v1-95M
self-similarity for section *identity* (which other sections are "the same
one"). On Titanium the two models independently agree on every segment. A
**drop should be derived from a named section-pair transition, not detected
directly** — CLAP ranks *"the drop, the beat slams back in"* near the bottom of
26 probes while *"the chorus, the biggest and catchiest part"* ranks top.
Nothing from this is in `src/` yet.

The first half of that is now an experiment with output you can audition:
[`experiments/allin1/`](experiments/allin1/README.md) exports named sections and
their transitions per song and renders them as two debugger lanes. Its
transitions reach **4/7 impacts at ±1.0 s while proposing 1.6 boundaries/min**
against the incumbent's 0/7 at 3.6/min — and the incumbent also loses to an
evenly spaced grid at the same budget. **Not promoted**; §3.3 promotion has not
been asked for. Identity is still missing, and the model's own beat grid should
not be used (four songs land a clean half-beat off essentia's, one halves the
tempo).

**Character is a separate deliverable from arrangement, and it is measured.**
The operator hand-marks blocks like `Armin - Revolution` `hint-006` — "Breath",
81.4-96.3, *"Vocal - no intense section"*, lit as "soft motion of moving heads,
parcans slow violet waves". That is a texture fact, not a verse/chorus fact, and
no shipped artifact carries it. [`experiments/clap/`](experiments/clap/README.md)
finds it from the stems plus one CLAP axis (calm vs intense), and adding that
axis cuts the detector's false territory from 73 % of the corpus to 41 % with no
loss. Ask CLAP how a passage *feels*; never what is playing — its drum and bass
probes are confidently wrong where the stems are exact. allin1 contributes
**shadow labels** here: with `include_activations=True` its frame-level
posterior holds sustained mass on labels its own 8-bar segmentation never used,
which is how a breakdown inside an `inst` stretch becomes visible.

**Identity is measured and still open.** No section identity reaches the
authoring model at all: `sections/form.py` computes a `repetition_group` and
`ui_data.py` copies it into the projected `sections.json`, but it is `null` on
every section of all 21 songs, so the key is dropped on write.
[`experiments/clap/`](experiments/clap/README.md) tried CLAP embeddings for it
and **lost to 20 MFCC coefficients** (mean pair AUC 0.68 vs 0.73). Its useful
finding: CLAP scores 0.83 at telling a section from *itself* and 0.68 at
matching two occurrences of the same part, so identity needs a representation
trained for invariance between occurrences — not a bigger general-purpose
embedding. **MFCC 0.73 is the number any next attempt must beat.**

## Documentation conventions

| Location | Status | How to treat it |
| --- | --- | --- |
| `CLAUDE.md`, `README.md`, `docs/` | **Current** | Contracts. `docs/` holds current material only. Keep in sync with code; delete a doc in the change that makes it stale. |
| `docs/issues.md` | **Open** | The issue queue — **pending issues only**; solving one means deleting the entry in the same change (§4.2). Currently empty. |
| *(git history)* | **Historical** | Git history is the archive. 45 story specs, the release plans, the closed issues and the superseded worklist were deleted in `c227bec` and after. Recover with `git log --diff-filter=D --name-only` if you need one — but they are **not** specifications, and current behaviour is defined by `src/`. |
| `docs/experiments_pending.md` | **Queue** | One entry per experiment — its plan, its measured results, its conclusion (constitution §3.4). A concluded entry leaves only when the operator picks archive or promote; `docs/archive/experiments.md` is where it goes, and is the one archive file the docs rule permits. |
| `experiments/` | **Measured evidence** | Reproducible experiments and their outputs. The best available statement of what actually works. |

`docs/constitution.md` was rewritten on 2026-09-02. Its former rules — *"if the
code and the documentation disagree, the documentation is assumed correct"* and
*"every new feature must be introduced via a Story file"* — are what produced 45
story specs for behaviour that had since changed. Both are gone, and so are the
story specs. **Do not create a new numbered story file**, and **do not add an
archive folder**: a document that stops being true gets deleted in a commit. The
sole exception is `docs/archive/experiments.md`, defined in constitution §3.4.

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
- **Experiments are first-class, and stay out of `src/`.** `experiments/` is a
  sandbox for anything — any model, any dependency, any throwaway code; `src/`
  never imports from it. State a question and a measurement up front, score
  against the incumbent *and* a cheap baseline, and write down negative results.
  Give time-bearing output a debugger lane so it can be auditioned against the
  song (copy the **Drop Proposals** lane: written to
  `reference/proposals/`, rendered under **Human Hints**). When something beats
  the incumbent, **ask before promoting it to `src/`** — and say what gets
  deleted in the same change. Constitution §3.
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
| `experiments/allin1/` | Named functional structure from All-In-One — proposal files plus two review lanes. Not promoted. |
| `experiments/clap/` | Character blocks beyond the arrangement (stems + CLAP calm axis + allin1 shadow labels), and the negative identity result. Not promoted. |

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
