# Analysis definition — the pipeline, and how good each part is

The **what** and the **how honest**. Every stage, which phase it belongs to, and
what it measures against ground truth. Read this before trusting any output.

- Why the system exists: [`product-definition.md`](product-definition.md)
- Rules you must not break: [`../CLAUDE.md`](../CLAUDE.md) "Rules that are load-bearing"
- What reaches the authoring model: [`mcp-definition.md`](mcp-definition.md)
- Exact fields and paths: [`reference/artifacts.md`](reference/artifacts.md)

> `STAGE_PIPELINE_IDS` in [`../src/analyzer/pipeline.py`](../src/analyzer/pipeline.py)
> is the **authoritative** stage list, ahead of any prose here. Each stage's
> module docstring carries its own measured numbers and caveats.

---

## The four phases

The split is not organisational tidiness. It puts a line in the codebase past
which everything is a claim that can be wrong, which is what makes the honesty
rules enforceable.

The test for the 1/2 line is **not** DSP vs. ML — stems, beat tracking and
transcription all use trained models, and excluding them would leave phase 1
empty. The test is: **does this stage assert something that could be musically
wrong?** A loudness curve cannot be wrong; it is a measurement. A chord label
can. A section name can.

Four rules govern the phases:

1. **Phase 1 carries no `confidence` field**, because there is nothing to be
   uncertain about. From phase 2 onward, confidence and provenance are mandatory.
2. **Phase 3 is defined by its input, not its determinism.** Chord-pattern
   mining is deterministic arithmetic and still belongs in phase 3. The rule is
   structural: phase 3 reads phase 2's output and **never opens the audio**.
   That is what makes it the layer where the show gets its shape — which
   sections are the same one returning, that a transition is `chorus → inst`,
   that a **drop is derived from a named section pair rather than detected**.
   Inferring a composite gesture straight from raw features, without named
   structure to hang it on, is the mistake this phase exists to prevent.
3. **Feedback is allowed; mutation is not.** Phase 3 may improve on phase 2 —
   snapping a boundary to a phrase grid it derived — but it writes a *new*
   artifact with provenance. It never edits phase 2's output in place. Once a
   later phase can silently overwrite an earlier one, it stops being possible to
   say which stage was wrong.
4. **Phase 4 publishes everything that ships, and nothing else.** A signal that
   reaches no projected file did not ship, whatever earlier phases computed.

Re-filing existing stages is not the point and is not worth doing on its own.
The phases are the shape a *rewrite* takes: replacement structural inference
lands as phase 2, identity and transitions as phase 3, and code belonging to
neither is deleted rather than relocated.

### Phase 1 — measure (audio in; facts that cannot be musically wrong)

| Module | Produces |
| --- | --- |
| `stems.py` | Demucs separation → `artifacts/stems/{bass,drums,harmonic,vocals}.wav`, seeded |
| `timing.py` | `artifacts/essentia/beats.json` — essentia beat *times* plus allin1-derived downbeat *phase* |
| `fft_bands.py` | `artifacts/essentia/fft_bands.json` — 7 fixed bands every 50 ms |
| `loudness.py` | `artifacts/essentia/rms_loudness.json` (10 ms) and `loudness_envelope.json` (200 ms), per source |

No `confidence` field anywhere in phase 1 — there is nothing to be uncertain about.

### Phase 2 — interpret (phase 1 + audio; claims that can be wrong)

| Module | Produces |
| --- | --- |
| `harmonic.py` | `artifacts/essentia/hpcp.json`, `artifacts/layer_a_harmonic.json` — HPCP, global key, chord events; also projects compact `key` / `chord_progression` into `sections.json` |
| `drums.py` | `artifacts/symbolic_transcription/drum_events.json` — Omnizart drum hits on the isolated drums stem |
| `genre.py` | `artifacts/genre.json` — genre with honest confidences and `guidance` prose |
| `segmentation.py` | `artifacts/section_segmentation/sections.json` — All-In-One named functional segmentation |
| `energy.py` | `artifacts/layer_c_energy.json` — energy states, per-section cards, accent candidates |

Chroma extraction and chord decoding stay **two stages, not one** — fusing them
would make a chroma bug and a decoding bug indistinguishable in the artifact,
which is exactly the ambiguity that made past chord issues hard to attribute.

### Phase 3 — relate (phase 2 only, **never audio**)

| Module | Produces |
| --- | --- |
| `gestures.py` | `song_event_timeline.json` — gesture phases + section-pair transitions |
| `hint_alignment.py` | `find_primary_section`, the shared window→section matcher |

### Phase 4 — publish

| Module | Produces |
| --- | --- |
| `hints.py` | `hints.json` — inference hints merged with `reference/human/human_hints.json` |
| `ui_data.py` | `sections.json`, `beats.json`, `info.json` — the compact top-level deliverables |

### Validation — orthogonal to all four

`validation/{beats,chords,sections,drums,drops}.py` score generated artifacts
against `reference/`; `report.py` aggregates into
`artifacts/validation/phase_1_report.{json,md}`.

Validation and the human/reference loop **observe** every phase rather than
occupying a position in the sequence, and must not be interleaved as ordinary
stages — doing so is what previously scattered `validate-beats` and
`validate-chords` through the middle of extraction. Human corrections may enter
at any phase, subject to the promotion rules.

### Shared infrastructure

| Module | Role |
| --- | --- |
| `cli.py` | `./analyze` / `python -m analyzer` argument parsing |
| `pipeline.py` | the stage DAG; `STAGE_PIPELINE_IDS` is authoritative |
| `allin1_cache.py` | runs All-In-One **once per song**, seeded with the pipeline's own stems, cached to `artifacts/allin1/raw.json`. Both `timing.py` (downbeat phase) and `segmentation.py` read it |
| `paths.py` | `SongPaths` — all `/data/` path resolution |
| `models.py`, `io.py`, `config.py`, `exceptions.py` | schema version, disk I/O, CLI config, error types |
| `_omnizart_runtime.py` | subprocess isolation for Omnizart |

---

## What to trust

Measured against hand-labelled ground truth on the four gold songs
(`_test_song`, `Titanium - David Guetta ft Sia`, `Armin - Revolution`,
`Hideaway - Kiesza`; 7 human-marked drop impacts), plus `reference/moises/` — a
second model's *inference*, not ground truth, but 5–200× more evaluation signal.
Reproduction: [`../experiments/drop_detection/README.md`](../experiments/drop_detection/README.md).

### Trusted — deterministic DSP, ~1,950 lines

`stems.py`, the beat-*time* grid in `timing.py`, `fft_bands.py`, `loudness.py`,
`harmonic.py`, `drums.py`, `energy.py`. Byte-reproducible and independently
checked.

- **Beat tracking is good.** 7/7 human-marked impacts land within 0.25 s of an
  essentia beat. Beat times are essentia's throughout.
- **Chord labels are informative, not settled.** Root+quality agreement with
  Moises varies widely by song: **1.00 / 0.69 / 0.51 / 0.38** across the four
  gold songs. `sections.json`'s `chord_progression` is confidence-gated on
  exactly this uncertainty, and `null` there is honest, not a bug.

### Structure — `segmentation.py`, a real improvement, not solved

Replaced `stages/sections/` (1,403 lines of deterministic-DSP phrase detection
plus an invented 13-value `section_character` vocabulary), which measured **0/7
within ±1.0 s** of hand-marked impacts and **0.29 F1** against 38 Moises segment
boundaries — worse than an evenly spaced grid at the same boundary budget.

| Against 38 interior boundaries, ±1.0 s | recall | precision | F1 |
| --- | --- | --- | --- |
| `segmentation.py` (allin1) | **0.53** | **0.91** | **0.67** |
| old `sections/` segmenter | 0.32 | 0.27 | 0.29 |

Honest caveats that ship with it:

- `function_status: "unknown"` is set on **every row** of a song where allin1's
  own labelling is degenerate (fewer than 3 distinct labels, or one label over
  90% of the track). The boundary stays usable; the name does not.
- `function_confidence` is `1 −` normalised Shannon entropy of allin1's
  frame-level label posterior over the section's span — how sure the *model* was.
- `same_label_as` means **label repetition** — "the third thing allin1 called a
  chorus" — never verified acoustic identity. See "Known gaps".

### Downbeats — honest, and short of target

The old `beat_in_bar` was pure modulo: there was no downbeat *detection* at all,
and it scored **0.16 F1 @±70 ms** against 385 Moises downbeats.
`timing.py` now derives the downbeat *phase* (never the beat times) from
allin1's `downbeat` frame activation, by majority vote of local arg-maxes in
16-bar windows — a single song-wide offset was tried first and scored worse than
the modulo baseline.

**Combined F1 is 0.226 — short of the 0.50 target.** Stating that plainly
matters more than rounding up:

| Song | F1 | Why |
| --- | --- | --- |
| `_test_song` | 0.604 | clears target |
| `Armin - Revolution` | 0.593 | clears target |
| `Titanium - David Guetta ft Sia` | 0.000 | allin1's activation confidently peaks (0.24–0.47) where the reference calls beat 3 and sits near zero (~0.001–0.02) at the true downbeat — a reproducible ~2-beat disagreement. Its *beat* grid was independently confirmed aligned to ~10 ms first, so this is not an indexing bug |
| `Hideaway - Kiesza` | 0.050 | essentia's beat *tracker* — untouched by this work — finds ~0.66 s intervals against the reference's ~0.48 s. The one gold song where essentia trails Moises. No phase choice on a wrong-tempo grid can land within ±70 ms |

Neither failure is fixable without fabricating a downbeat allin1 does not
support (forbidden — never invent a plausible default) or reworking essentia's beat tracker.

**Bar numbers are therefore not to be assumed correct.** A `null` confidence is
the honest "we don't know", not a snapped guess — `validate_beats` excludes
`null` rows from the predicted set entirely, because an abstention is not a claim.

### Gestures — `gestures.py`, better than what it replaced

Replaced the ~3,800-line Epic-5 `event_*` chain, which measured **0/7 @±0.25 s
and 2/7 @±1.0 s** — largely on the strength of `layer_add`/`layer_remove`, a
per-beat energy delta with one of three template sentences attached, and 52% of
every event it ever emitted.

| @±1.0 s | @±0.25 s | |
| --- | --- | --- |
| **4/7** | **2/7** | `gestures.py` |
| 2/7 | 0/7 | old `event_*` stack |

It reads only trusted phase-1/2 artifacts and assembles named primitives
(riser, downlifter, reverse cymbal, snare roll, pre-drop gap, impact) into
phases `approach → build → tension → impact → release` anchored on a detected
impact. A phase absent from a gesture means **no supporting primitive was
found** — never guessed. **A drop is never named directly**; naming stays with
the section-pair transition.

---

## Known gaps

### Identity — the largest remaining gap

No section identity reaches the authoring model. `same_label_as` is label
repetition, not acoustic identity. [`../experiments/clap/README.md`](../experiments/clap/README.md)
tried CLAP embeddings and **lost to 20 MFCC coefficients** (mean pair AUC 0.68
vs 0.73). The useful finding: CLAP scores 0.83 at telling a section from
*itself* but 0.68 at matching two occurrences of the same part — so identity
needs a representation trained for **invariance between occurrences**, not a
bigger general-purpose embedding. **MFCC 0.73 is the number any next attempt
must beat.** Archived as concluded; a follow-on is queued in
[`experiments.md`](experiments.md).

### Character blocks — measured, not shipped

The operator's hand-marked texture blocks (`Armin - Revolution` `hint-006`,
"Breath") are a deliverable no artifact carries. [`../experiments/clap/README.md`](../experiments/clap/README.md)
finds them from the stems plus one CLAP axis (calm vs intense), cutting the
detector's false territory from 73% of the corpus to 41% with no loss.

Two rules from that work: **ask CLAP how a passage *feels*, never what is
playing** — its drum and bass probes are confidently wrong where the stems are
exact. And allin1 contributes **shadow labels**: with `include_activations=True`
its frame-level posterior holds sustained mass on labels its own 8-bar
segmentation never used, which is how a breakdown inside an `inst` stretch
becomes visible. Not in `src/`; open in [`experiments.md`](experiments.md).

### Gesture precision has never been audited

Gestures are scored on impact *recall*. A phantom primitive — a riser or tension
span asserted where the music has none — moves that metric not at all, yet fires
a cue that contradicts the song. Tracked in [`issues.md`](issues.md).

---

## Deleted in v3.0 — do not reintroduce

~6,000 lines and ~20 MB/song of per-song artifact left `src/` in this release.
Recover any of it with `git log --diff-filter=D --name-only`.

| Removed | Why |
| --- | --- |
| The ML event stack (`event_ml.py`, training script, seeded models) | 0 events on 21 of 21 songs |
| `event_benchmark.py` | `status: "skipped"` on 21 of 21 songs; the annotation directory it scored against never existed |
| `unified.py` (`music_feature_layers.json`) | a re-packaging of files nothing downstream read |
| `patterns.py` | chord-pattern mining that reached no projected file |
| Symbolic note transcription (`symbolic/`, Basic Pitch, ~1,341 lines, 7.0 MB/song) | its only route to the model was a templated `motif_recall` hint sentence, itself deleted. `drums.py` and its Omnizart path are unaffected |
| The whole `event_*` stack (~3,800 lines) | measured at chance — see Gestures above |
| The old `stages/sections/` segmenter (1,403 lines) | measured at chance — see Structure above |
| The Moises takeover of the canonical grid | `run_phase_1` no longer substitutes `reference/`-derived beats or chords. `reference/` is validation-only |
| `validation/events.py`, `validation/energy.py`, the `form` target | no labels to score against |
| `light_design.py`, `lighting.py`, `beatdrop_visualizer.py` (~1,066 lines) | out of scope; removed 2026-09-02; the lighting-score stage had been throwing on every run with its failure swallowed by a bare `except` |
