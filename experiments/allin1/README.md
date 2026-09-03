# Experiment — `allin1` for named song form

**Status: measured, not promoted.** Nothing in `src/` reads anything in here.
The output is reviewable in the debugger UI as two lanes; see *Review it* below.
Queue entry, with the same numbers in summary form:
[`../../docs/experiments_pending.md`](../../docs/experiments_pending.md)
(constitution §3.4).

## The question

The shipped section segmentation is measured at chance: its boundaries land near
a hand-placed `drop impact` **0/7 within ±1.0 s**, and its labels are mood
adjectives invented per section ("Momentum Lift", "Vocal Spotlight"), so nothing
in the artifact says *which part of the song* a section is, or that a returning
chorus is the same part as the first one.

> Can All-In-One (Kim & Nam, ISMIR 2023) supply what is missing — **named**
> functional sections, and **transitions between them**, placed accurately
> enough to hang a cue on?

Two things carry a light show: named structural parts and their transitions, and
composite gestures with internal phases. This experiment is about the first.
Section *identity* (which other sections are acoustically the same one, not just
identically labelled) is a second model's job and is **not** attempted here.

The prior survey in [`../drop_detection/README.md`](../drop_detection/README.md)
picked `allin1` as the thing to try next. This is that trial, taken to the point
where a human can audition it against the audio.

## How to run it

```bash
# build the sandbox image once (natten 0.15 / torch 2.1 — it cannot share the
# analyzer environment; the pinning is explained in the sibling experiment)
docker build -f experiments/drop_detection/research/Dockerfile.allin1 \
             -t ai-light-song-v2-allin1:dev .

# GPU step: run the model over the corpus and cache its raw output (~6 s/song)
./experiments/allin1/run_in_container.sh python -m experiments.allin1.run cache

# second GPU pass: the frame-level activations of Measurement 3
./experiments/allin1/run_in_container.sh python -m experiments.allin1.run cache-activations

# everything below reads the committed cache and needs no GPU and no allin1
python -m experiments.allin1.run export     # write the per-song proposal files
python -m experiments.allin1.run score      # the measurement tables -> out/score.txt
python -m experiments.allin1.run show "Titanium - David Guetta ft Sia"

# reproducibility check — calls the model repeatedly (needs the sandbox image)
./experiments/allin1/run_in_container.sh python -m experiments.allin1.run stability
```

`cache/` holds the raw model output for all 21 songs and is committed, so every
number below is reproducible without a GPU. `out/score.txt` and
`out/stability.json` are the generated evidence.

## Measurement 1 — boundary accuracy against the incumbent and a baseline

Gold set: the four songs carrying hand-placed `drop impact` marks, 7 impacts
total. Recall of those impacts, at a comparable boundary budget.

| method | ±0.5 s | ±1.0 s | ±2.0 s | boundaries/min |
| --- | --- | --- | --- | --- |
| **allin1 section transitions** | **3/7** | **4/7** | 4/7 | **1.6** |
| allin1 phrase edges (every segment row) | 3/7 | 4/7 | **6/7** | 3.3 |
| shipped `sections.json` (incumbent) | 0/7 | 0/7 | 1/7 | 3.6 |
| evenly spaced grid, same budget (baseline) | 0/7 | 2/7 | 3/7 | 3.6 |

Read three things off this:

* allin1's **merged** transitions reach 4/7 while proposing **less than half**
  the boundaries the incumbent does. Fewer, better-placed boundaries is the
  whole shape of the improvement.
* The incumbent does not beat **evenly spaced guesses**. That is the baseline
  every method has to clear to have found anything at all, and `sections.json`
  does not clear it.
* Seven positives across four songs is a small sample. It is enough to separate
  "at chance" from "not at chance"; it is not enough to rank two working
  methods, and no claim here should be read as finer than that.

Where the hits and misses are:

```
  Hideaway - Kiesza                        impact   62.41  nearest   62.44  (+0.03s)
  Titanium - David Guetta ft Sia           impact   74.66  nearest   75.23  (+0.58s)
  Titanium - David Guetta ft Sia           impact  151.26  nearest  151.42  (+0.16s)
  Titanium - David Guetta ft Sia           impact  212.01  nearest  212.38  (+0.37s)
  Armin - Revolution                       impact   57.83  nearest   44.76  (-13.07s)
  Armin - Revolution                       impact  153.96  nearest  111.23  (-42.73s)
  _test_song                               impact   28.40  nearest   14.82  (-13.58s)
```

The three Titanium hits are all `chorus → inst` or `chorus → outro`. The drop is
not a separate thing the model had to find; it **is** the section change, and the
label pair says what kind of change it is. The three misses are not near-misses,
they are different events entirely — on Armin and `_test_song` allin1 finds a
form that does not contain the marked drop at all.

## Measurement 2 — the stems it is given change the answer

The single most consequential finding, and it is not about accuracy.

`allin1` runs `demucs` itself unless it is handed stems, and `demucs` output is
not reproducible run to run. Feeding it the pipeline's own stems (`_seed_demix`
in [`model.py`](model.py)) was originally a memory workaround. It turns out to
be what makes the model reproducible at all:

* **Seeded with the pipeline's stems, allin1 is stable.** Three consecutive runs
  on each gold song produced byte-identical section sequences and every boundary
  in every run ([`out/stability.json`](out/stability.json)).
* **Unseeded, it is not, and the difference is not cosmetic.** This cache and the
  earlier survey's cache disagree on **14 of 21 songs**. Re-running Armin
  unseeded reproduced the survey's cache exactly, which identifies the cause.

What that changed:

| song | survey (allin1's own demucs) | this run (pipeline stems) |
| --- | --- | --- |
| Armin - Revolution | `intro`, `inst`, `intro` — degenerate | `intro verse inst verse chorus inst` |
| Chimera - Hana | `intro`, `inst` only — degenerate | 8 sections, 6 distinct labels |
| Hideaway - Kiesza | 6 sections | 8 sections, `outro` recovered |

**The survey's conclusion that allin1 degenerates on instrumental trance was an
artifact of the separation it was given, not a property of the model.** Two of
the three songs it named are fine when the stems are held fixed. Any future
model that consumes stems inherits this: the stems are part of the input, and an
experiment that lets a dependency generate its own is not reproducible.

## Measurement 3 — the frame-level outputs the segment list throws away

`allin1.analyze(..., include_activations=True)` returns four curves at 100 Hz,
not just the segment list: `beat`, `downbeat`, `segment`, and a **posterior over
all ten labels per frame**. The published segmentation is an argmax of the last
of these, quantised to an 8-bar phrase. Two useful things survive underneath it
([`activations.py`](activations.py), exported into the `frame_labels` block of
each proposal file):

* **Per-section confidence.** Normalised entropy of the posterior inside each
  committed section, 0 when the model is certain and 1 when it has no opinion.
  On Armin it averages **0.78** — the model names that song while being close to
  opinion-less about it. The segment list has no room to say so, and a name
  carrying that little conviction should not be read as one.
* **Shadow labels.** Sustained posterior mass on a label the committed
  segmentation never used *anywhere in the song*. On Armin, `break` appears in
  no published section, yet holds 24 % of the mass across 68.6–75.9 s and
  **30 % across 143.4–175.0 s**, peaking at 0.40 — a stretch published as
  `inst`, where the drum stem falls to 0.011–0.037 and the vocal to 0.003. It is
  a real breakdown the 8-bar argmax could not express.

On `_test_song`, whose published read is only `intro chorus`, the shadow labels
are `inst` and `outro`, and the `outro` runs cover four of the five hand-marked
outro hints.

This costs no extra model and no extra pass beyond the flag. It feeds the
**Character** lane through [`../clap/`](../clap/README.md), which is where the
"beyond the arrangement" work lives.

## Measurement 4 — labelling health across the corpus

The failure mode that matters is not a wrong boundary, it is a confident wrong
*name*. It is detectable without ground truth — count distinct labels, check the
dominant label's share of the song — so the exporter marks those songs rather
than guessing. Full table in [`out/score.txt`](out/score.txt).

Degenerate on **1 of 21**: `_test_song`, which is a 58 s excerpt with two
sections, so arguably correct. Every other song gets 3–6 distinct labels with no
label covering more than 68 % of the track. On a degenerate song the exporter
sets `function_status: "unknown"` on every row and the UI greys the lane out —
the boundary may still be usable where the name is not.

## Measurement 5 — its beat grid is either right or exactly a half-beat out

allin1 emits its own beats, downbeats and tempo. Compared with the essentia grid
the pipeline already ships (`out/score.txt`, third table):

* **16 of 21** agree to within 7 % of a beat period.
* **4 of 21** sit at 0.43–0.47 of a beat — a clean **half-beat phase offset**,
  the model on the offbeat, not wrong about the tempo.
* **1 of 21** (`Sash - Raindrops`) halves the tempo outright: 70 BPM and 178
  beats against essentia's 446.

So take the **structure** from allin1 and keep the **grid** from essentia. There
is no case here for replacing a beat tracker that already puts 7/7 human impacts
within 0.25 s of a beat.

## What is exported

`python -m experiments.allin1.run export` writes one file per song to
`data/analysis/<song>/reference/proposals/allin1.json` — a proposal, so it stays
out of `artifacts/`, out of the stable top-level contract, and out of
`reference/human/` (constitution §3.2). It carries every feature derivable from
the model's four outputs:

| key | what it is |
| --- | --- |
| `sections` | merged label runs — the song form. `name` numbers a returning label (`chorus 2`), `same_label_as` points at the first section with that label, plus bar span, 8-bar phrase count, `function_status` |
| `transitions` | one row per section boundary: the label `pair`, a `kind` (lift / release / shift), the bar, the signed offset to the nearest essentia beat, `on_downbeat`, and `matches_human_impact` |
| `phrases` | the model's own unmerged segment rows — its 8-bar phrase grid |
| `frame_labels` | per-section posterior entropy and the shadow labels of Measurement 3 (present once `run cache-activations` has been run) |
| `bar_grid` | downbeats, meter, median bar length |
| `tempo` | BPM, beat count, median beat period, period spread |
| `beat_agreement` | the Measurement 4 comparison, per song |
| `labelling` | the Measurement 3 honesty flag, with its reason |

`kind` is a reading convention derived from an intensity ordering of the Harmonix
vocabulary, **not** a measurement. In particular there is deliberately **no
`kind: "drop"`**: three of the seven gold impacts are `chorus → inst`, one is
`chorus → outro`, and four label pairs are not enough to justify a rule that
would then be applied to eighteen unlabelled songs. Deriving a drop from a label
pair is the right idea; the ground truth to fit it does not exist yet.

## Review it

Two lanes in the debugger (`docker compose up ui`, then load a song):

* **allin1 Transitions** — directly beneath **Human Hints** and **Drop
  Proposals**, expanded on load. Each block is one bar wide at the section
  change, labelled `✓ → inst` when it already matches a hand-placed drop impact
  and `? → inst` when it does not. Play the song and judge the `?` rows.
* **allin1 Sections** — directly beneath **Sections**, the incumbent it is
  scored against. Expand both to compare `chorus 2` against
  `010 Groove Plateau (0.78)` over the same span.

Both lanes come out of the registry when this experiment is promoted or
abandoned.

## What promotion would take, and what it would delete

Not proposed yet — under constitution §3.3 that is a decision to ask for, and
this is the material for the ask rather than the ask itself.

A promotion would add a phase-2 segmentation stage seeded from the existing
stems (~6 s/song) and **delete** `src/analyzer/stages/sections/` along with the
mood-adjective vocabulary, changing the projected `sections.json` and
`artifacts/section_segmentation/sections.json` (the reach test — those are files
the cue-authoring model actually reads). Promotion that only adds would be a
mistake here; the incumbent it replaces is the thing measured at chance.

Three things stand between here and that:

1. **The ground truth is the wrong shape.** Seven `drop impact` clicks placed by
   hand, a median 0.135 s off the nearest beat, cannot resolve ±0.5 s and cannot
   score a *named* segmentation at all — nothing in the repo says where a verse
   ends. Re-deriving the labels as bar-aligned section transitions would let
   every number above be replaced by a real one.
2. **Identity is still missing.** `same_label_as` is label repetition, not
   acoustic identity: it says "the third thing allin1 called a chorus", not
   "this is the same music as the first chorus". A light show needs the second
   to reuse a look. CLAP embeddings were tried and lost to 20 MFCC coefficients
   ([`../clap/`](../clap/README.md) Measurement 4); the survey's MERT clustering
   pooled inside these boundaries is the remaining candidate.
3. **Armin and `_test_song` are still missed by 13 s and more.** The form allin1
   finds on those tracks does not contain the marked drop. Whether that is the
   model or the label is exactly what item 1 would settle.

## Negative results worth not rediscovering

* **A boundary count is not a boundary quality.** The incumbent proposes 3.6
  boundaries/min and scores below an evenly spaced grid at the same budget.
  Always score against the do-nothing baseline; it is cheap and it is where the
  incumbent failed.
* **Letting a dependency generate its own inputs makes an experiment
  irreproducible**, and the symptom looks like a modelling result — "the model
  degenerates on trance" — rather than a plumbing bug. See Measurement 2.
* **allin1's beats are not a second opinion worth having.** Four songs land a
  clean half-beat off and one halves the tempo. Use it for structure only.
* **The merged section boundary is not the same object as the raw segment
  edge.** Merging equal-labelled neighbours is what turns an 8-bar phrase grid
  into song form; scoring the unmerged edges instead inflates the boundary count
  to 3.3/min for one extra hit at ±2.0 s.
