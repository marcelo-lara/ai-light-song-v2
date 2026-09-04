# Wave-2 review — every experiment measured against the module it would replace

*Written 2026-09-04, after the wave-2 batch. This section reads the entries
below against `src/` as it stands today and says, per module, whether to
**remove**, **replace**, **complement** or **keep**. It is advice, not a
decision: nothing here has been promoted, and §3.3 still applies.*

*Facts marked **(verified here)** were re-measured across all 21 analysed songs
while writing this; everything else is cited from the entry below it.*

## The one-line verdict

**Roughly 6,000 of the analyzer's ~14,600 lines produce inference that is either
measured at chance, measured at literally zero, or never projected to the
authoring model — and the two projected files that carry the most weight
(`sections.json`, `song_event_timeline.json`) are the two that measure worst.**
Meanwhile the three facts a cue author most needs — *which part is this*, *is
this part the earlier one returning*, *what does this passage feel like* — are
each either missing or provably wrong. Processing time is not the problem. The
problem is that the expensive half of the pipeline is spending it on claims
nobody reads and claims that are wrong.

## Module-by-module: what is measured, and what it costs

| `src/` module | lines | writes | projected? | measured | verdict |
| --- | --- | --- | --- | --- | --- |
| `stems.py` | 198 | `stems/` | no (feeds all) | trusted | **keep** |
| `timing.py` | 156 | `beats.json` | **yes (#4)** | beats 7/7 within 0.25 s; **downbeats 3/7** | **keep beats, replace downbeat phase** |
| `loudness.py` | 160 | `rms_loudness.json` | **yes (detail)** | trusted | **keep** |
| `fft_bands.py` | 138 | `essentia/fft_bands.json` | no | its whole-song percentile normalisation **won** the reactive-bands ablation 5/7 vs 2/7 @±0.25 s | **keep, vindicated** |
| `drums.py` | 253 | `symbolic_transcription/drum_events.json` | **yes (detail)** | trusted | **keep** |
| `genre.py` | 330 | `genre.json` | **yes** | honest confidences (`dance @ 0.27`) | **keep** |
| `harmonic.py` | 736 | `layer_a_harmonic.json`, `hpcp.json` | **no** | trusted DSP, but its only consumer is the segmenter that measures at chance | **keep as input — but decide project-or-stop** |
| `energy.py` | 302 | `layer_c_energy.json`, `energy_summary/` (4.0 MB/song) | **no** | never scored | **keep as input, stop publishing** |
| `sections/` (`segmenter`+`form`+`utils`) | 1,403 | `sections.json`, `section_segmentation/` | **yes (#1)** | **0/7 @±1.0 s**, 1/7 @±2.0 s; loses to an evenly spaced grid (2/7) and to a 20-line librosa baseline | **REPLACE** |
| `event_rules/` + `event_machine/` + `event_features/` | 2,447 | `event_inference/` (8.8 MB/song) | no | — | **REPLACE (with the stage below)** |
| `event_timeline` + `event_review` + `event_identifiers` + `review_queue` + `event_contracts` | 1,352 | `song_event_timeline.json` | **yes (#2)** | **0/7 @±0.25 s, 1/7 @±0.5 s**; 2,395 events over 21 songs | **REPLACE** |
| `event_ml.py` + `event_ml_train.py` + `event_ml_models.py` | 1,080 | `events.ml.json` | no | **0 events on 21 of 21 songs (verified here)** | **REMOVE** |
| `event_benchmark.py` | 175 | `validation/event_benchmark.json` | no | **`status: "skipped"` on 21 of 21 — `benchmark_annotations/` does not exist in the tree (verified here)** | **REMOVE** |
| `symbolic/` + `_basic_pitch*` + `_omnizart_runtime` | 1,341 | `layer_b_symbolic.json` (7.0 MB/song) | **no** | feeds only the templated `motif_recall` hints and the event features | **REMOVE (keep `drums.py`)** |
| `patterns.py` + `validation/patterns.py` | 603 | `pattern_mining/chord_patterns.json`, `layer_d` | **no** | never scored, never projected | **REMOVE or project** |
| `unified.py` + `validation/unified.py` | 351 | `music_feature_layers.json` | **no** | a re-packaging of files nothing reads | **REMOVE** |
| `hints.py` | 365 | `hints.json` | **yes (#3)** | 877 hints, 4 templated categories, **`user_hint_count: 0` on all 21 songs (verified here)** | **REBUILD** |
| `validation/` (rest) | ~1,700 | `validation/` | no | `form_score` `mode: "unlabelled"`, `labelled_boundary_count: 0` on 4/4; `drops_score` timed on 1 song | **cut to what has labels** |
| `ui_data.py`, `hint_alignment.py` | 364 | debugger input | UI | — | **keep** |

## 1. Remove — inference that returns nothing

These are not close calls. None of them needs another experiment to settle;
each is already measured at zero, or has no consumer at all.

1. **The ML event stack — 1,080 lines, 0 events.** `events.ml.json` contains an
   empty `events` array on **every one of the 21 analysed songs** (verified
   here). Three modules, a training script, a seeded model directory and a
   pipeline stage produce nothing at all. Delete outright.
2. **`event_benchmark.py` — skipped 21/21.** It scores against
   `benchmark_annotations/<song>.json`, a directory that **does not exist in the
   repository**. Every run writes `status: "skipped", reason: "No benchmark
   annotation file exists for this song."` This is a validation stage that has
   never validated anything.
3. **Half of `song_event_timeline.json` is beat-level arrangement noise.**
   2,395 events across 21 songs, **114 per song, median duration 0.488 s** — one
   beat. `layer_add` (655) and `layer_remove` (583) are **52 % of the file** and
   both are a per-beat energy delta with a fixed sentence attached. There are
   **46 distinct `summary` strings for 2,395 events**; the top three are
   *"Arrangement appears to gain material at this beat."* (×655),
   *"Arrangement appears to strip back at this beat."* (×583) and
   *"Breakdown candidates are merged across adjacent negative-delta beats."*
   (×258) — the last is an internal implementation note, and the input guide
   names that exact failure ("*'Impact hits remain single-beat candidates' is an
   internal note, not a cue hint*"; it appears 116 times). The concept pass sees
   `type`, the window and `intensity` for all 114 of them.
4. **Symbolic note transcription — 1,341 lines and 7.0 MB per song, for nothing
   projected.** `basic_pitch` and `omnizart` pitch transcription reaches the
   authoring model through exactly one route: the templated `motif_recall` hint
   (*"Repeated material returns here through phrase groups …"*, 244 of the 877
   hints, all the same sentence). Drum events — which *are* projected — come
   from `drums.py`, not from here.
5. **`unified.py` / `music_feature_layers.json`.** A merge of four layer files,
   none of which is on the MCP surface. The merge is invisible squared.
6. **`patterns.py`.** Chord-pattern mining is honest deterministic arithmetic
   and it reaches nobody. Either promote a compact form of it into a projected
   file or stop computing it; carrying it in between is the worst of both.
7. **Drop detection from raw features — `event_identifiers.py`.** It picks drops
   off bass-band transients directly. Constitution §5.2 says the opposite in as
   many words: *a drop is derived from a named section pair, not detected*. The
   result is **5 `drop` and 20 `fake_drop` events across the whole 21-song
   corpus** against 7 hand-marked impacts on four songs — it is not finding
   them.
8. **Validation stages with no labels.** `form_score.json` exists on 4 songs and
   reports `mode: "unlabelled"`, `labelled_boundary_count: 0` on all four;
   `drops_score.json` is in `presence` mode on 3 of 4 and `timed` on one. These
   files read as scores and contain no scoring. Keep the beat/chord validators,
   which do compare against real reference data; drop the rest until labels
   exist.

**Rough total: ~4,000 lines and ~20 MB of per-song artifact, none of which
changes a cue.**

## 2. Replace — where an experiment beats the module it was built against

### 2.1 `sections/` → `allin1` (gated on SongFormer)

The incumbent is the highest-priority projected file in the contract and it is
the worst-measured module in the tree.

| method | ±0.5 s | ±1.0 s | ±2.0 s | boundaries/min |
| --- | --- | --- | --- | --- |
| **allin1 section transitions** | **3/7** | **4/7** | 4/7 | **1.6** |
| shipped `sections.json` | 0/7 | 0/7 | 1/7 | 3.6 |
| evenly spaced grid, same budget | 0/7 | 2/7 | 3/7 | 3.6 |

allin1 also supplies what the incumbent structurally cannot: a *named*
functional label (`intro verse chorus bridge inst break outro`) instead of an
invented mood adjective, at **less than half** the boundary budget. Deletes
`src/analyzer/stages/sections/` (1,403 lines) and changes `sections.json` plus
`artifacts/section_segmentation/sections.json`.

**Do not promote before the SongFormer entry runs.** SongFormer reports HR.5F
0.703 against All-In-One's 0.596 on the same Harmonix vocabulary; promoting
allin1 first risks wiring the pipeline's whole structural read to the
second-best model. That run is cheap relative to the cost of getting it wrong.

### 2.2 `beats.json` downbeats → allin1's downbeat phase

Not a new experiment — it is the grid-consensus entry's own negative result read
forwards. Consensus fusion ties two trackers and loses to the third:

| downbeat phase | hits @ ±0.25 s |
| --- | --- |
| essentia (ships today) | 3/7 |
| beat-this | 3/7 |
| **allin1** | **4/7** |
| grid-consensus fusion | 3/7 |

If allin1 is promoted for structure it is already in the pipeline, so taking its
downbeat *phase* over essentia's costs nothing and wins the only comparison
that has been run. Keep essentia's beat *times* (7/7 within 0.25 s) — this is a
phase swap, not a grid swap. The honest caveat carries too: on `_test_song` all
four hypotheses agree at confidence 1.0 and still miss by 0.66 s, so a
`confidence` per downbeat and an `unknown` span belong in `beats.json`
regardless of which tracker wins.

### 2.3 The `event_*` stack → the gestures stage

| method | ±0.25 s | ±0.5 s | ±1.0 s | events/min |
| --- | --- | --- | --- | --- |
| gesture impact phase | 2/7 | 4/7 | 4/7 | 14.1 |
| incumbent `song_event_timeline` | 0/7 | 1/7 | 2/7 | 1.5 |
| RMS-derivative peak-picker (baseline) | 3/7 | 6/7 | 7/7 | 40.8 |

Gestures beat the 3,800-line incumbent by a wide margin **and lose to a one-line
peak-picker on recall**. The recall column is not what decides this: the
peak-picker emits no phases, no evidence and no claim that can be wrong, and
constitution §1.2 asks specifically for the approach/build/tension/impact/release
structure the gestures stage is the only measured method that produces. But the
entry's own honesty stands — **the per-primitive precision audit by ear was not
done**, and a phantom riser fires a cue that contradicts the music. That audit,
on 20–30 spans across four songs, is the cheapest high-value work in this whole
file and should happen before any promotion talk.

### 2.4 `hints.json` → merge the human hints, now

This one needs no model. The input guide asks for
`reference/human/human_hints.json` to be merged as `source: "human"`; four gold
songs have that file; **`user_hint_count` is 0 on all 21 songs (verified
here)**. The operator's own hand-marked, timed, lighting-specific hints — the
single highest-signal text in the repository — do not reach the authoring model
at all, while 877 generated sentences drawn from a pool of ~330 templates do.
Merging them is a small change to `hints.py` and it is the largest quality gain
per line in this review.

## 3. Complement — signals the pipeline has no equivalent of

### 3.1 Character blocks (stems + CLAP calm axis + allin1 shadow labels)

The pipeline has no texture layer. The ablation is what justifies it:

| rule | breath blocks | share of corpus claimed | finds the Armin `Breath` block |
| --- | --- | --- | --- |
| stems + CLAP calm | 28 | **41 %** | yes |
| stems alone | 81 | 73 % | yes |

CLAP contributes **exactly one axis** — calm ↔ intense — and is confidently
wrong about what is playing (drums present where the drum stem sits at 0.03).
Used that way it nearly halves the detector's false territory and covers 7 of
the 10 hand-marked non-drop hints.

**A suggestion that turns this from an addition into a replacement.** §3.3 warns
that promotion which only adds is usually a mistake, and the CLAP entry concedes
it deletes nothing. It does not have to: `section_character`'s 13-value
controlled vocabulary is currently *derived from the segmenter that measures at
chance*, and it is what `get_song_brief`'s `similar_sections` grouping runs on.
Replacing that vocabulary with measured character blocks — voice present, drums
out, calm; drums and bass out; full power — deletes a fabricated field instead
of adding a file.

### 3.2 Vocal phrase edges

| method | ±0.1 s | ±0.25 s | ±0.5 s | bounds/min |
| --- | --- | --- | --- | --- |
| vocal_phrases | **28/94** | **42/94** | **66/94** | 44.9 |
| shipped `sections.json` | 5/94 | 5/94 | 10/94 | 3.6 |
| mix-RMS threshold (baseline) | 25/94 | 37/94 | 51/94 | 61.2 |

A third of `_test_song`'s hand-marked boundaries are vocal-phrase edges, at
eleven times chance. Nothing in the pipeline emits them, and they are
sub-section by construction — `hint-010`/`hint-011` is split by a 0.63 s breath
*inside a single lyric line*. Lands in `song_event_timeline.json`, which is
already projected, so no contract change.

**Not settled**: the budget-matched ablation against mix-RMS was never run, and
the reactive-bands entry in this same file is the standing proof that omitting
one can invert a result. Run the ablation before the promotion conversation, not
during it.

### 3.3 Section identity — the most valuable missing fact

**Verified here: the `repetition_group` key is absent from all 290 sections of
all 21 projected `sections.json` files.** `sections/form.py` computes it,
`ui_data.py` copies it, it is `null` everywhere, and the key is dropped on
write. So nothing reaching the authoring model says that the chorus at 2:10 is
the chorus from 0:55 returning — which for a light show is close to the single
most valuable fact in the file, because the returning look is what makes a show
read as designed rather than reactive.

The bar is measured and unmet: **MFCC 20 at pair AUC 0.73**, CLAP 0.68. Note
that allin1 does *not* close this — `same_label_as` is label repetition ("both
are called chorus"), not "this is the same music". The pending identity entry is
the right shape (invariance-trained embeddings, cover-song objective), and its
own noise-floor clause is the important part: four songs is very few section
pairs, and the honest output may be a request for hand-marked "these two are the
same part" pairs rather than another model.
## 3.5 Addendum — `reference/moises/` is a bigger evaluation set than anything used so far

*Added after the operator clarified what these files are: `reference/moises/*.json`
is **Moises.ai inference**, not hand-labelling, and the curated rows are the ones
marked `confidence: "0.99"` — a **string**, which is why a numeric scan for a
confidence field finds nothing. Only `lyrics.json` carries the field at all;
`beats.json`, `chords.json` and `segments.json` have no confidence key, so
nothing in them is operator-curated. Scoring against them measures **agreement
with another vendor's model**, not correctness — but it is 5–200× more signal
than the 7 hand-clicked impacts every entry in this file is scored on.*

Curated (`0.99`) lyric words: `_test_song` 24/34 (71 %), `Titanium` 40/287
(14 %), `Armin` 32/96 (33 %), `Hideaway` 2/234 (1 %).

**One claim in this file is now false and should be read as retracted.** The
allin1 entry says *"nothing in the repo says where a verse ends"*.
`reference/moises/segments.json` does, on all four gold songs — **42 named
segments, 38 interior boundaries**, labelled `Intro / Verse / Chorus / Bridge /
Instrumental`. That is the named-segmentation ground truth the entry said was
missing, and re-scoring against it does not change the verdict — it sharpens it.

### Structure, re-scored against 38 Moises boundaries instead of 7 impacts

| method | recall @±1.0 s | **precision** | **F1** | bounds/min |
| --- | --- | --- | --- | --- |
| **allin1 phrase edges** | **0.84** | 0.76 | **0.80** | 3.4 |
| **allin1 sections** | 0.53 | **0.91** | 0.67 | 1.8 |
| shipped `sections.json` | 0.32 | 0.27 | 0.29 | 3.7 |
| evenly spaced grid, same budget | 0.24 | — | — | 3.7 |

The incumbent's F1 is **0.29 against allin1's 0.67–0.80** — a 2.3–2.8× gap on
38 boundaries, where the previous evidence was 0/7 vs 4/7 on 7. Note *precision*
in particular: **91 % of allin1's section boundaries are real boundaries**,
against 27 % of the incumbent's. Per song the incumbent is 0/11 on `Hideaway`
@±0.5 s where allin1 gets 5/11.

### Downbeats, re-scored against 385 Moises downbeats instead of 7 impacts

| method | F1 @±70 ms | songs it gets right |
| --- | --- | --- |
| essentia beat *times* (trusted, for contrast) | **0.59** (1.00 on 2 of 4; 0.98–0.99 at ±0.25 s on the others) | — |
| **allin1 downbeats** | **0.59** | 3 of 4 |
| essentia downbeats (**ships today**) | **0.16** | 1 of 4 |

This is a far stronger version of §2.2's 4/7-vs-3/7. The failures are **whole-beat
phase errors, not timing errors**: on `Titanium` essentia sits exactly **+1.00
beats** off Moises's bar phase and allin1 **+1.96 beats** — three independent
readings, three different phases, which is `Titanium`'s bar grid being genuinely
unresolved rather than one tracker being sloppy. `Hideaway` is different again:
essentia's *beats* are half a beat out (`+0.53`), so the problem there is the
beat grid, not the phase. Both cases are §7's *"say so rather than snapping"* —
`beats.json` needs a per-downbeat confidence and an `unknown` span.

### Chords — never scored on a real song, and they agree with Moises about half the time

| song | beats compared | exact (root+quality) | root only |
| --- | --- | --- | --- |
| `_test_song` | 125 | **1.00** | 1.00 |
| `Titanium` | 473 | 0.69 | 0.69 |
| `Armin - Revolution` | 369 | 0.51 | 0.71 |
| `Hideaway - Kiesza` | 466 | **0.38** | 0.40 |

Two models disagreeing on ~43 % of beats does not say which is wrong, and
`Hideaway`'s number is partly the half-beat grid error above corrupting the
alignment. But it is the first time `harmonic.py` has been measured on real
music, and it does not support treating our chord labels as settled.

**Why it was never measured: `validate-chords`, `validate-beats` and
`validate-sections` are `skipped` on 20 of 21 songs, including three of the four
gold songs that now have the files.** The Moises references for `Titanium`,
`Hideaway` and `Armin` landed **2026-09-02**; their `phase_1_report.json` is
from **2026-08-30**. Nobody has re-run the pipeline since the reference data
arrived. **A plain re-run of the corpus turns 1 validated song into 4, for
free** — that is the cheapest item anywhere in this review.

**One code comment is now wrong and should be corrected in the refinement.**
`phase_1_report.json`'s own notes say *"Chord validation treats reference chord
files as authoritative human-validated comparison inputs when present."* They
are not human-validated; they are Moises inference. A validator that calls its
comparison input authoritative when it is a second opinion is exactly the
overstatement §2 exists to prevent.

### So: is there a better model than Moises?

The operator's standing offer is to replace it. Per signal:

- **Segments — yes, probably.** allin1 already produces a *named* segmentation
  that agrees with Moises at F1 0.80 while adding an 8-bar phrase grid Moises
  has no equivalent of, and SongFormer claims better still. Moises's own
  segmentation is coarse on this repertoire — it labels 8 of 11 spans on `Armin`
  and 8 of 12 on `Hideaway` simply `Instrumental`.
- **Downbeats — yes.** allin1 at F1 0.59 vs essentia's 0.16.
- **Beats — no.** essentia is already at or above Moises everywhere except
  `Hideaway`, where both should be checked by ear before either is called wrong.
- **Chords — unknown, and worth one experiment.** Nothing in this file has ever
  tried a chord model; Moises is the only external opinion we have, and we agree
  with it on ~57 % of beats over the three real songs. Note the reach test first:
  **chords currently reach the authoring model in no file at all**, so a better
  chord model changes nothing about the show until `harmonic.py` is either
  projected or deleted. Decide that before spending a run on it.
- **Lyrics — yes, on text; no, on time.** ACE-Step beats the whisper baseline on
  `Titanium` (WER 0.23 vs 0.32), and Moises's own word offsets are unusable
  (`Armin` holds one word for 52.2 s). Only the `0.99` words are truth, and on
  `Hideaway` that is 2 words out of 234 — so a forced aligner is needed
  regardless of which transcriber wins.
- **Identity — nobody has it,** Moises included. Still the largest gap.

## 4. Archive — measured, negative, do not reopen

- **VocalParse** — hallucinated Mandarin on 3 of 4 gold songs (WER 1.00), melody
  head degenerate on 4/4. Model-capability limit, not a decoding knob.
- **Reactive bands** — the headline hypothesis came back inverted: at a matched
  ~29 accents/min the **incumbent's whole-song percentile normalisation wins
  5/7 vs 2/7** at ±0.25 s. The durable finding is methodological (two curves on
  different scales cannot share a threshold) and the practical one is that
  `fft_bands.py` is *validated*, not superseded.
- **Grid consensus** — ties two trackers, loses to allin1, phrase grid clearly
  worse (0/7 @±1.0 s vs allin1's 4/7). Two findings survive: kick placement
  carries almost no downbeat-phase information in four-on-the-floor repertoire
  (Titanium's histogram `[77, 76, 65, 86]`), and §2.2 above.

## 5. Suggested refinement order

Cheapest and most certain first; each step is independently useful.

0. **Re-run the corpus.** The Moises references for three of the four gold
   songs landed after the last full run, so `validate-beats`, `validate-chords`
   and `validate-sections` are `skipped` on 20 of 21 songs. One run turns 1
   validated song into 4 and costs nothing but time (§3.5).
1. **Delete what is measured at zero** — the ML event stack, `event_benchmark`,
   `unified`, symbolic note transcription, the label-less validation scores.
   No experiment gates this; it is ~4,000 lines and ~20 MB/song of artifact.
2. **Merge the human hints into `hints.json`** and cut the three templated hint
   categories to the ones that name a moment. Small change, immediate reach.
3. **Run SongFormer.** It gates the structural decision and nothing else can
   proceed cleanly around it.
4. **Do the gestures precision audit by ear** — 20–30 spans, four songs.
5. **Run the vocal-phrases budget-matched ablation** against mix-RMS.
6. Then the structural replacement lands as one change: named sections (allin1
   or SongFormer) + allin1's downbeat phase + character blocks replacing
   `section_character` + gesture phases replacing the event stack — deleting
   `sections/` and `event_*` in the same commit, per §3.3.
7. **Identity** last of the current queue, because a bad segmentation makes
   every embedding look bad and it should be measured on the winning one.

**Score everything from here on against the Moises boundaries as well as the
impacts** (§3.5). Seven hand-clicked impacts is a thin metric that several
entries in this file have already been unable to separate methods with; 38 named
segment boundaries, 385 downbeats and 1,433 chord-beats are sitting unused in
`reference/`, and they cost nothing to score against.

Music Flamingo stays where it is — run order 7, highest ceiling, and the only
candidate that could replace `hints.py`'s templated prose outright. Its
grounding harness (every timestamped claim cross-checked against the stems) is
the reusable part regardless of whether the model survives.

---

# Experiments to try

## CLAP

<https://github.com/LAION-AI/CLAP>

### Status

[DONE] — concluded. The character layer works and is reviewable in the debugger;
section identity failed. Awaiting the operator's archive-or-promote decision
(§3.3).

### Why? What for?

- it is used by Audio Vectors:
"""
AudioVector turns your tracks into 512-dimensional Microsoft CLAP audio embeddings — dense AI audio vectors for semantic similarity search, catalog matching, and recommendation pipelines.
""""

**What the experiment is actually for:** to see what CLAP can infer *beyond the
song arrangement sections*. The reference case is the operator's own ground
truth — `Armin - Revolution` `hint-006`, "Breath", 81.395–96.326,
*"Vocal - no intense section"*, lighting *"soft motion of moving heads. parcans
slow violet waves"*. An undoubtable voice block, worth its own look, and
invisible to any verse/chorus label. `_test_song` shows the same at finer grain:
`Spacer`, `Outro start`, three `Vocal outro` phrases, `Finale`.

### Experiment Plan

Built as [`../experiments/clap/`](../experiments/clap/README.md). Three sources
on a shared 10 Hz grid, each used for what it is good at:

- **stems** (`essentia/rms_loudness.json`) — what is physically playing. Already
  trusted, exact, free.
- **CLAP** — contrastive probe *pairs* (never single sentences; the survey
  established absolute readings are unusable), giving the perceptual axes the
  stems cannot: calm ↔ intense, sparse ↔ dense.
- **allin1's frame-level posterior** — `include_activations=True` returns beat,
  downbeat, segment and a per-frame posterior over all ten labels at 100 Hz.
  The published segment list is an argmax of that, quantised to 8 bars, and
  discards the rest.

Four block kinds, each taken from the operator's own hints and each mapping to a
different look: **breath** (voice present, drums out, calm), **void** (drums and
bass out, no voice), **vocal lead**, **full power**. Thresholds are relative to
each song's own levels, so nothing transfers between tracks. Exported to
`reference/proposals/character.json` and rendered as the **Character** lane.

### Results evidence

Full tables in [`../experiments/clap/out/character.txt`](../experiments/clap/out/character.txt)
and [`../experiments/clap/out/score.txt`](../experiments/clap/out/score.txt).

**It finds the block.** `char-004 breath 83.50–95.00` against the hand-marked
81.40–96.33 — inside the span, covering 11.5 s of 14.9 s, edges inset by the
smoothing and CLAP window. 7 of the 10 hand-marked non-drop hints are covered by
a character block.

**The ablation is what justifies CLAP:**

| rule | breath blocks | breath seconds | share of corpus claimed | Armin block found |
| --- | --- | --- | --- | --- |
| stems + CLAP calm | **28** | **241 s** | **41 %** | yes |
| stems alone | 81 | 973 s | 73 % | yes |

Both find it; only the first is specific. Without the calm term `breath`
degenerates into "any voice with the drums down".

**Where CLAP is right and wrong.** Its `calm` axis tracks the operator's own
intensity judgement — positive on `Breath` +1.65, `Outro start` +1.80, `Spacer`
+1.26; strongly negative on `prepare for end` −2.54 and `Finale` −2.35, the two
hints whose lighting note is "max intensity". Its `vocal` axis is weak where the
vocal stem is unambiguous, and its `drums`/`bass` axes are simply wrong — it
reports drums present through the Armin block where the drum stem sits at 0.03.

**allin1 beyond the arrangement.** On Armin, `break` appears in no published
section yet holds 30 % of the frame posterior across 143.4–175.0 s, exactly
where the drum stem falls to 0.011 — a breakdown the 8-bar argmax could not
express. Per-section posterior entropy averages 0.78 on that song: it names the
form while being nearly opinion-less about it.

**Section identity failed** (measured before the redirection, kept for the
baseline it establishes): mean pair AUC — MFCC 20 **0.73**, CLAP raw 0.68,
chroma 0.62, CLAP centred 0.61, duration control 0.59, time control 0.46. Twenty
MFCC coefficients beat the 512-d embedding. CLAP scores 0.83 at telling a
section from *itself* and 0.68 at matching two occurrences of the same part, so
identity needs a representation trained for invariance between occurrences. The
lane built for it was removed (§3.2).

### Conclusion

CLAP is worth keeping for exactly one thing: **a perceptual intensity axis**. It
cannot say what is playing — the stems do that better and for free — and it
cannot recognise a returning part. It can say whether a passage feels calm or
intense, which is the axis the operator's hints are actually written in, and
combined with the stems it nearly halves a texture detector's false territory.

The unexpected result is on the allin1 side: its frame-level posterior finds
breakdowns and outros its own published segmentation cannot name, at no extra
model cost.

A promotion would add a **character layer** to the pipeline — stem-derived
presence plus one CLAP axis plus allin1 shadow labels — and would need a new
projected file, since no file in
[`reference/analysis-input-guide.md`](reference/analysis-input-guide.md) carries
texture today. It deletes nothing, which §3.3 warns is usually a mistake; the
honest counter is that the pipeline has no character layer at all to replace.
Before that: the ground truth is 10 hand-marked blocks, 9 of them in a 58 s
synthetic excerpt. More marked blocks across real tracks would settle the
thresholds that are currently set by hand.

---

## All-In-One (`allin1`)

<https://github.com/mir-aidj/all-in-one>

### Status

[DONE] — concluded, awaiting the operator's archive-or-promote decision (§3.3).

### Why? What for?

Named song form. The shipped segmentation labels sections with invented mood
adjectives ("Momentum Lift", "Vocal Spotlight"), so nothing in the artifact says
*which part of the song* a section is, or that a returning chorus is the same
part as the first one — and its boundaries are measured at chance. `allin1` is
the one model in the 2026-09 survey that outputs *named* functional structure
(Harmonix vocabulary: `intro verse chorus bridge inst solo break outro`) in a
single multi-task model trained on pop/EDM, the repertoire this project targets.

The ask: extract everything it produces — segments included — and put it on the
timeline so it can be validated against the song by ear.

### Experiment Plan

Built as [`experiments/allin1/`](../experiments/allin1/README.md).

- `model.py` runs the model in the existing `ai-light-song-v2-allin1:dev`
  sandbox and caches its raw output per song; the cache is committed so every
  number is reproducible without a GPU. The model is seeded with the pipeline's
  own demucs stems rather than letting it separate for itself.
- `features.py` derives everything obtainable from its four outputs: merged
  **sections** (song form, with `chorus 2` numbering and `same_label_as`), the
  **transitions** between them (label pair, bar, offset to the essentia beat,
  `on_downbeat`), the raw 8-bar **phrase** grid, the **bar grid**, **tempo**, a
  **beat-grid comparison** against essentia, and a **degeneracy check** that
  marks a song `unknown` rather than emitting a confident wrong name.
- `export.py` writes one proposal per song to
  `data/analysis/<song>/reference/proposals/allin1.json` (§3.2 — never
  `artifacts/`, never `reference/human/`).
- `score.py` measures against the incumbent `sections.json` **and** against an
  evenly spaced grid at the same boundary budget.
- Two debugger lanes: **allin1 Transitions** beneath Human Hints and Drop
  Proposals, **allin1 Sections** beneath Sections.

### Results evidence

Gold set: 4 songs, 7 hand-placed `drop impact` marks. Full tables in
[`experiments/allin1/out/score.txt`](../experiments/allin1/out/score.txt).

| method | ±0.5 s | ±1.0 s | ±2.0 s | boundaries/min |
| --- | --- | --- | --- | --- |
| **allin1 section transitions** | **3/7** | **4/7** | 4/7 | **1.6** |
| allin1 phrase edges (unmerged) | 3/7 | 4/7 | 6/7 | 3.3 |
| shipped `sections.json` (incumbent) | 0/7 | 0/7 | 1/7 | 3.6 |
| evenly spaced grid, same budget (baseline) | 0/7 | 2/7 | 3/7 | 3.6 |

- All three Titanium hits are `chorus → inst` / `chorus → outro`: the drop **is**
  the section change, and the label pair says what kind of change it is.
- The incumbent does not beat evenly spaced guesses.
- **Reproducibility:** `allin1` runs `demucs` itself unless handed stems, and
  demucs is not reproducible. Seeded with the pipeline's stems it is stable —
  3/3 identical runs on every gold song. Unseeded it disagrees with itself on
  **14 of 21** songs, and that, not the model, is what produced the survey's
  "degenerates on instrumental trance" finding: Armin recovers a full
  `intro verse inst verse chorus inst` read and Chimera goes from 2 distinct
  labels to 6.
- **Labelling health:** degenerate on 1 of 21 (`_test_song`, a 58 s excerpt);
  every other song gets 3–6 distinct labels.
- **Its beat grid is not usable:** 16 of 21 agree with essentia to within 7 % of
  a beat, 4 sit a clean half-beat out of phase, and `Sash - Raindrops` halves the
  tempo. Take the structure, keep essentia's grid.

### Conclusion

`allin1` supplies the named structure the pipeline has no equivalent of, and does
it with **less than half** the incumbent's boundary budget — against an incumbent
that loses to evenly spaced guesses. Adopting it would mean deleting
`src/analyzer/stages/sections/` and changing the projected `sections.json`.

Three things are unresolved and none of them are settled by more modelling:
the ground truth is the wrong shape (7 hand-clicked impacts cannot score a
*named* segmentation — nothing in the repo says where a verse ends); section
**identity** is still missing (`same_label_as` is label repetition, not "the same
music"); and Armin and `_test_song` are still missed by 13 s and more, which the
first item would tell us how to read. No `kind: "drop"` is emitted: four label
pairs across the gold set cannot justify a rule applied to eighteen unlabelled
songs.



## VocalParse — singing voice transcription (lyrics + melody)

<https://huggingface.co/pymaster/VocalParse>

### Status

[DONE] — concluded, **negative**. Ran on CPU (this box's 4 GB GPU can't hold the
model) over the four gold songs, which now all carry Moises word-level lyric
ground truth. VocalParse hallucinates Mandarin on real non-Mandarin vocals and
its melody head collapses; it is not usable for this corpus. Awaiting the
operator's archive-or-promote decision (§3.3) — recommendation: **archive**.

### Why? What for?

No lyric ever reaches the authoring model. A sung line is a cue: the vocal
entry after an instrumental stretch is a look change, the title hook is usually
the biggest moment in the song, an a-cappella line wants a spotlight, and the
last word before a drop is the count-in. The operator's own hints already carry
this — `_test_song` has three separate `Vocal outro` phrases and a `Finale`,
`Armin - Revolution` has the "Breath" vocal block — but nothing in any artifact
says *what* is being sung or *when*, to the word.

The goal is **the lyric line with a precise start and end**, and ideally each
word's onset, so a reasoning model can hang a cue on "the hook lands here".
VocalParse is one of two singing-transcription models under test (the other is
[ACE-Step Transcriber](#ace-step-transcriber--multilingual-singing-transcription-with-structure)).
Its distinguishing output is the **vocal melody** — MIDI pitch and note value
per syllable — which is a second signal the pipeline has no equivalent of: a
rising vocal line into a chorus is a build a model could light.

### Experiment Plan

Built as [`../experiments/vocalparse/`](../experiments/vocalparse/README.md).
VocalParse is a Qwen3-ASR-1.7B fine-tune; it takes 16 kHz mono and emits an
interleaved token stream — `感 <P_68> <NOTE_4> 受 <P_60> … <BPM_89>` — lyric
tokens spliced with pitch (`<P_#>`, MIDI), note value (`<NOTE_#>`, log2) and one
global tempo. It predicts **no per-token timestamp**, and it is trained
"primarily on Mandarin Chinese singing" — this corpus is almost entirely
English and European, so a poor lyric result is a plausible and reportable
outcome.

- **Run it on the vocal stem the pipeline already produces**
  (`artifacts/stems/vocals.wav`), not the mix — the model expects isolated
  voice and the stems are trusted. Resample to 16 kHz mono, cache the raw
  string per song, parse to `{lyrics, syllables:[{text, midi, note_value}],
  bpm}`.
- **Timing comes from alignment, not from VocalParse.** Following LyricWhiz
  (2306.17103), Whisper is the "ear": run `whisper-large-v3` with
  `word_timestamps=True` on the same vocal stem to get word onsets in seconds.
  VocalParse's syllable sequence is aligned onto that word timeline by order.
  When VocalParse's text and Whisper's text disagree beyond a threshold
  (different language, garbage output), emit `alignment: "unavailable"` and
  place the whole transcription as a single span — **never fabricate per-word
  times** (constitution §2).
- **Derive note durations** as `note_value · 60 / bpm` for the melody signal,
  anchored to the aligned syllable onsets.
- Export the `vocalparse` source into
  `reference/proposals/vocal_transcription.json` (shared with the other
  experiment, keyed by `model`), rendered as the **Vocal Transcription** lane
  directly before **allin1 Sections**.

### Results evidence

Run on CPU in the `ai-light-song-v2-vocalparse:dev` sandbox (torch 2.4.1+cpu),
`max_new_tokens=768`, greedy. Scored against `reference/moises/lyrics.json`,
which now exists for all four gold songs (the operator added it mid-experiment).
Raw output in [`../experiments/vocalparse/out/score.txt`](../experiments/vocalparse/out/score.txt)
and the per-song caches.

**Lyric WER — VocalParse vs the whisper-large-v3 baseline (both on the vocal stem):**

| song | VocalParse WER | whisper baseline WER | whisper word-onset MAE |
| --- | --- | --- | --- |
| `_test_song` (synthetic, English) | 0.12 | **0.04** | 0.59 s |
| `Titanium` (English pop) | 1.00 | **0.32** | 0.41 s |
| `Hideaway` (English house) | 1.00 | 0.97 | 27 s (hallucinated) |
| `Armin - Revolution` (trance, sparse vocal) | 1.00 | 0.99 | 71 s (hallucinated) |

(Whisper baseline: `float32`, VAD off, `condition_on_previous_text=False` —
the settings arrived at for the ACE-Step experiment; the shared baseline cache
lives at `experiments/.whisper_baseline_cache/`.)

**What VocalParse actually produced:**

- `_test_song` — its `<asr_text>` chain-of-thought step gave
  *"This is a test song welcome to dark blue studio light show light show light
  show welcome to dark blue studio"* — near-perfect, and the only case where it
  beat the (CPU-degraded) baseline.
- `Titanium` — transcribed as **Chinese**: *"有啥的好我爱听你温柔的叙述…"* then
  an infinite loop of *"嗯许多话阮不想说"*. Pure hallucination.
- `Hideaway` — *"啊啊啊啊…"* (just "ah") to the token limit.
- `Armin` — *"啊啊啊…"*, language reported as `Other HEME`.

**The melody head never worked.** On every song the interleaved
`<P_#> <NOTE_#>` span collapsed to a run of `<P_0>` (pitch 0) followed by junk
tokens (`rawidłow`, `-wsj`, `CUS`). `melody_status` is `degenerate` or `empty`
on 4/4. No BPM token was ever emitted. This is consistent with the model card's
"primarily trained on Mandarin Chinese singing", and CPU-only inference
(float32, no flash-attn) likely makes the collapse worse — but the Mandarin
hallucination on the lyric side is a model-capability limit, not a decoding
knob.

**Baseline caveat.** The whisper baseline runs on CPU (CTranslate2 4.x needs
CUDA 12, which this box's CUDA-11.8 base image lacks). At `float32` with the VAD
off it is strong on the two prominent-vocal songs (WER 0.04 and 0.32) but
hallucinates YouTube-caption text on the two sparse-vocal songs. The VocalParse
verdict does not depend on it — VocalParse scored 1.00 on every real song.

### Conclusion

**Negative. VocalParse is not usable on this corpus.** Three of the four gold
songs came back as hallucinated Mandarin; the one success is a synthetic test
track. The melody signal — the one thing VocalParse offers that the pipeline
lacks — collapsed on every song. Nothing here reaches the reach test, so
`lyrics.json` is not proposed. Recommendation: **archive**. If singing-voice
melody is wanted later, it needs a model trained on Western pop, run on a GPU.

The reusable artifacts: the `whisper-large-v3`-on-the-vocal-stem baseline (worth
re-running on a GPU box — it is the real lyric-timing candidate), the
`reference/proposals/vocal_transcription.json` schema, and the **Vocal
Transcription** debugger lane, all shared with the ACE-Step experiment.


## ACE-Step Transcriber — multilingual singing transcription with structure

<https://huggingface.co/ACE-Step/acestep-transcriber>

### Status

**PROBED — strongly positive, not yet a full run.** Transcribed `_test_song`
and `Titanium - David Guetta ft Sia` on CPU (the thinker is 8.9 B params;
`Qwen2_5OmniThinkerForConditionalGeneration`, bf16, ~18 GB mmap'd, no GPU on
this box). Both came back with near-correct lyrics **and** a correct named song
structure. The one gap is timing — the model emits ordered lines and `[tags]`
with no seconds. Full corpus run and the timing solution are the open work;
`### Results evidence` below is the two-song probe.

### Why? What for?

Same goal as [VocalParse](#vocalparse--singing-voice-transcription-lyrics--melody):
put the sung lyric line, with precise timing, in front of the authoring model,
because a sung line is a cue. ACE-Step Transcriber is the stronger candidate for
*this* corpus — it is a Qwen2.5-Omni-7B fine-tune (11B params) built by the
ACE-Step team as their own training-data annotator, covers 50+ languages
including the European ones this corpus is full of, and it does two jobs the
pipeline needs at once: transcribe the lyrics **and** tag the song structure
(`[Intro]`, `[Verse 1]`, `[Chorus]`, `[Bridge]`, `[Outro]`), optionally naming
the instruments in each section.

That structure output is directly comparable to the incumbent `sections.json`
and to the `allin1` experiment — a third independent read of the song's form,
this one derived from what the voice is doing.

### Experiment Plan

Built as [`../experiments/acestep_transcriber/`](../experiments/acestep_transcriber/README.md).

- Load via `transformers` (`Qwen2.5-Omni` class); prompt
  `"Transcribe this audio in detail"`; parse the structured output —
  `# Languages` then `# Lyrics` with `[Section]` tags and lyric lines — into
  `{language, sections:[tag], lines:[text]}`.
- Feed it the **mix**, not the stem: unlike VocalParse it is trained on full
  songs and uses the backing track for the structure tags.
- **Timing:** check whether the chat template exposes a timestamped decode
  (ACE-Step 1.5 generates LRC via a separate alignment stage — the transcriber
  itself may not emit times). If it does not, align lyric lines to a
  `whisper-large-v3` word timeline on the vocal stem, exactly as the VocalParse
  experiment does, and derive `[Section]` spans from the lines they contain.
- Export the `acestep` source into the shared
  `reference/proposals/vocal_transcription.json`; the section tags also render
  in the **Vocal Transcription** lane so its form read can be auditioned
  against **Sections** and **allin1 Sections** next to it.

### Results evidence

Two-song CPU probe in the `ai-light-song-v2-acestep:dev` sandbox
(transformers 4.57.1, torch 2.4.1+cpu, `Qwen2_5OmniThinkerForConditionalGeneration`
bf16, thinker only — the talker and token2wav vocoder are not loaded). Prompt
`"Transcribe this audio in detail"` on the **mix**. `_test_song` at 320 new
tokens (~13 min), `Titanium` at 1024 (~40 min). Raw output in
`experiments/acestep_transcriber/cache/*.acestep.json`.

**`_test_song`** (synthetic, 58 s):

```
[Intro] [Atmospheric synth pads and arpeggio]
[Verse 1]   This is a test song / Welcome to Dark Blue Studio
[Build-up]  Light show! / Light show!
[Drop 1] [Instrumental]
[Chorus]    Light show! / Light show! / Welcome to Dark Blue Studio
[Outro] [Synth pads fade out]
```

Moises truth: *"This is a test song / Welcome to the dark blue studio / Light
show, light show / Light show / Light show, welcome to dark blue studio"* — one
dropped "the", otherwise exact.

**`Titanium`** (real English pop — the song VocalParse turned into looping
Mandarin):

- Structure: `Intro → Verse 1 → Pre-Chorus → Chorus → Instrumental Break →
  Verse 2 → Pre-Chorus → Chorus → Instrumental Break → Bridge → Chorus →
  Outro`. This is the correct song form, with scene tags ("Clean electric
  guitar arpeggio", "Synth lead melody over driving beat", "Music fades out")
  and backing-vocal parentheticals "(I am titanium)".
- Chorus *"You shoot me down, but I'm on fire / I am titanium"* — exact.
  Pre-chorus *"I'm bulletproof, nothing to lose / Fire away, fire away /
  Ricochet, you take your aim"* — exact. Verse 1 near-exact (one garbled line:
  "how are your bullets weak?" → "how are I? But that's me, go slow"). Bridge,
  Verse 2 mostly right.

**Lyric WER vs `reference/moises/lyrics.json`** (`run score`):

| song | ACE-Step WER | whisper baseline WER |
| --- | --- | --- |
| `_test_song` | 0.04 | 0.04 |
| `Titanium` | **0.23** | 0.32 |

On the synthetic track both are near-perfect; on `Titanium` ACE-Step wins on WER
*and* delivers the structure the baseline cannot. The whisper baseline
(`float32`, VAD off, `condition_on_previous_text=False`) is strong on these two
but **hallucinated YouTube-caption junk** on the two sparse-vocal gold songs —
`Hideaway` came back as French *"Sous-titrage Société Radio-Canada"*, `Armin` as
Japanese *"ご視聴ありがとうございました"*. A whisper baseline on the vocal stem
needs a stem-RMS vocal-activity gate (the LyricWhiz "PANNs filtering" idea) to
be trustworthy on quiet passages.

**Timing is the open problem.** The transcriber emits no seconds — ordered
lines and `[tags]` only (ACE-Step 1.5's LRC comes from a separate alignment
stage that is not in this checkpoint). `align.py` currently anchors the lines to
a `whisper-large-v3` word timeline on the vocal stem, but that baseline is weak
on CPU (`int8`/`float32`, CUDA-12 CTranslate2 unavailable on the CUDA-11.8
base), so on `_test_song` only 2 of 7 lines matched and the section spans fell
back to even spacing (`alignment: "unavailable"`, every span flagged `approx`).
A real timing solution is **forced alignment of ACE-Step's own (good) transcript
to the vocal stem** — not yet built, and now scoped as
[Vocal phrase blocks](#vocal-phrase-blocks--the-boundaries-the-operator-actually-marks),
run order 1 of this wave.

**Structure vs the incumbent and allin1:** blocked by the timing problem. With
the spans falling back to even spacing, ACE-Step's `[Section]` boundaries score
0/1 and 0/3 against the hand-marked drop impacts (allin1 gets 0/1 and 3/3 on the
same two songs). That 0/3 measures the broken alignment, not the structure —
the *sequence* of tags on `Titanium` (Intro/Verse/Pre-Chorus/Chorus/…) is
correct. The comparison only becomes real once the lines carry true onsets.

### Conclusion

**Positive on the two things that are hard — lyrics and named structure — and
open on timing.** ACE-Step Transcriber transcribes this corpus's English pop
with low WER and produces a correct verse/pre-chorus/chorus/bridge/instrumental
form with descriptive scene tags, in one pass, on the mix. It is the first thing
tried here that delivers *named* structure and lyrics together, and it succeeds
exactly where VocalParse fails.

It is **not ready to promote**: (1) timing is unsolved — the lines need real
onsets, which means adding a forced-aligner; (2) only two songs are transcribed,
both English — the 50-language claim is untested here; (3) an 8.9 B model with
no GPU path on the current box is a heavy production dependency. Next steps, in
order: a forced-aligner against ACE-Step's transcript; the full 21-song run
(needs a GPU or an overnight CPU batch); then score its structure against
`allin1` and the incumbent on one axis. If it clears those, promotion adds a
top-level `lyrics.json` (§9 contract change + MCP handoff) and its structure
feeds section naming rather than shipping as its own file.


## Vocal phrase blocks — the boundaries the operator actually marks

<https://github.com/m-bain/whisperX>

### Status

**[DONE] — Part A concluded, Part B not built.** The detector finds the
operator's vocal-phrase edges 5–6× better than the shipped `sections.json`, but
does not clearly beat a naive mix-RMS threshold once its firing rate is accounted
for, and the two were never compared at a matched budget. Forced alignment
(Part B) needs its own sandbox image and was not attempted. Awaiting the
operator's archive-or-promote decision (§3.3).

### Why? What for?

The operator's hand-marked hints are the only statement in this repository of
what a cue actually is, and **a large share of them are vocal-phrase edges, not
arrangement edges**. Auditing every hint boundary in the gold set against the
onset and offset of every sung line in `reference/moises/lyrics.json`:

| song | hint boundaries within ±0.10 s of a vocal edge | vs. chance |
| --- | --- | --- |
| `_test_song` | **10 / 30 (33 %)** | 3 % |
| `Titanium - David Guetta ft Sia` | 4 / 30 (13 %) | 6 % |
| `Armin - Revolution` | 1 / 24 (4 %) | 2 % |
| `Hideaway - Kiesza` | 0 / 10 (0 %) | 3 % |

Chance is the fraction of the song covered by a ±0.10 s window around each
vocal edge, so on `_test_song` the operator marks vocal edges at **eleven times**
the rate a boundary placed at random would.

The individual matches say what kind of fact this is. On `_test_song`:

| hint | operator's boundary | vocal edge | Δ |
| --- | --- | --- | --- |
| `hint-006` "Vocal outro phrase 1.1" | 43.339 → 44.356 | line 4 on/off 43.36 → 44.39 | +0.021 / +0.034 |
| `hint-009` "Synth Pad", *ambient melody* | 44.455 → 47.045 | the **gap** between lines 4 and 5 | −0.065 / +0.045 |
| `hint-010` "Vocal outro 2" | 47.091 → 50.03 | line 5 onset 47.09 | −0.001 |
| `hint-011` "Vocal Outro 3" | 50.076 → 54.576 | the 0.63 s breath **inside** line 5 (49.91 → 50.54) | — |
| `hint-012` "prepare for end" | 54.606 | line 5 offset 54.68 | +0.074 |

The whole outro — four consecutive looks with four distinct fixture behaviours —
is *exactly* the vocal-activity timeline. `hint-009` is an instrumental block
defined by nothing but the absence of voice; the `hint-010`/`hint-011` split is
a breath inside a single lyric line, invisible to any section model. The same
shape appears on `Titanium`, where six drop-phase boundaries sit on the last
word of a sung line (`"You shoot me down, but I'm a bomb"` at 71.41 for the
tension entry, `"I am titanium"` at 151.77 for the impact→release flip).

Nothing in the pipeline emits this. `sections.json` cannot: a vocal phrase is
sub-section, and the boundary that matters is a breath. The CLAP experiment
found the character axis but not the edge — its `vocal` axis is explicitly
*"weak where the vocal stem is unambiguous"*.

**Ground-truth caveat, and it is the reason this entry is scoped the way it is.**
Only `_test_song`'s word timings are genuinely word-level. On the other three,
Moises stretches a line's last word across the following instrumental — `Armin`
holds *"calling"* from 48.27 to 100.45 (52.2 s), `Hideaway` has a 29.3 s word,
`Titanium` a 7.1 s one; between 5 % and 9 % of words per song run over 1.5 s and
account for 50–88 s of "sung" time each. So **line onsets are usable corpus-wide,
line offsets are usable on `_test_song` only** — which is precisely constitution
§3.5's "use `_test_song` alone" case, and precisely why the second half of this
entry is a forced aligner.

### Experiment Plan

Build as `experiments/vocal_phrases/`. Two halves, measured separately.

**A — the detector (no model, no image).**

- Read `artifacts/stems/vocals.wav` and `artifacts/essentia/rms_loudness.json`;
  compute a vocal-activity envelope with hysteresis (separate on/off thresholds,
  relative to the stem's own running level, not a whole-song percentile — the
  same normalisation argument as the reactive-bands entry).
- Emit `vocal_phrase` and `instrumental_gap` blocks, `{start, end, confidence}`,
  with a **breath split**: a within-phrase silence longer than a swept threshold
  (0.3–1.0 s) becomes a boundary, because `hint-010`/`hint-011` is a 0.63 s one.
- Emit a `sustained_note` marker where a single vocal note holds past a swept
  duration — `_test_song` holds *"show,"* for 2.78 s straight through the drop
  build, and a held vocal over a build is a look in its own right.
- Snap nothing to the bar grid (`CLAUDE.md`: downbeats are not trusted); report
  the physical onset per §7.

**B — real onsets for the transcript (whisperX / wav2vec2 forced alignment).**

- Force-align ACE-Step Transcriber's transcript — measured at WER 0.04 and 0.23,
  the best text available — to the vocal stem. This is the "not yet built" step
  the ACE-Step entry's conclusion names as next, and it also repairs the lumped
  Moises offsets so the other three gold songs become usable phrase truth.
- Compare the aligner's word times to Moises on `_test_song`, where Moises is
  now trustworthy, before trusting it anywhere else.

**Measurement — fixed before the run (§3).**

1. **Boundary hit-rate against the human hints** at ±0.10 / ±0.25 / ±0.50 s,
   always reported with **boundaries per minute** — the same budget-aware framing
   the allin1 entry uses, since a detector that fires constantly hits everything.
2. **Incumbent:** the shipped `sections.json` boundaries, scored identically.
   **Cheap baseline:** a fixed threshold on mix RMS with no stem and no
   hysteresis.
3. **Phrase-edge accuracy against `_test_song`'s lyrics** — MAE of detected
   phrase on/off against line on/off, the reason the improved file matters.
4. **Aligner check:** word-onset MAE vs Moises on `_test_song`; then the count of
   >1.5 s "words" the aligner removes on the other three.

Export `data/analysis/<song>/reference/proposals/vocal_phrases.json`; add a
**Vocal Phrases** lane under Human Hints, beside the existing **Moises Lyrics**
lane so a proposal, the transcript and the hand-marked truth stack vertically
(§3.2).

**Reach test (§1.3).** If promoted, `vocal_phrase` / `instrumental_gap` /
`sustained_note` become events in `song_event_timeline.json`, which is already
projected. Nothing new joins the top-level contract, and the reference lyrics
themselves stay validation-only (§2) — the detector reads the stem, never
`reference/`.

### Results evidence

Built as [`experiments/vocal_phrases/`](../experiments/vocal_phrases/README.md),
**Part A only**. Full tables in
[`out/score.txt`](../experiments/vocal_phrases/out/score.txt). Gold set, 94 hint
boundaries.

| method | ±0.1 s | ±0.25 s | ±0.5 s | bounds/min |
| --- | --- | --- | --- | --- |
| **vocal_phrases** | **28/94** | **42/94** | **66/94** | 44.9 |
| shipped `sections.json` (incumbent) | 5/94 | 5/94 | 10/94 | 3.6 |
| mix-RMS threshold (cheap baseline) | 25/94 | 37/94 | 51/94 | 61.2 |

**It beats the incumbent and does not clearly beat the baseline.** The mix-RMS
threshold fires 61/min against the detector's 45, and at that inflated budget it
matches or beats the detector on the two songs where it fires roughly twice as
often — `_test_song` (12/16/23 at 47/min vs 11/14/20 at 21/min) and `Titanium`
(10/18/21 at 85/min vs 7/14/24 at 45/min). Where the stem gate earns its keep is
the dense mixes: `Hideaway` **8/10** at ±0.5 s against **0/10** for both the
baseline and the incumbent, and `Armin` 8/24 at ±0.1 s against the baseline's
3/24. **No budget-matched ablation was run**, and the sibling reactive-bands
entry below is the standing evidence that omitting one can invert a result.

**breath_s sweep** (`_test_song`, the only song with trustworthy word-level
offsets): onset MAE is flat at **0.022 s** across 0.3–1.0 s — the detector finds
where a phrase starts regardless of the breath setting. Offset MAE degrades
0.145 → 0.164 s as looser thresholds merge trailing reverb into the phrase. The
shipped 0.5 s is a middle point, not a measured winner.

**`sustained_note` came back empty on `_test_song`** — the one song whose audit
names a 2.78 s note held through the drop build. Root cause confirmed by
inspection: the held note's own amplitude decay dips below the hysteresis OFF
threshold mid-note and splits the phrase, so neither half reaches the 1.5 s
minimum, and the sustain scan only looks within a phrase. Bridging on pitch
continuity would fix it — a design gap, not a tuning one.

**Part B — forced alignment — was not built.** `transformers` is absent from the
`app` image and that image's `torchaudio` reports a CUDA mismatch against `torch`
(2.1.2+cu121 vs a CUDA-11.8 build), so it needs a new sandbox image on the
`experiments/vocalparse` pattern. The ACE-Step Transcriber entry's one open
problem therefore stays open, and line *offsets* on the three non-`_test_song`
gold songs remain unusable as truth.

### Conclusion

The premise holds: the operator marks vocal edges, nothing in the pipeline emits
them, and a stem-gated hysteresis detector finds them far better than the shipped
segmentation does. What is **not** established is the claim the entry rests on —
that the stem gate and the hysteresis are what does the work. Against a fixed
threshold on mix RMS the win appears only on the dense mixes, and the two were
never compared at a matched firing budget. Two things stand between this and a
promotion discussion, in order: a budget-matched ablation against the mix-RMS
baseline, and Part B, which is also the ACE-Step entry's blocker.

---

## Reactive band dynamics — MilkDrop's auto-gain normalisation instead of whole-song percentiles

<https://www.geisswerks.com/milkdrop/milkdrop_preset_authoring.html>

### Status

**[DONE] — concluded, negative on its own headline hypothesis.** Measured fairly,
the incumbent's whole-song percentile normalisation **beats** the local auto-gain
this entry was built to displace, for discrete accent extraction. The dense
per-beat stream — the intended deliverable — was never measured separately and
remains an untested claim. Awaiting the operator's archive-or-promote decision
(§3.3).

### Why? What for?

Realtime music visualisers solved "make a rig look like it is listening" twenty
years ago, and the feature set they solved it with is astonishingly small. The
entire audio vocabulary a MilkDrop preset can read is `bass`, `mid`, `treb`,
their damped twins `bass_att` / `mid_att` / `treb_att`, and `vol` — seven
numbers per frame. projectM, which reimplements it, extracts the same three band
amplitudes by FFT and passes them plus their attenuated forms to every shader.

What makes those seven numbers work is **the normalisation, not the bands**.
MilkDrop's variables are auto-gain adjusted against a *short running average*:
`bass = instantaneous bass volume / smoothed average bass volume`, so `1` is
normal, below ~`0.7` is quiet and above ~`1.3` is loud bass — and it reads the
same whether the source is a CD or a radio stream. The question the number
answers is "**is the bass hitting harder than it has been hitting lately?**"

Our `artifacts/essentia/fft_bands.json` already has strictly more raw material —
seven bands at 50 ms, plus `brightness_ratio`, `transient_strength` and
`dropout_strength` — but it normalises with
`per-song-per-band-log-power-percentile` over the 5th–95th percentile of the
**whole song**. That answers a different and much less useful question: "is this
loud *for this song*?" Inside a quiet breakdown every band sits near the bottom
of the song-wide range, so a hit that is unmistakable to the ear is numerically
invisible. A lighting cue in a breakdown is exactly the cue that must not be
missed. And `fft_bands.json` is not on the MCP surface at all, so today the
answer reaches nobody.

The second thing MilkDrop gets right is **two timescales from one signal**. The
attenuated variables drive what should move slowly — dimmer level, colour, pan
and tilt on a moving head. The instantaneous variables drive what should snap —
strobe, shutter, a colour flick on the accent. A single "energy" curve cannot
serve both, and the pipeline currently emits neither.

The deliverable: a compact, beat-synchronous, locally-normalised band stream the
authoring model can read as "how hard, in what part of the spectrum, right now,
relative to a moment ago" — plus a discrete accent list derived from it.

### Experiment Plan

Build as `experiments/reactive_bands/`, no new image (numpy over existing JSON).

- **Inputs, all trusted phase-1:** `artifacts/essentia/fft_bands.json` (raw band
  power before the percentile squash — recompute from audio in the experiment
  rather than un-normalising), `artifacts/essentia/rms_loudness.json` (per-stem),
  `beats.json`.
- **Collapse to MilkDrop's three bands** (`bass` ≈ sub+bass, `mid` ≈
  low_mid+mid, `treb` ≈ upper_mid+presence+brilliance) *and* keep the seven-band
  form, so the ablation can say whether three is enough.
- **Local auto-gain:** for each band, divide instantaneous power by an
  exponentially-weighted running mean of that band. Sweep the averaging window —
  1 s, 2 s, 4 s, 8 s, and a bar-length window — and pick by measurement, not by
  taste. Emit both the raw ratio (`bass`) and a damped ratio (`bass_att`), the
  damping constant also swept.
- **Per-stem as well as per-mix.** MilkDrop had no stems; we do. A `vocals`
  reactive curve and a `drums` reactive curve are strictly more informative than
  the mix, and the stems are already trusted.
- **Reduce for the token budget.** The projected form is per-beat and per-bar
  aggregates (max and mean of the instantaneous ratio, mean of the attenuated
  one), not a 20 Hz stream. State the byte cost per song in the results.
- **Accents.** Where the instantaneous ratio crosses a threshold above its
  attenuated twin, emit a discrete accent `{time, band, strength, beat, bar}`.
  This is the transferable core of MilkDrop's beat detection, and unlike it we
  can snap to the essentia beat grid, which is measured good.
- Export `data/analysis/<song>/reference/proposals/reactive_bands.json`; add a
  **Reactive Bands** lane (three curves plus accent ticks) under Human Hints,
  copying the Drop Proposals lane (§3.2).

**Measurement — fixed before the run (§3).**

1. **Accents vs. ground truth.** Hit-rate of accent times against the 7
   hand-marked drop impacts at ±0.25 / ±0.5 / ±1.0 s, reported with accents per
   minute — a dense detector that hits everything proves nothing (this is the
   same budget-aware framing the allin1 entry uses).
2. **The ablation that justifies the whole entry:** identical detector, two
   normalisations — local running mean vs. the incumbent whole-song percentile.
   Report hit-rate overall *and* restricted to hints that fall inside
   low-loudness passages, which is where the two should diverge.
3. **Cheap baseline:** thresholded raw per-stem RMS from `rms_loudness.json`.
4. **Window sweep table** — one row per averaging window, so the chosen constant
   is defensible.

**Reach test (§1.3) — which projected file this lands in.**

A new dense artifact plus per-beat aggregates. The input guide explicitly
invites this: *"If a new dense signal would be valuable (e.g. a spectral-flux or
onset-strength stream), it is one registry entry in `detail.py` — propose it."*
Accents additionally become `song_event_timeline.json` events with a real
`intensity`.

### Results evidence

Built as [`experiments/reactive_bands/`](../experiments/reactive_bands/README.md);
`bands.py` replicates the incumbent's exact FFT frame parameters (44.1 kHz,
4096-sample Hann, 50 ms hop) so that normalisation is the only variable. Full
tables in [`out/score.txt`](../experiments/reactive_bands/out/score.txt). Gold
set, 7 drop impacts.

**A methodology bug was caught mid-run, and fixing it inverted the result.** The
first ablation pass applied the same *absolute* accent threshold to both curves.
That is not a comparison: the local ratio is unbounded (`power / running_mean`,
spikes past 10) while the incumbent's percentile ratio is clipped to `[0, 2]` by
construction, so a cutoff like 2.0 made the percentile curve fire ~0 accents
whatever the quality of its normalisation. Replaced with a per-song binary search
on each curve's own threshold to a matched ~29 accents/min.

| normalisation, budget-matched at ~29/min | ±0.25 s | ±0.5 s | ±1.0 s |
| --- | --- | --- | --- |
| local running mean (2 s) | 2/7 | 4/7 | 5/7 |
| **whole-song percentile (incumbent)** | **5/7** | **7/7** | **7/7** |

**At a matched budget the incumbent wins outright.** That is the opposite of this
entry's hypothesis, and it is the result.

**The sub-hypothesis the entry was actually designed around is at the noise
floor.** Whether local normalisation helps *specifically* inside quiet passages
has **2** qualifying impacts in the whole gold set, and they tie either way (2/2
at ±0.5 s both). Not resolved — this needs more hand-marked low-loudness impacts,
not more tuning (§3, "ground truth is precious and scarce").

**The discrete-accent measurement is itself unstable to how the threshold is
set.** The same local detector scores 2/7 at ±0.25 s under per-song budget
matching and 4/7 at the fixed shipped threshold of 2.0, at effectively the same
average rate (29.2 vs 29.2/min). The ablation's direction is unaffected — both
normalisations were measured under one protocol — but it is a reason to distrust
small differences anywhere in these tables.

**Against a genuinely naive baseline it still wins**: thresholded raw drums-stem
RMS, no band split, no auto-gain, gets 3/7, 4/7, 4/7 while firing 130/min; the
band accents get 4/7, 5/7, 6/7 at 29/min. That is a win over no processing at
all, not over the incumbent.

**Calibration and sweeps.** The first accent threshold tried (0.5) fired 91/min —
useless as a discrete list. 2.0 was shipped (29/min, 5/7 at ±0.5 s); recall
degrades smoothly with no natural knee, so it is a token-budget choice as much as
an accuracy one. Window sweep at matched rate: 2 s best (5/7 at ±0.5 s), 1 s 4/7,
4 s and 8 s 3/7 each; a per-song bar-length window ties 2 s at 5/7 and is
arguably the more principled default, not adopted only because this gold set
cannot separate the two.

**The token-budget goal was not demonstrated.** The plan asked for the byte cost
per song. The exported proposal carries five sources × three bands, per-beat and
per-bar, and runs **0.43–1.8 MB per song** on disk (Titanium 1.69 MB; 834 KB
minified; a mix-only three-band slice of that song is 161 KB). Nothing that size
reaches an authoring model, and which one or two sources a projected form would
keep is an unmade decision.

### Conclusion

The ablation this entry exists to run came back **against** local auto-gain, once
measured fairly, for discrete accent extraction. That is the headline — not the
win over a naive RMS threshold. Three things would have to change before it is
worth reopening: the dense per-beat stream, which is the actual deliverable and a
different claim from accent recall, needs a measurement of its own; the
low-loudness hypothesis needs more than two marked impacts; and if local
normalisation is kept at all it should be for the continuous stream, not as a
replacement accent detector. The durable finding for anyone who tries this again
is the methodological one: two curves on different scales cannot share a
threshold, and the unfair version of this comparison looked like a strong
positive.

---

## Transition-FX and gesture phases — riser, downlifter, snare roll, pre-drop gap, impact

<https://www.ujam.com/tutorials/how-to-create-huge-edm-transitions/>

### Status

**[DONE] — concluded, mixed.** Beats the `event_*` stack it was built to replace
by a wide margin, and is the only method measured here that emits named phase
structure — but it loses on raw impact recall to a one-line RMS-derivative
peak-picker, and the per-primitive precision audit the plan named as the thing
that matters was not done. Awaiting the operator's archive-or-promote decision
(§3.3).

### Why? What for?

Constitution §1.2 says a drop "has an approach, a build, a tension span, an
impact and a release, and each phase becomes a different look", and that a flat
list of independent events loses the thing that matters. The current
`event_*` stack claims to do this and is measured at chance, because it infers
gestures from raw features with no named structure to hang them on — the mistake
§5.2 exists to prevent.

But there is a route that needs neither the section labels nor a model. In the
repertoire this corpus is made of, **producers construct these gestures out of a
small, named, deliberately conspicuous set of sound-design devices**, and each
one has a signal signature that is trivially detectable and essentially
unambiguous:

| device | what it is, in the producer's words | signature in our existing artifacts |
| --- | --- | --- |
| **uplifter / riser** | noise or pitch sweep climbing for 4–16 bars into the drop | high-band energy and spectral centroid rising near-monotonically over a bar-multiple span; no chord change; often no drums |
| **downlifter** | the mirror, marking the *start* of the build | the same ramp, descending, immediately after a section edge |
| **reverse cymbal / reverse reverb** | amplitude ramp terminating in a transient | envelope rising into a `transient_strength` spike |
| **snare roll / drum build** | 1/4 → 1/8 → 1/16 → 1/32 subdivision doubling | onset density from `drum_events.json` doubling across consecutive bars |
| **pre-drop gap** | one to two beats of near-silence before the hit | `dropout_strength` spike / broadband RMS collapse on a beat boundary |
| **impact** | the crash-and-sub hit that lands the drop | simultaneous sub and brilliance transient on a downbeat |

Layering these at different timescales is standard practice — a 16-bar noise
sweep for macro tension, a 4-bar pitch riser under it, a 2-bar reverse reverb
immediately before the hit. That layering *is* the phase structure the
constitution asks for, and it is legible from the outside.

The pre-drop gap deserves its own mention: a beat or two of silence followed by
the impact is the single most reliable lighting moment in this repertoire —
blackout, then everything. It is a `dropout_strength` spike we already compute
and never report.

### Experiment Plan

Build as `experiments/gestures/`, numpy only.

- **Inputs:** `fft_bands.json` (levels, `brightness_ratio`,
  `transient_strength`, `dropout_strength`), `rms_loudness.json` (per stem),
  `drum_events.json`, `beats.json`, and — if entry 1 has run — its locally
  normalised bands, which should make every one of these rules easier to state.
- **One detector per primitive**, each with an explicit written rule, a span, an
  anchor beat/bar, and its own confidence derived from how well the observation
  matched the rule (monotonicity of the ramp for a riser; the subdivision ratio
  for a roll). No tuned global threshold that means different things per song —
  thresholds relative to the song's own levels, as the CLAP character
  experiment already does.
- **Assembly into composite gestures.** Primitives that overlap or abut on the
  bar grid merge into one gesture with named internal phases —
  `approach → build → tension → impact → release` — each phase carrying its own
  start, end and confidence. A gesture missing its impact is still emitted, with
  the missing phase absent rather than guessed (§2: never invent a plausible
  default).
- **Explicitly do not name the section.** This experiment says *a build of this
  shape happens here*; it does not say "this is the drop". Deriving `kind:
  "drop"` needs the named section pair (§5.2, and the allin1 entry's refusal to
  emit one on four label pairs).
- Export `reference/proposals/gestures.json`; **Gestures** lane, rendered as
  spans with phase sub-bars so the internal structure is auditionable.

**Measurement — fixed before the run (§3).**

1. **Impact phase vs. the 7 hand-marked drop impacts** at ±0.25 / ±0.5 / ±1.0 s,
   with gestures per minute.
2. **Build spans vs. the operator's non-drop hints** — `_test_song`'s `Spacer`
   ("volume drops to restart melody"), `Outro start` ("drum and bass leaves"),
   `prepare for end`; Armin's `Breath`. Report which hints a gesture covers and
   which it misses.
3. **Incumbent:** `song_event_timeline.json` events of type build/drop/impact on
   the same songs, scored identically. **Cheap baseline:** a plain RMS-derivative
   peak-picker at the same event budget.
4. **Per-primitive precision**, hand-auditioned in the lane: for each detected
   riser and gap, does it exist in the audio? Twenty or thirty spans across four
   songs is small enough to check by ear, and precision is what matters here —
   a phantom build fires a cue that contradicts the music.

**Reach test (§1.3) — which projected file this lands in.**

`song_event_timeline.json` — the phases become the tightly-timed, few,
high-value discrete events the input guide asks for, with real `intensity` and
an actionable `summary`. If promoted this is a phase-3 stage, and it is the
first honest candidate to replace part of the `event_*` stack rather than add to
it (§3.3 — promotion that only adds is usually a mistake).

### Results evidence

Built as [`experiments/gestures/`](../experiments/gestures/README.md) — one
detector per device (riser, downlifter, reverse cymbal, snare roll, impact,
pre-drop gap), assembled into gestures anchored on a detected impact, with any
phase lacking a supporting primitive simply absent (§2). Full tables in
[`out/score.txt`](../experiments/gestures/out/score.txt). Gold set, 7 drop
impacts.

| method | ±0.25 s | ±0.5 s | ±1.0 s | events/min |
| --- | --- | --- | --- | --- |
| gesture impact phase | 2/7 | 4/7 | 4/7 | 14.1 |
| incumbent `song_event_timeline` build/drop/impact | 0/7 | 1/7 | 2/7 | 1.5 |
| **RMS-derivative peak-picker (baseline)** | **3/7** | **6/7** | **7/7** | 40.8 |

**The incumbent row is a direct confirmation of `CLAUDE.md`'s "measured at
chance"** — on the metric its own event stack exists to own, it lands 0/7 at
±0.25 s. **The baseline row is the humbling one**: an eight-detector rule engine
does not beat a one-line peak-picker on impact-instant recall. The peak-picker
fires ~3× as often and says nothing — no phases, no evidence, no claim that can
be wrong — which is why recall alone cannot settle this comparison in either
direction.

**What the gestures deliver that the baseline structurally cannot**: 12 gestures
assembled from 35 primitives on `_test_song` alone, each phase carrying its own
span, confidence and a per-primitive evidence string auditable against the audio.
That is constitution §1.2's composite gesture, and no recall number scores it.

**Non-drop hint coverage is where the limits show, and the coverage criterion is
generous.** Overlap-based coverage credits `_test_song`'s `Drum Hit`
(7.44–7.63 s, 0.19 s long) to a `build` spanning **2.8–32.2 s**, and Armin's
`Breath` (81.4–96.3) to builds and approaches spanning 78–100 s. A 29-second
build overlapping a fifth-of-a-second hint is not evidence the detector found it.
The one convincing case is `_test_song`'s `High Energy` (29.6–36.5), covered by a
dense and plausibly-timed tension/impact/release chain. It **misses outright**
all three `Vocal outro` phrases, `Synth Pad`, `prepare for end` and `Finale` —
every vocal- and texture-driven block, none of which has a riser, roll or
transient to detect. That is the vocal-phrase entry's territory rather than a bug
here; the two signals are complementary.

**The measurement the plan called for was not run.** Per-primitive precision —
does each detected riser, roll and gap actually exist in the audio, hand-audited
over 20–30 spans across four songs — is the number that decides whether these are
real, and only spot-checking against the score tables was done. A phantom build
fires a cue that contradicts the music, and nothing measured here rules that out.

### Conclusion

Positive against the stack it was built to replace, negative against the cheapest
possible baseline on the only metric measured, and the one thing it uniquely
offers — named, evidenced, phase-structured gestures — is not scored by that
metric at all. The honest reading is that this is not yet a settled result so
much as a working detector with one number attached. Before a promotion
discussion: the precision audit by ear, and a baseline made to say something
structured, so that it can be wrong too. If promoted this would be a phase-3
stage and the first honest candidate to **delete** part of the `event_*` stack
rather than sit beside it.

---

## SongFormer — the current structure SOTA, measured against our own allin1 result

<https://github.com/ASLP-lab/SongFormer>

### Status

**[PENDING] — run order 4 of 7.** Must run *before* any decision to promote
allin1, because it may change which model gets promoted.

**Not executed in the 2026-09-04 wave-2 batch.** Scoped only: SongFormer's
`requirements.txt` pins `torch==2.4.0` alongside `muq==0.1.0` and some fifty
other dependencies, and the project's own runtime figure is 2–4 s/song on an
NVIDIA L40 against this box's 4 GB GTX 1650 — a new multi-GB sandbox image on the
`experiments/acestep_transcriber` pattern, not a side task. It still gates the
allin1 promotion decision.

### Why? What for?

`allin1` is the best structural read this repository has measured — 4/7 impacts
at ±1.0 s on 1.6 boundaries/min, against an incumbent that loses to evenly
spaced guesses — and it is sitting unpromoted. SongFormer (ASLP-lab, 2025) is a
multi-resolution self-supervised structure analyser that reports **HR.5F 0.703
and ACC 0.807 on SongFormBench-HarmonixSet against All-In-One's 0.596** and
LinkSeg's 0.630, on the same Harmonix vocabulary this project already targets.
It ships checkpoints, one-click inference, and full training and evaluation
code.

If that margin survives contact with our four gold songs, promoting allin1 would
be promoting the second-best available model into a pipeline whose whole
structural read hangs off it. If it does not survive, that is itself the finding
that clears allin1 for promotion — a negative result with real value.

Worth a look in the same run: [EDMFormer](https://github.com/25ohms/EDMFormer),
a SongFormer fork adapted for EDM specifically. This corpus is EDM-heavy and the
one song `allin1` degenerates on is the synthetic excerpt; a genre-matched fork
is cheap to try once the harness exists.

### Experiment Plan

Build as `experiments/songformer/`, **mirroring `experiments/allin1/`'s file
layout exactly** — `model.py` (runs in its own sandbox image and caches raw
output per song, cache committed so the numbers reproduce without a GPU),
`features.py`, `export.py`, `score.py`, `run_in_container.sh`. Reusing that
shape is the point: the two models must be scored by the same code.

- **Reproducibility first.** `allin1`'s "degenerates on instrumental trance"
  finding turned out to be unseeded demucs, not the model — it disagreed with
  itself on 14 of 21 songs. Determine whether SongFormer demixes internally; if
  it does, seed it with the pipeline's stems as we did for allin1. If it cannot
  be seeded, run each gold song 3× and **report the disagreement rate before
  reporting any accuracy number.**
- **Do not use its beat or bar grid.** Same rule as allin1: take the structure,
  keep essentia's grid.
- **Degeneracy check** carried over from allin1 — a song that collapses to one
  or two distinct labels is `unknown`, not a confident wrong name.
- Export `reference/proposals/songformer.json`; **SongFormer Sections** lane
  placed directly beside **allin1 Sections** so the two segmentations can be
  A/B'd against the waveform, and **SongFormer Transitions** beside allin1's.

**Measurement — fixed before the run (§3).**

Reuse `experiments/allin1/score.py` verbatim so the table is directly
comparable:

| method | ±0.5 s | ±1.0 s | ±2.0 s | boundaries/min |
| --- | --- | --- | --- | --- |
| SongFormer transitions | | | | |
| allin1 transitions (incumbent for this comparison) | 3/7 | 4/7 | 4/7 | 1.6 |
| shipped `sections.json` | 0/7 | 0/7 | 1/7 | 3.6 |
| evenly spaced grid, same budget (baseline) | 0/7 | 2/7 | 3/7 | 3.6 |

Plus: label-sequence agreement with allin1 per song; distinct-label count per
song across all 21; 3-run reproducibility; and — because 7 hand-clicked impacts
**cannot** score a named segmentation, as the allin1 entry says outright — the
full label sequence written out per song for the operator to audition by ear.
Where the two models disagree on a boundary, that disagreement is the shortlist
of places worth hand-labelling next.

**Reach test (§1.3) — which projected file this lands in.**

The top-level `sections.json` and `artifacts/section_segmentation/sections.json`
— the highest-priority projected files. A promotion here deletes
`src/analyzer/stages/sections/`.

### Results evidence

*(to be filled by the run)*

### Conclusion

*(to be filled by the run)*

---

## Section identity from an invariance-trained embedding — the target is MFCC 0.73

<https://github.com/Liu-Feng-deeplearning/CoverHunter>

### Status

**[PENDING] — run order 5 of 7.** Reopens the one question the CLAP experiment
closed negatively, with the representation class its own diagnosis pointed at.

**Not executed in the 2026-09-04 wave-2 batch.** Scoped only: it needs several
model downloads (CoverHunter/ByteCover, MuQ) behind one harness alongside the
classical DTW/MFCC baseline — more image-building than the SongFormer entry, not
less.

### Why? What for?

Section identity is the measured, still-open gap. `sections/form.py` computes a
`repetition_group`, `ui_data.py` copies it into the projected `sections.json`,
and it is `null` on every section of all 21 songs — so nothing reaching the
authoring model says that the chorus at 2:10 is the chorus from 0:55 returning.
For a light show that is close to the most valuable single fact in the file: the
returning part gets the returning look, and that recall is what makes a show
read as designed rather than reactive. `allin1`'s `same_label_as` is label
repetition ("both are called chorus"), not "this is the same music".

The CLAP experiment measured the honest bar and failed to clear it: mean pair
AUC — **MFCC 20: 0.73**, CLAP raw 0.68, chroma 0.62, CLAP centred 0.61. Twenty
MFCC coefficients beat a 512-d general-purpose embedding. Its useful diagnosis:
CLAP scores 0.83 at telling a section from *itself* but only 0.68 at matching
two occurrences of the same part, so what is needed is a representation trained
for **invariance between occurrences**, not a bigger general-purpose one.

There is an entire task built on exactly that objective. Cover-song
identification trains embeddings so that two renditions of the same song — a
different key, tempo, arrangement, singer — land in the same place. That is a
strictly harder invariance than "verse 2 versus verse 1", which differs only by
an added layer or a vocal ad-lib. CoverHunter is the current SOTA, and it is
**256-dimensional** against ByteCover2's 1536 — compact enough that per-section
embeddings cost nothing.

### Experiment Plan

Build as `experiments/identity/`.

- **Fix the harness first.** Reuse `experiments/clap/score.py`'s pair-AUC
  protocol unchanged so every number is directly comparable to the 0.73 already
  on record. Sections come from the best available segmentation at run time
  (allin1's, or SongFormer's if entry 3 wins) — and the harness must be able to
  re-run against either, since a bad segmentation makes every embedding look bad.
- **Candidates, all through the same harness:**
  1. **CoverHunter / ByteCover** embeddings over section-length crops — the
     invariance-trained hypothesis.
  2. **[MuQ](https://github.com/tencent-ailab/MuQ)** layer-wise. MuQ beats MERT
     across nearly all MARBLE tasks, and the layer-wise investigation of SSL
     music models finds structural information concentrated in particular
     middle layers — so sweep layers, exactly as the MERT survey did here (MERT
     layer 2 was the one that got 5/7).
  3. **Beat-synchronous chroma with transposition search + DTW alignment cost** —
     a *cheap classical* baseline much stronger than the plain chroma that
     scored 0.62, and the one a promotion would have to beat on cost grounds.
  4. **MFCC 20** — the incumbent to beat, plus the duration and time controls
     (0.59 / 0.46) that establish the floor.
- **Report the clustering, not only the AUC.** The deliverable is a
  `repetition_group` per section; write out the actual grouping each method
  produces per song, in the lane, so the operator can say by ear which one is
  right. AUC over four songs is a thin number and should not be the only one.
- Export `reference/proposals/identity.json`; **Identity** lane colouring each
  section by its group, placed directly under the sections lanes.

**Measurement — fixed before the run (§3).**

Mean pair AUC over gold-set section pairs — **must beat 0.73** — plus the
self-vs-other gap (CLAP's 0.83/0.68), plus per-song grouping tables.

**State the noise floor.** Four songs is very few section pairs, and §3's rule
is that a measurement at the noise floor of the labels means fixing the labels,
not tuning against them. If the harness shows the AUC gap between methods is
inside the noise, the honest output of this experiment is a request to the
operator for hand-marked "these two are the same part" pairs across the corpus —
which is cheap to mark and would make every future identity attempt scorable.

**Reach test (§1.3) — which projected file this lands in.**

`sections.json` `repetition_group`, currently null everywhere, and
`get_song_brief`'s `similar_sections` grouping — which today is derived from
`section_character` string equality, a proxy the input guide itself flags as
approximate.

### Results evidence

*(to be filled by the run)*

### Conclusion

*(to be filled by the run)*

---

## Bar grid and phrase grid by musical consensus — repairing the foundation cues snap to

<https://github.com/CPJKU/beat_this>

### Status

**[DONE] — concluded, negative.** The plan's assumed strongest evidence signal —
kick placement — measured as a near-useless phase discriminator in this
repertoire; the resulting consensus ties two of the three individual trackers and
loses to the third, and its phrase grid loses clearly to allin1's. Awaiting the
operator's archive-or-promote decision (§3.3).

### Why? What for?

Beat tracking here is good — 7/7 human impacts land within 0.25 s of an essentia
beat. **Downbeats are not.** Three independent trackers (essentia, beat-this,
allin1) hit 3/7, 3/7 and 4/7 and disagree with each other in different places,
and `CLAUDE.md` says plainly: do not assume a correct bar grid.

Everything downstream assumes one anyway. `beats.json` is a projected file whose
`type: "downbeat"`, `bar` and `beat` fields the MCP server turns into the
downbeat list, and the input guide says *"cue placement snaps to downbeats and
bar numbers, so downbeat detection and bar numbering must be correct and
continuous."* A half-bar phase error puts every cue in the show on the wrong
beat — the failure is not subtle, it is the whole show being slightly wrong in a
way an audience feels.

There is also a stronger grid hiding above the bar. This repertoire is built in
**8- and 16-bar phrases**, and a cue placed on a phrase boundary is right even
when the section *label* is wrong. The allin1 experiment already measured this
by accident: its raw, unmerged 8-bar phrase edges score 4/7 at ±1.0 s and
**6/7 at ±2.0 s** — better recall than its own merged sections. Nobody has tried
to derive that grid deliberately.

### Experiment Plan

Build as `experiments/grid_consensus/`, numpy over cached tracker outputs.

- **Four hypotheses, not three votes.** Take the existing downbeat phases from
  essentia, beat-this and allin1, and add a fourth derived from the audio
  itself: the phase and period that maximise 4-beat and 8-bar periodicity in the
  beat-synchronous band-energy novelty (an autocorrelation over the beat grid,
  which is trusted).
- **Resolve by musical evidence, not by majority.** A vote between three
  trackers that are each ~45 % right is worth little. Score each candidate phase
  against facts the pipeline already measures well: kick placement from
  `drum_events.json`, chord-change positions from `harmonic.py` (harmonic rhythm
  overwhelmingly lands on downbeats), section-boundary positions, and the gap /
  impact positions from entry 2 if it has run. The phase that best explains the
  music wins.
- **Emit `unknown` when it is unknown.** Where the trackers disagree *and* the
  musical evidence does not resolve them, the artifact says so rather than
  snapping — constitution §7: *"Where the grid itself is uncertain, say so
  rather than snapping and implying precision that isn't there."* A confidence
  per downbeat, and a flagged span where the grid is untrustworthy, is far more
  useful to a cue author than a continuous lie.
- **Phrase grid as a first-class output:** the 8- and 16-bar phrase boundaries
  with an explicit anchor bar and a confidence, plus the detected phrase length
  per span (some songs switch).
- Export `reference/proposals/grid.json`; **Phrase Grid** lane, with disputed
  spans visibly marked.

**Measurement — fixed before the run (§3).**

1. **Downbeat phase** against the 7 hand-marked impacts (an impact is almost
   always on a downbeat), and against each individual tracker's 3/7, 3/7, 4/7.
2. **Phrase edges** vs. the impacts at ±0.5 / ±1.0 / ±2.0 s and at a stated
   edges-per-minute budget, against allin1's unmerged phrase edges (3/7, 4/7,
   6/7 at 3.3/min) and an evenly spaced grid at the same budget.
3. **Disagreement and `unknown` rate across all 21 songs** — how often the
   trackers conflict, and how often musical evidence resolves them. This is the
   number that says whether the current `beats.json` is quietly wrong on most of
   the corpus.
4. **Cheap baseline:** essentia's downbeats alone, which is what ships today.

**Reach test (§1.3) — which projected file this lands in.**

`beats.json` — a top-level projected file, priority 4 in the input guide — and,
if the phrase grid survives, a phrase-boundary hint category in `hints.json`
(`phrase_boundary` is already in the input guide's suggested tag set and is
never emitted).

### Results evidence

Built as
[`experiments/grid_consensus/`](../experiments/grid_consensus/README.md), reading
three already-committed caches as data — `beats.json` (essentia, trusted),
`experiments/allin1/cache/`, and `drop_detection/research/cache/beatthis/` — so
no new model or container was needed. Scope stated up front: 4/4 assumed, one
global phase per song resolved over essentia's own beat times. Full tables in
[`out/score.txt`](../experiments/grid_consensus/out/score.txt).

**The evidence sweep falsified the plan's own reasoning.** The plan asserted kick
placement would be a strong discriminator. Measured, kicks in this
four-on-the-floor-heavy corpus land **near-uniformly across all four phases** —
Titanium's histogram is `[77, 76, 65, 86]`. Every weighting that included kick
evidence at any weight scored at or below chord evidence alone:

| weighting | hits @ ±0.25 s |
| --- | --- |
| kick-only | 1/7 |
| **chord-change-only (shipped)** | **3/7** |
| section-only | 2/7 |
| gesture-only | 3/7 |
| equal-all (kick included) | 2/7 |
| kick-heavy, as originally planned | 2/7 |

The shipped weighting is chord-change-only because of this table, not because of
the plan.

**Consensus does not beat the best single tracker:**

| method | downbeat phase, hits @ ±0.25 s |
| --- | --- |
| essentia's own downbeat marking (what ships today) | 3/7 |
| beat-this | 3/7 |
| **allin1** | **4/7** |
| this experiment's consensus | 3/7 |

**Phrase grid is a clear loss**: 0/7 at ±0.5 s, 0/7 at ±1.0 s and 1/7 at ±2.0 s,
against allin1's already-measured raw unmerged phrase edges at 3/7, 4/7, 6/7 and
3.3 edges/min. The phrase-length-picking logic never got to matter — the bar
anchoring underneath it is too weak.

**The problem is deeper than phase.** On `_test_song` all four hypotheses agree
at confidence 1.0 and the resolved downbeat still misses the impact by **0.66 s**
— essentia's trusted beat *times* place no beat on that impact at all. Choosing
the right one of four phases cannot fix that.

**Corpus-wide disagreement:** across 21 songs only **6 resolve** and **15 come
back `unknown`** under the shipped weighting, with at least one hypothesis
disagreeing on 20 of 21. Of the resolved songs, musical evidence overrides
essentia's own downbeat phase on 3/21. The high `unknown` rate is the most
defensible thing here: it says chord-change evidence alone is often too sparse to
resolve a song's phase, which is §7's "say so rather than snapping" applied
honestly rather than a confident wrong grid on fifteen songs.

### Conclusion

Negative. The specific fusion tried ties two trackers, loses to the third, and its
phrase grid is clearly worse than the one allin1 already produces as a
by-product. Two things are worth carrying forward. First the kick-uniformity
result: in four-on-the-floor repertoire kick placement carries almost no
downbeat-phase information, which falsifies an assumption obvious enough that it
would otherwise be made again. Second, if allin1 is promoted for section
structure, the honest move on this problem is to take allin1's downbeat *phase*
directly — it already wins this exact comparison at 4/7 — and retire the fusion
approach rather than iterate on it. `unknown` on 15 of 21 songs may be the most
useful output this run produced.

---

## Music Flamingo — timestamped musical description, cross-checked against the stems

<https://huggingface.co/nvidia/music-flamingo-hf>

### Status

**[PENDING] — run order 7 of 7.** The frontier entry: highest ceiling, highest
risk, heaviest to run. Smoke on `_test_song` first (§3.5). Note the checkpoint
is released for **non-commercial research only** — that constrains promotion,
not experimentation, and should be settled with the operator before any
promotion discussion.

**Not executed in the 2026-09-04 wave-2 batch**, and unchanged in scope.

### Why? What for?

The CLAP experiment established two things. First, the **character layer is
real and wanted** — the operator's `Breath` block on `Armin - Revolution`
(81.4–96.3 s, "Vocal - no intense section", lit as soft moving-head motion and
slow violet parcan waves) is an undoubtable look that no verse/chorus label can
express. Second, CLAP delivers **exactly one usable axis** — calm ↔ intense —
and is confidently wrong about what is playing, reporting drums present where
the drum stem sits at 0.03.

What the pipeline actually wants is a reader that can describe a passage the way
the operator's own hints describe it, with times. Music Flamingo is the first
audio-language model built specifically for that: it is a music-specialised
Audio Flamingo 3 with **Rotary Time Embeddings, which ground audio tokens to
absolute time rather than sequence position — introduced explicitly for
structural segmentation and mapping lyrics to form** — over full-length songs up
to 20 minutes, with theory-aware captioning covering harmony, structure and
timbre. Its sibling [Audio Flamingo
Next](https://huggingface.co/nvidia/audio-flamingo-next-hf) adds Temporal Audio
Chain-of-Thought, which grounds each intermediate reasoning step to a timestamp.

If it works, one pass produces the character layer, candidate section names,
*and* the one-sentence `description` and `summary` prose the input guide asks
for and which the pipeline currently generates from templates.

**The risk, stated up front: audio-LLMs hallucinate timestamps.** The ACE-Step
experiment in this file already hit the same wall from the other side — correct
structure, no usable times. So this experiment is designed as a *timing-honesty
measurement* first and a capability demonstration second. If the times are not
real, that is the result, and it is worth knowing before anyone builds on top of
an LALM.

### Experiment Plan

Build as `experiments/music_flamingo/`, its own sandbox image.

- **Two decoding modes, compared.**
  1. *Whole song*: ask for a timestamped structural and character description in
     one pass, leaning on RoTE.
  2. *Window-anchored*: 15–30 s crops, each prompt stating the crop's absolute
     offset, so the model only has to describe, never to count. Times come from
     the crop boundary plus a within-crop position.
  The delta between these two is the direct measurement of whether RoTE's
  absolute-time grounding is real on our material.
- **Ask it how things feel, never what is playing.** The CLAP finding
  generalises and should be treated as a standing rule for any such model here:
  perceptual and structural questions to the model, factual "is there a kick"
  questions to the stems, which are exact and free.
- **Cross-check every claim against phase-1 facts, and record the check.** If it
  says "the drums drop out at 143 s", check the drum stem RMS in that window; if
  it says "the vocal enters", check the vocal stem; if it says "quiet", check
  loudness. Claims that survive are emitted with the check as provenance; claims
  that fail are emitted as `unverified` or dropped, never silently kept. **This
  grounding harness is the reusable deliverable of the experiment** — it applies
  to any future audio-LLM, and it is the only way an LALM's output can enter a
  pipeline governed by §2.
- Export `reference/proposals/description.json`; render as a **Description**
  lane of timestamped text spans, tinted by whether each claim passed its
  cross-check, directly under the Character lane so the two can be compared.

**Measurement — fixed before the run (§3).**

1. **Timing honesty** — the headline number: what fraction of the model's
   timestamped claims survive the stem cross-check, whole-song mode vs.
   window-anchored mode. Report it before anything else.
2. **Coverage of the 10 hand-marked non-drop hints**, against the CLAP character
   detector's 7/10, and time error on the ones it does find.
3. **Does it name `Breath`?** The Armin block is the reference case for the
   whole character line of work. A description of 81–96 s that says "solo vocal,
   drums out, spacious, calm" is the target; anything less specific is a miss.
4. **Baselines:** the shipped `hints.json` inference hints (the thing this would
   replace); the CLAP calm-axis character blocks; and a rules-only baseline of
   stems + `fft_bands.json`, which the CLAP ablation already showed claims 73 %
   of the corpus on its own — a description model has to be *more specific* than
   that, not just correct.
5. **Cost:** wall-clock per song and hardware needed, stated plainly. An 8 B
   model with no GPU path on this box is a heavy production dependency, and the
   ACE-Step entry is the cautionary precedent.

**Reach test (§1.3) — which projected file this lands in.**

`hints.json` (per-section, human-quality prose, short and concrete) and the
`description` / `summary` fields of `sections.json` and
`song_event_timeline.json` — all projected, all currently template-generated.
Possibly a new character/texture file, which is the same contract change the
CLAP entry flagged; the two should be resolved together rather than each adding
a file.

### Results evidence

*(to be filled by the run)*

### Conclusion

*(to be filled by the run)*
