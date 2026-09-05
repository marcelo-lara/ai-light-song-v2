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
human-marked drop impacts, plus `reference/moises/` — a second model's
inference, not ground truth, but 5-200× more evaluation signal, see
[`docs/contract-change-v3.0.md`](docs/contract-change-v3.0.md)), full write-up
and reproduction in
[`experiments/drop_detection/README.md`](experiments/drop_detection/README.md).
This section was rewritten for v3.0
([`docs/implementation-plan-v3.0.md`](docs/implementation-plan-v3.0.md)) — the
segmenter and event stack it used to describe as "not trusted" are deleted, and
the two stages that replaced them carry their own honest, mixed measurements
below rather than a bare "not trusted" label.

### Trusted — deterministic DSP, roughly 1,950 lines

Stems (`stems.py`), the beat-*time* grid (`timing.py`), FFT bands, loudness,
HPCP and chords (`harmonic.py`), drums (`drums.py`), energy features
(`energy.py`). Byte-reproducible and independently checked. Beat tracking is
good — **7/7 human impacts land within 0.25 s of an essentia beat**, and beat
*times* stay essentia's throughout this release; only the downbeat *phase*
(below) changed. Chord agreement with a second model (Moises) varies widely by
song — 1.00 / 0.69 / 0.51 / 0.38 exact root+quality on the four gold songs — so
treat individual chord labels as informative, not settled; `sections.json`'s
projected `chord_progression` field is gated on exactly this uncertainty (see
below).

### Structure — `segmentation.py`, replacing the old `sections/` segmenter

`stages/sections/` (1,403 lines of deterministic-DSP phrase detection plus an
invented 13-value `section_character` mood vocabulary) is deleted. It measured
**0/7 within ±1.0 s** against hand-marked impacts and 0.29 F1 against 38 Moises
segment boundaries — worse than an evenly spaced grid at the same boundary
budget. It is replaced by `stages/segmentation.py`, which runs All-In-One
(Kim & Nam, ISMIR 2023) seeded with the pipeline's own stems and merges its
8-bar phrase segments into named song-form section runs.

> Measured against 38 interior boundaries in `reference/moises/segments.json`
> across the four gold songs: **recall 0.53, precision 0.91, F1 0.67** at
> ±1.0 s, against the old segmenter's 0.32 / 0.27 / 0.29. Full numbers:
> [`docs/contract-change-v3.0.md`](docs/contract-change-v3.0.md) §7.

This is a real improvement, not a solved problem: `function_status: "unknown"`
is set explicitly on every row of a song where allin1's own labelling is
degenerate, and `same_label_as` means label repetition ("the third thing
called a chorus"), **not** verified acoustic identity — see "Identity" below.

### Downbeats — taken from allin1, with an honest shortfall

The old `beat_in_bar` assignment was pure modulo — there was no downbeat
*detection* in this pipeline at all, and it measured 0.16 F1 @±70 ms against
385 Moises-labelled downbeats. `timing.py` now derives the downbeat *phase*
(never the beat times) from allin1's own `downbeat` frame activation, with a
per-downbeat `confidence` and an honest `null` where essentia's and allin1's
phases disagree by a whole beat or more.

**Measured result: combined F1 is 0.226 — short of the 0.50 target set for
this item.** Say this plainly rather than rounding up: two of the four gold
songs individually clear 0.50 (`_test_song` 0.604, `Armin - Revolution`
0.593); `Titanium - David Guetta ft Sia` scores 0 because allin1's own downbeat
activation confidently disagrees with the reference phase by ~2 beats (its
*beat* grid was independently confirmed correctly aligned first); `Hideaway -
Kiesza` scores 0.050 because essentia's own beat *tracker* — unchanged by this
item — finds a different tempo than the reference on that one song, the single
gold-set case where essentia trails Moises. Neither failure is fixable within
this item's scope without fabricating a downbeat allin1 doesn't support
(forbidden — constitution §2) or reworking essentia's beat tracker. Full
root-cause writeup: [`docs/contract-change-v3.0.md`](docs/contract-change-v3.0.md)
§8. **Bar numbers are therefore still not to be assumed correct** — treat a
`null`-confidence downbeat exactly as the honest "we don't know" it is, not as
a snapped guess.

### Gestures — `gestures.py`, replacing the whole `event_*` stack

The Epic-5 `event_*` chain (`event_rules/`, `event_machine/`,
`event_features/`, `event_timeline.py`, `event_review.py`,
`event_identifiers.py`, `review_queue.py`, `event_contracts.py`,
`_stem_activity.py` — ~3,800 lines) measured **0/7 @±0.25 s, 2/7 @±1.0 s**
against hand-marked drop impacts, largely on the strength of `layer_add`/
`layer_remove` — a per-beat energy delta with one of three template sentences
attached, 52% of the events it ever emitted. It is deleted and replaced by one
phase-3 stage, `stages/gestures.py`, which reads only trusted phase-1/2
artifacts (never audio) and assembles named-primitive detectors (riser,
downlifter, reverse cymbal, snare roll, pre-drop gap, impact) into gesture
phases (`approach → build → tension → impact → release`) anchored on a
detected impact.

> Measured: **4/7 @±1.0 s, 2/7 @±0.25 s** against the incumbent's 2/7 and 0/7.
> A phase absent from a gesture (e.g. no `tension` row) means no supporting
> primitive was found for it — never guessed. A drop is still never named
> directly; naming stays with the section-pair transition (constitution §5.2).
> Full numbers: [`docs/contract-change-v3.0.md`](docs/contract-change-v3.0.md)
> §9.

### Removed in v3.0

Roughly 6,000 lines and ~20 MB/song of per-song artifact left `src/` in this
release (full list and rationale: `docs/implementation-plan-v3.0.md`,
`docs/product-refinement-v3.0.md`):

- **The ML event stack** (`event_ml.py` + training script + seeded models,
  1,080 lines) — 0 events on 21 of 21 songs.
- **`event_benchmark.py`** — `status: "skipped"` on 21 of 21 songs; the
  annotation directory it scored against never existed in the tree.
- **`unified.py`** (`music_feature_layers.json`) — a re-packaging of files
  nothing downstream read.
- **`patterns.py`** — chord-pattern mining that reached no projected file.
- **Symbolic note transcription** (`symbolic/`, Basic Pitch, ~1,341 lines,
  7.0 MB/song) — its only route to the authoring model was a templated
  `motif_recall` hint sentence, itself deleted in the `hints.json` rebuild.
  `drums.py` and its own Omnizart transcription path are unaffected.
- **The whole `event_*` stack** — see "Gestures" above.
- **The old `stages/sections/` segmenter** — see "Structure" above.
- **The Moises takeover of the canonical grid** — `run_phase_1` no longer ever
  substitutes `reference/moises/`-derived beats or chords for the pipeline's
  own output; `reference/` is validation-only, never a generation input
  (constitution §2, §9).
- **Validation targets with no labels** (`validation/events.py`,
  `validation/energy.py`, the `form` target) — `--compare` now supports
  `beats`, `chords`, `sections`, `drums`, `drops` only.

`light_design.py`, `lighting.py` and `beatdrop_visualizer.py` (~1,066 lines)
and their outputs `lighting_score.md`, `lighting_events.json` and
`beatdrop_visual_plan.json` were deleted separately, on 2026-09-02 (Epic 7).
None appeared in the MCP input contract; `data/fixtures/` never existed; and
the lighting-score stage had been throwing on every run with its failure
swallowed by a bare `except`. Out of scope per constitution §1.1 — do not
reintroduce any of this.

### Character is a separate deliverable from arrangement, and it is measured

The operator hand-marks blocks like `Armin - Revolution` `hint-006` — "Breath",
81.4-96.3, *"Vocal - no intense section"*, lit as "soft motion of moving heads,
parcans slow violet waves". That is a texture fact, not a verse/chorus fact,
and no shipped artifact carries it. [`experiments/clap/`](experiments/clap/README.md)
finds it from the stems plus one CLAP axis (calm vs intense), and adding that
axis cuts the detector's false territory from 73% of the corpus to 41% with no
loss. Ask CLAP how a passage *feels*; never what is playing — its drum and bass
probes are confidently wrong where the stems are exact. allin1 contributes
**shadow labels** here: with `include_activations=True` its frame-level
posterior holds sustained mass on labels its own 8-bar segmentation never used,
which is how a breakdown inside an `inst` stretch becomes visible. **Not in
`src/` for v3.0** — see `docs/experiments.md`, which keeps this as its
own open entry (the CLAP experiment's *identity* result, immediately below,
is archived as promoted; its character-layer idea is not).

### Identity is measured and still open — the largest remaining gap

No section identity reaches the authoring model. `same_label_as` (new in
v3.0's `sections.json`) is **label repetition**, not acoustic identity — it
says "the third thing allin1 called a chorus," never "this is the same music as
the first chorus." [`experiments/clap/`](experiments/clap/README.md) tried CLAP
embeddings for real identity and **lost to 20 MFCC coefficients** (mean pair
AUC 0.68 vs 0.73). Its useful finding: CLAP scores 0.83 at telling a section
from *itself* and 0.68 at matching two occurrences of the same part, so
identity needs a representation trained for invariance between occurrences —
not a bigger general-purpose embedding. **MFCC 0.73 is the number any next
attempt must beat.** This CLAP result is archived as concluded
(`docs/archive/experiments.md`); a follow-on invariance-trained-embedding
attempt is queued in `docs/experiments.md`.

## Documentation conventions

| Location | Status | How to treat it |
| --- | --- | --- |
| `CLAUDE.md`, `README.md`, `docs/` | **Current** | Contracts. `docs/` holds current material only. Keep in sync with code; delete a doc in the change that makes it stale. |
| `docs/issues.md` | **Open** | The issue queue — **pending issues only**; solving one means deleting the entry in the same change (§4.2). Currently empty. |
| *(git history)* | **Historical** | Git history is the archive. 45 story specs, the release plans, the closed issues and the superseded worklist were deleted in `c227bec` and after. Recover with `git log --diff-filter=D --name-only` if you need one — but they are **not** specifications, and current behaviour is defined by `src/`. |
| `docs/experiments.md` | **Queue** | One entry per experiment — its plan, its measured results, its conclusion (constitution §3.4). A concluded entry leaves only when the operator picks archive or promote; `docs/archive/experiments.md` is where it goes, and is the one archive file the docs rule permits. |
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
| `data/analysis/<Song - Artist>/` | Stable deliverables — exactly the five top-level files (`info.json`, `beats.json`, `hints.json`, `sections.json`, `song_event_timeline.json`), plus `artifacts/`. |
| `data/analysis/<Song - Artist>/artifacts/` | Intermediates, producer-scoped (`essentia/`, `section_segmentation/`, `allin1/`, …). |
| `data/analysis/<Song - Artist>/reference/` | Human and external ground truth. Read-only to the pipeline. |
| `ui/` | Read-only artifact debugger (React + TS + Vite). Never writes to `data/analysis/`. |
| `experiments/drop_detection/` | Drop-detector experiment and the pretrained-model survey. |
| `experiments/allin1/` | Named functional structure from All-In-One. **Promoted in v3.0** into `src/analyzer/stages/segmentation.py`; the experiment's own README and measurements stay as the record of how the promotion was justified. |
| `experiments/gestures/` | Named gesture-phase detection (riser/downlifter/snare-roll/pre-drop-gap/impact primitives). **Promoted in v3.0** into `src/analyzer/stages/gestures.py`. |
| `experiments/clap/` | Character blocks beyond the arrangement (stems + CLAP calm axis + allin1 shadow labels), and the negative identity result. The identity result is archived as concluded (`docs/archive/experiments.md`); the character-layer idea is still queued (`docs/experiments.md`) and not in `src/`. |

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
