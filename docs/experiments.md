# Experiments

One entry per experiment, carrying its plan, its measured results and its
conclusion. An entry leaves this file only when the operator picks **archive**
or **promote**. Promoted ones go to
[`archive/experiments_promoted.md`](archive/experiments_promoted.md), the rest to
[`archive/experiments_discarded.md`](archive/experiments_discarded.md) — which
also holds entries stopped before they ever ran, said so explicitly rather than
implied as a result. Both files are TLDRs: the full writeup stays in
`experiments/<topic>/README.md` where the experiment lived.

[Loose ends](#loose-ends) at the foot of this file holds the open questions the
queue *depends* on but which are not themselves experiments.

## How experiments work here

Improving the musical read is research, not only engineering. Most attempts
fail. These rules exist to make failing cheap and the failure *legible*, so the
same dead end is not walked twice.

- **`experiments/<topic>/` is a sandbox for anything** — other models, other
  libraries, other container images, throwaway code, competing approaches side
  by side. Nothing there is held to the pipeline's determinism, schema or style
  rules, and **nothing in `src/` may import from it.** The reason is specific:
  unproven work merged straight into `src/` is how the analyzer accumulated
  several thousand lines of event machinery built on a segmentation that
  measured at chance.
- **State the question and the measurement before starting.** What would count
  as better, on which songs, against which incumbent.
- **Always measure against the thing you propose to replace, and against a cheap
  classical baseline.** "It looked plausible" is not a result. MFCC-20 beating
  CLAP at section identity is the standing example of why the baseline matters.
- **A negative result is a deliverable.** Write down what was tried, what it
  scored, and what specifically was wrong with it.
- **Keep the record where the experiment lives** — `experiments/<topic>/README.md`,
  alongside the numbers. That README is current material and stays in the tree
  regardless of age; measured evidence does not go stale.
- **Ground truth is precious and scarce.** When a measurement sits at the noise
  floor of the labels, say so and fix the labels rather than tuning against them.

### Run against the four gold songs

`_test_song`, `Titanium - David Guetta ft Sia`, `Hideaway - Kiesza`,
`Armin - Revolution` — the songs with hand-labelled ground truth, so the only
place a measured comparison means anything. When an experiment is too heavy for
all four, or is only a smoke test, use `_test_song` alone.

### Make it reviewable — add a UI lane

Musical output has to be *heard against the song*, not read as a table. Anything
time-bearing — boundaries, regions, events, curves — gets its own lane in the
debugger, played against the waveform and the human hints. The pattern to copy:
`experiments/drop_detection` writes
`data/analysis/{song}/reference/proposals/drop_impacts.json`, and the UI
renders it as the **Drop Proposals** lane directly beneath **Human Hints**.

- Output goes under `reference/proposals/`, never into `artifacts/` and never
  into the stable top-level contract. It is a proposal, not a deliverable.
- It never overwrites `reference/human/` — hand-authored truth stays hand-authored.
- The lane is registered like any other, and removed when the experiment is
  abandoned or promoted.

An experiment whose output cannot be placed on a timeline just reports numbers.

### Promotion is asked for, never assumed

When an experiment beats the incumbent, **stop and ask before moving anything
into `src/`.** A better number is necessary, not sufficient; the cost of
carrying another production stage is a judgement about the pipeline as a whole.

A promotion proposal states: what it replaces, the metric and **both** numbers,
what gets **deleted** from `src/` in the same change, and which projected file
changes. Promotion that only adds is usually a mistake — the point of the
sandbox is that the production pipeline stays small.

### Entry shape

Title, then the **URL** of the model or repo on the very next line (that link
may carry its own instructions, so it is the first thing a reader follows), then
`### Status`, `### Why? What for?` (the purpose in the operator's terms),
`### Experiment Plan` (the implementation plan under `experiments/<topic>/`),
`### Results evidence` (the gold-set comparison against the incumbent *and* the
baseline) and `### Conclusion` (a short TLDR).

---

## The queue

## CLAP — character layer (calm/intense texture blocks)

<https://github.com/LAION-AI/CLAP>

### Status

**[OPEN] — blocked on ground truth, not on method.** CLAP's *section-identity*
result (measured, negative: MFCC 20 beats CLAP) is concluded and archived —
[`archive/experiments_discarded.md`](archive/experiments_discarded.md). This
entry is the other
half: a character/texture layer beyond verse-chorus arrangement, and on the
little truth that exists it is measured and positive.

**Split, 2026-09-06.** The allin1 frame-posterior finding this experiment turned
up is a separate and much cheaper question, and now has its own entry below —
that posterior is already cached in production and needs no CLAP forward pass.
What stays here is the CLAP half only: the perceptual calm ↔ intense axis.

**Do not run more CLAP work until texture blocks are marked** on `Titanium` and
`Hideaway` (see [Loose ends](#loose-ends)). The gold set holds **12 non-drop
hints, 10 of them inside the 58-second synthetic `_test_song`**. This entry's
thresholds are being hand-set against an absence of labels, and no amount of
method work fixes that.

### Why? What for?

To see what CLAP can infer *beyond the song arrangement sections*. The
reference case is the operator's own ground truth — `Armin - Revolution`
`hint-006`, "Breath", 81.395–96.326, *"Vocal - no intense section"*, lighting
*"soft motion of moving heads. parcans slow violet waves"*. An undoubtable
voice block, worth its own look, and invisible to any verse/chorus label
(the "what happens inside a part" deliverable (docs/product-definition.md); see the pinned operator
guidance on non-arrangement character blocks). `_test_song` shows the same at
finer grain: `Spacer`, `Outro start`, three `Vocal outro` phrases, `Finale`.

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

*This measurement is the origin of the separate `allin1` label-posterior entry
above, and is quoted there. It stays here because it was measured by this
experiment.*

### Conclusion

CLAP is worth keeping for exactly one thing: **a perceptual intensity axis**. It
cannot say what is playing — the stems do that better and for free. It can say
whether a passage feels calm or intense, which is the axis the operator's hints
are actually written in, and combined with the stems it nearly halves a texture
detector's false territory.

**The contract question this entry used to carry is answered.** It said a
promotion would need a new projected file, since no file in
[`mcp-definition.md`](mcp-definition.md) carries texture. The v3.2 plan creates
that file — top-level `arrangement_state.json`, shaped so a CLAP `feel` field
fuses into the same rows without a rewrite. So this entry no longer proposes a
file. It proposes **one field on an existing one**, which is a far smaller
promotion than it was, and it no longer "deletes nothing" in isolation — it
enriches a row the pipeline is already publishing.

What stands between it and that promotion is the ground truth, and only that.
The thresholds are hand-set against 10 blocks in a 58-second synthetic excerpt.
Mark texture on `Titanium` and `Hideaway` first; the arrangement-state entry is
blocked on exactly the same labels, and one marking session unblocks both.

One warning for whoever tunes this next, from `arrangement_state`'s
Measurement 1: this experiment's `smooth_s: 2.0` / `min_block_s: 4.0` is why it
emits only three blocks on `_test_song` and misses the 16 s vocal entry, the
36.5 s `Spacer` and the whole outro structure. **The smoothing was the cost, not
the stems.**

---

## allin1's label posterior — the structure it already computes and throws away

<https://github.com/mir-aidj/all-in-one>

### Status

**[OPEN] — split out of the CLAP character entry on 2026-09-06, with its first
observation already in hand.** Not yet run as an experiment in its own right.
Ranked ahead of every other open entry on cost alone: **no new model, no new
image, no GPU, no new published file.**

### Why? What for?

`segmentation.py` ships an argmax over allin1's ten-label frame posterior,
quantised to 8 bars. The posterior is far richer than its argmax — and the
pipeline **already computes and caches it**. `analyzer.allin1_cache` persists
the `label` activation at 100 Hz for every song, because `timing.py` needed the
`downbeat` stream out of the same forward pass and running the model twice was
not acceptable. So this signal is sitting in the production cache at zero
marginal cost and nothing reads it.

Two things it plausibly answers, both of which the shipped surface currently
either gets wrong or honestly refuses:

- **Structure the argmax cannot express.** On `Armin - Revolution` the label
  `break` appears in no published section, yet holds 30 % of the frame
  posterior across 143.4–175.0 s — exactly where the drum stem falls to 0.011.
  An 8-bar argmax has no way to say that, and a breakdown is a look change.
- **A measured basis for `function_status`.** That field is set to `"unknown"`
  today by a coarse heuristic over the *label set* — too few distinct labels, or
  one label covering too much of the track. Per-section posterior entropy
  measures how sure allin1 actually is, per section rather than per song: on
  `Armin` it averages 0.78, meaning the model names the form while being nearly
  opinion-less about it. That is a confidence, and this repo's rule is that
  confidence is a separate numeric field that is never inflated.

### Experiment Plan

Not yet built. `experiments/allin1_posterior/`, reading the committed
`analyzer.allin1_cache` caches as data — no model run, so the ordinary `app`
service is enough and no research image is needed.

1. **Entropy as a real confidence.** Per published section, take the mean
   posterior entropy over its frames. Score it against the gold songs: does
   entropy separate the sections a listener would call correctly named from the
   ones they would not? The incumbent is the current label-set heuristic, which
   has never been measured at all — that is a low bar and it should be stated as
   one. Baseline: section duration (long sections are likelier to be named
   right), so the entropy claim has to beat the trivial explanation.
2. **Shadow labels.** Find spans where a non-argmax label holds a sustained
   share of the posterior — the `Armin` `break` is the worked example — and score
   their boundaries on the gold set against `sections.json` as the incumbent and
   an even grid at matched boundary budget as the baseline.
3. **Reach test, settled before building.** Both outputs land on rows that are
   already published: entropy as a second, honestly *named* confidence on
   `sections.json` (never folded into the existing one, which measures something
   else), shadow labels as an optional field on the same rows. **This entry
   proposes no new file** — it is the only open entry that adds nothing to the
   delivery surface.

Time-bearing output goes to `reference/proposals/allin1_posterior.json` with its
own debugger lane, per the UI-lane rule above.

### Results evidence

Carried over from [`../experiments/clap/`](../experiments/clap/README.md), which
measured the posterior incidentally while testing something else. This is **one
song, observational** — it is what justifies opening the entry, not a result:

- `Armin - Revolution`: `break` holds 30 % of the frame posterior across
  143.4–175.0 s and appears in no published section; the drum stem reads 0.011
  across that span.
- Per-section posterior entropy on that song averages 0.78.

No gold-set comparison, no baseline, no incumbent number. Everything in the plan
above is unrun, and this section must not be cited as if it were a measurement.

### Conclusion

*(to be filled by the run)*

---

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

**Highest ceiling in the open queue, 2026-09-06.** It is the only entry with a
positive measured result blocked on something buildable rather than on ground
truth. Its blocker — a forced aligner — is the *same* sandbox image that the
vocal-phrase entry's unbuilt Part B needs. One image build unblocks both; see
[Loose ends](#loose-ends).

### Why? What for?

Same goal as [VocalParse](archive/experiments_discarded.md#vocalparse--singing-voice-transcription-lyrics--melody):
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
top-level `lyrics.json` (a deliverable-contract change + MCP handoff) and its structure
feeds section naming rather than shipping as its own file.

---

## Vocal phrase blocks — the boundaries the operator actually marks

<https://github.com/m-bain/whisperX>

### Status

**[OPEN] — one cheap re-score from a decision, and the likely answer is
archive.** Part A concluded: the detector finds the operator's vocal-phrase
edges 5–6× better than the shipped `sections.json`, but does not clearly beat a
naive mix-RMS threshold once its firing rate is accounted for, and the two were
never compared at a matched budget. Part B (forced alignment) was never built.

**Do not build the budget-matched ablation this entry asked for.** A cheaper
test now exists and probably settles it. `arrangement_state` — promoted into the
pipeline in v3.2 as the `detect-arrangement-state` stage — emits
`+vocals` / `-vocals` edges from the same per-stem RMS series, and its
Measurement 1 shows that hysteresis-plus-smoothing, which is exactly this
entry's method, **halves** F1 on `_test_song` (0.59 → 0.27) and displaces a
hand-marked boundary by 6 s. So the decision path is:

> Score the shipped `detect-arrangement-state` stage's vocal edges against this
> entry's existing 94-boundary scorer. If the stage that is being promoted
> anyway matches or beats this detector, this entry archives with **zero** new
> production code.

Only if the standalone detector wins that comparison is the budget-matched
ablation against mix-RMS worth running.

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
line offsets are usable on `_test_song` only** — which is precisely the
"use `_test_song` alone" case, and precisely why the second half of this
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
  the physical onset — the transient wins over the nearest grid position.

**B — real onsets for the transcript (whisperX / wav2vec2 forced alignment).**

- Force-align ACE-Step Transcriber's transcript — measured at WER 0.04 and 0.23,
  the best text available — to the vocal stem. This is the "not yet built" step
  the ACE-Step entry's conclusion names as next, and it also repairs the lumped
  Moises offsets so the other three gold songs become usable phrase truth.
- Compare the aligner's word times to Moises on `_test_song`, where Moises is
  now trustworthy, before trusting it anywhere else.

**Measurement — fixed before the run.**

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
— a proposal lane, never a deliverable.

**Reach test.** If promoted, `vocal_phrase` / `instrumental_gap` /
`sustained_note` become events in `song_event_timeline.json`, which is already
projected. Nothing new joins the top-level contract, and the reference lyrics
themselves stay validation-only — the detector reads the stem, never
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

## SongFormer — the current structure SOTA, measured against our own allin1 result

<https://github.com/ASLP-lab/SongFormer>

### Status

**[PENDING] — the only pending entry still carried.** The two siblings it was
queued alongside were archived un-run on 2026-09-06: section identity (reopens a
closed negative) and Music Flamingo (non-commercial licence, so a positive
result could not ship). This one is kept because **structure is the weakest
interpreted layer in the pipeline** — `segmentation.py` measures F1 0.67 — and
SongFormer attacks exactly that.

**Still not executed, and unchanged in scope.** Its `requirements.txt` pins
`torch==2.4.0` alongside `muq==0.1.0` and some fifty other dependencies, and the
project's own runtime figure is 2–4 s/song on an NVIDIA L40 against this box's
4 GB GTX 1650 — a new multi-GB sandbox image on the
`experiments/acestep_transcriber` pattern, not a side task. Carrying it means
accepting that image build; if that is not going to happen, archive it rather
than leaving it pending a third time.

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

**Measurement — fixed before the run.**

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

**Reach test — which projected file this lands in.**

The top-level `sections.json` and `artifacts/section_segmentation/sections.json`
— the highest-priority projected files. A promotion here deletes
`src/analyzer/stages/sections/`.

### Results evidence

*(to be filled by the run)*

### Conclusion

*(to be filled by the run)*

---

## Arrangement state — *who is playing*, from a file we already publish

No model, no repo. The detector is arithmetic over
`data/analysis/{song}/loudness.json`:
[`../experiments/arrangement_state/README.md`](../experiments/arrangement_state/README.md)

### Status

**[PROMOTING] — v3.2, plan written.** The v3.2 implementation plan promotes the
detector into a phase-3 `detect-arrangement-state` stage and publishes a new
top-level `arrangement_state.json`. This entry is retired by that plan's item 5,
which deletes `experiments/arrangement_state/` and moves this text to the
archive; it stays here until the production path is proven.

Promoted on `_test_song` evidence alone, knowingly: F1 0.59 @0.5 s (median hit
error 0.07 s) where `sections.json` scores 0.00, and unmeasurable on the other
three gold songs because their hand-marked hints are almost entirely drop
stages. That is a limit of the labels, not of the detector — see
[Loose ends](#loose-ends).

The file is shaped so the **CLAP character layer** can fuse a `feel` field into
the same rows later without a rewrite: the stems say what is playing, CLAP says
how it feels. The two entries' shared contract question is therefore settled by
this plan, not left open.

### Why? What for?

It began as a question about the debugger. Reading `_test_song`'s per-stem RMS
lane, the operator said:

> bars 7–15 there is a voice approach to a high energy region from bar 15–22 …
> we do not want the exact name, but something to tell "something is happening
> here, that is different to other region". Why is it so hard for models to
> infer something there?

Everything the authoring model is told about those fifteen seconds is one row:

```
section-002   14.82 → 58.05   "chorus [unverified]"   confidence 0.446
```

A single 43-second section covering the vocal approach, the drop, the
high-energy region, the spacer and the whole outro. The model is not failing to
infer a contrast — the surface it reads has no contrast on it.

And the reason is structural, not acoustic. Every producer of published
structure reads something other than the stems: `segmentation.py` reads a mix
spectrogram and quantises to 8 bars (≈14.8 s on this song — longer than the
entire high-energy region it would need to name); `harmonic.py` reads HPCP, and
the chord is `D#m` on both sides of every boundary in question; `gestures.py`
reads mix FFT and drum onsets and emits *events*, never a state. The one stage
that reads the stems, `loudness.py`, publishes the series and draws no
conclusion from it.

So the signal is already in the delivery surface, as numbers, and nothing turns
it into a fact. This is a plumbing gap, not a perception problem — which is
exactly why it is worth an experiment rather than a model.

### Experiment Plan

Under [`../experiments/arrangement_state/`](../experiments/arrangement_state/),
stdlib only, run in the ordinary `app` service:

```bash
docker compose run --rm --no-deps -T --entrypoint python app \
  -m experiments.arrangement_state.run score
docker compose run --rm --no-deps -T --entrypoint python app \
  -m experiments.arrangement_state.run export
docker compose run --rm --no-deps -T --entrypoint python app \
  -m experiments.arrangement_state.run ablation
docker compose run --rm --no-deps -T --entrypoint python app \
  -m experiments.arrangement_state.run margin-sweep
docker compose run --rm --no-deps -T --entrypoint python app \
  -m experiments.arrangement_state.run breath-compare
```

Every table below regenerates from one of these five commands into
`experiments/arrangement_state/out/*.txt` — none of the numbers in this entry
are asserted.

`detector.py` reads the **published** `loudness.json` — not the artifact — so
the result also demonstrates that a phase-3 stage could produce this without
touching audio. Three decisions carry it:

1. **Per-stem, per-song thresholds.** A stem sounds when it is within 18 dB of
   its own 98th percentile in this song. Nothing absolute, nothing shared
   between stems or songs.
2. **Detect at 250 ms, gate on persistence (1.5 s), report the fine edge.** The
   reported time is never a smoothed centre.
3. **The mix channel never triggers a change** — it is a sum of the stems.

Every change carries `margin_db`, the smallest dB headroom among the stems that
flipped: a measured distance from the decision boundary rather than a tuned
score, and the natural confidence for a published row.

**Measured against** the shipped `sections.json` boundaries (the incumbent) and
an evenly spaced grid given the same detection budget (the baseline that killed
CLAP semantic novelty). **Ground truth** is the start time of every hint in
`reference/human/human_hints.json` — the operator's own answer to "something
different starts here".

**Reach test — which projected file this lands in.** Not yet decided, and it is
the open contract question: either new rows in `sections.json` distinguished by
kind, or a new top-level character/texture file. Whichever is chosen must serve
the CLAP entry too. Nothing here is worth building into `src/` until that is
settled.

**Still to do:** the UI lane is built (`reference/proposals/arrangement_state.json`
renders as the "Arrangement State" lane in `ui/src/timeline/laneState.ts`,
positioned below Moises Lyrics / above Drop Proposals, so this can now be
judged by ear against Human Hints). The one thing outstanding is texture hints
on `Hideaway`, `Armin` and `Titanium`.

### Results evidence

Full report: [`../experiments/arrangement_state/out/score.txt`](../experiments/arrangement_state/out/score.txt).

**`_test_song` — the one song labelled densely enough to measure.** 15 hints in
58 s:

| method | n | P / R / F1 @ 0.5 s | @ 1.0 s |
| --- | --- | --- | --- |
| **arrangement state** | 17 | **0.59 / 0.60 / 0.59** | **0.76 / 0.73 / 0.75** |
| shipped `sections.json` (incumbent) | 1 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| even grid, same budget (baseline) | 17 | 0.18 / 0.27 / 0.21 | 0.47 / 0.73 / 0.57 |

Median absolute error over the nine hits is **0.07 s**. The operator's two named
boundaries land at `29.75 +bass -vocals` (hint `High Energy`, 29.59, d=+0.16)
and `42.50 -bass` (hint `Outro start`, 42.48, d=+0.02).

The six misses partition cleanly and **none belong to this detector**: `Drum
Hit` (a 186 ms one-shot → `gestures.py`), the three drop stages at 27.6–29.1
(sub-bar gesture internals → `gestures.py`), `Vocal Outro 3` (a phrase split
inside continuous vocals → the vocal-phrase entry above) and `prepare for end`
(a fade, not a stem flip → an envelope-slope term nobody has built). The four
together account for 15/15, and three already exist.

**The Armin `Breath` block, without a model.** The reference case for the whole
character line of work. `run breath-compare` computes every cell from files at
run time — the hand-marked span from `human_hints.json`, the arrangement-state
block from `detector.blocks()`, and the CLAP row from
`reference/proposals/character.json` block `char-004`:

| source | block | start error | end error |
| --- | --- | --- | --- |
| hand-marked | 81.39 – 96.33 | — | — |
| **arrangement state (stems only)** | **83.00 – 95.50** | **+1.61 s** | **−0.83 s** |
| CLAP character layer (`stems+clap`, `char-004`) | 83.50 – 95.00 | +2.11 s | −1.33 s |

**Correction from an earlier draft of this table:** the arrangement-state start
was previously reported as `81.50` (+0.11 s), which merged by hand across a
1.75 s drum re-entry at 81.25–83.0 s that the detector reports as its own
block. The mechanically-correct block matching "no intense section" is
`83.00–95.50`; the earlier number was not reproducible from the committed
detector and has been replaced. It is still tighter than the GPU pass on both
edges, by a smaller margin than first claimed. This does not overturn the CLAP
ablation — the calm/intense axis still cuts a texture detector's false territory
from 73 % to 41 % — it confirms that experiment's own division of labour: the
stems say *what is playing*, CLAP says *how it feels*.

**Smoothing is the failure mode, and it is not a small effect.** `detector.py`
now implements the smoothed variant explicitly as `detect_smoothed()`, so
`run ablation` regenerates this table rather than asserting it — duty cycle
(mean presence over the ±1.0 s neighbourhood) gated by hysteresis, in place of
the persistence gate, same song:

| variant | n | P / R / F1 @ 0.5 s | `Spacer` boundary error |
| --- | --- | --- | --- |
| **persistence gate, fine edge reported (shipped)** | 17 | **0.59 / 0.60 / 0.59** | **0.00 s** |
| ±1 s duty-cycle smoothing + hysteresis | 15 | 0.27 / 0.27 / 0.27 | 6.00 s |

This is "the physical onset wins over the nearest grid position" as a number,
and it explains a known result: the CLAP character layer's `smooth_s: 2.0` is
why it emits three blocks on `_test_song`, missing the 16 s vocal entry, the
`Spacer` and the whole outro.

**The corpus — and why its number measures the labels, not the detector.**

| song | hints | state F1 @0.5 s | incumbent F1 @0.5 s | grid F1 @0.5 s |
| --- | --- | --- | --- | --- |
| `_test_song` | 15 | **0.59** | 0.00 | 0.21 |
| `Hideaway - Kiesza` | 5 | 0.13 | **0.33** | 0.00 |
| `Armin - Revolution` | 12 | 0.20 | **0.24** | 0.09 |
| `Titanium - David Guetta ft Sia` | 15 | 0.07 | **0.33** | 0.07 |
| **corpus (pooled)** | 47 | **0.20** (R 0.43) | **0.24** (R 0.19) | 0.08 (R 0.19) |

Read straight, the detector loses to the incumbent on pooled F1 while more than
doubling its recall. Both halves are real, and the cause is the label set:
**32 of the 47 corpus hints are the five stages of a drop** — Hideaway 5 of 5,
Titanium 15 of 15, Armin 10 of 12. Those belong to `gestures.py`. Outside
`_test_song` the corpus holds exactly **two** texture hints. So on three of four
gold songs every genuine arrangement change is scored as a false positive by
construction.

Tuning does not rescue it, which is the confirming check: `run margin-sweep`
filters `detect()`'s own changes to `margin_db >= threshold` and rescores —
gating trades recall for precision and never improves pooled corpus F1 @0.5 s:

| min `margin_db` | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pooled F1 @0.5 s | 0.20 | 0.20 | 0.19 | 0.18 | 0.17 | 0.16 | 0.10 | 0.10 |

That is the expected shape for a detector whose false positives are mostly
unlabelled true positives.

### Conclusion

**The contrast the operator can read off the UI in one glance is recoverable by
arithmetic over a file the pipeline already publishes, and no shipped stage
looks for it.** F1 0.59 @0.5 s on `_test_song` where `sections.json` scores
0.00 (median hit error 0.07 s), and the reference `Breath` block found tighter
on both edges than a CLAP forward pass.

The honest limit is the ground truth, not the method: the corpus score is
measuring an absence of texture labels on three of the four gold songs. **Mark
texture blocks there before tuning anything** — the detector is being promoted
on one song's evidence, which is a knowing bet, not a measured corpus result.
See [Loose ends](#loose-ends).

Both things this conclusion once listed as outstanding are done: the UI lane is
built, and the contract decision shared with the CLAP entry is taken — a new
top-level `arrangement_state.json`, with room for a CLAP `feel` field on the
same rows.

---

## Loose ends

Open questions this queue depends on that are **not themselves experiments**.
They are recorded here rather than acted on, because each is a decision, not a
task.

### The gold set has almost no non-drop ground truth

Counted directly from `reference/human/human_hints.json` on 2026-09-06:

| song | drop-stage hints | everything else |
| --- | --- | --- |
| `_test_song` (58 s, synthetic) | 5 | **10** |
| `Titanium - David Guetta ft Sia` | 15 | **0** |
| `Hideaway - Kiesza` | 5 | **0** |
| `Armin - Revolution` | 10 | **2** |

**12 non-drop hints in the whole gold set, 10 of them inside one 58-second
synthetic excerpt.** Every open entry that is not about drops is being scored
against labels that mostly do not exist — which is why `arrangement_state` is
promotable on `_test_song` alone and unmeasurable elsewhere, and why the CLAP
character thresholds are hand-set.

This is the standing rule "ground truth is precious and scarce — when a
measurement sits at the noise floor of the labels, say so and fix the labels
rather than tuning against them" coming due. **Marking texture blocks on
`Titanium` and `Hideaway` in the debugger unblocks three entries at once** and
is worth more than any method work currently queued. It is an operator task: the
hints are hand-authored truth and nothing in the pipeline may write them.

### One sandbox image unblocks the two best open entries

ACE-Step Transcriber's only gap is timing — it emits ordered lines and `[tags]`
with no seconds — and the vocal-phrase entry's unbuilt Part B is forced
alignment. **These are the same missing forced-aligner image.** `transformers`
is absent from the `app` image and that image's `torchaudio` reports a CUDA
mismatch against `torch` (2.1.2+cu121 against a CUDA-11.8 build), so it needs a
new sandbox image on the `experiments/vocalparse` pattern. Building it once
turns the queue's highest-ceiling result into something measurable.

### Debugger lanes outlive their experiments

`ui/src/data/sparseArtifacts.ts` carries seven `reference/proposals/` lanes. The
UI-lane rule above says a lane is removed when its experiment is abandoned or
promoted, and three are now stranded by the 2026-09-06 archive decisions:

| lane | state |
| --- | --- |
| `reactive_bands` | experiment archived — **retire** |
| `grid` | experiment archived — **retire** |
| `vocal_transcription` | VocalParse archived, but **keep** — shared with the open ACE-Step entry |
| `arrangement_state` | promoted by v3.2 item 4 to read the top-level file instead |
| `character`, `vocal_phrases` | entries still open — keep |
| `drop_impacts` | see below |

Retiring the two is a `ui/` change with its own tests, not a docs edit, so it is
not done here. Procedure: [`reference/ui-development.md`](reference/ui-development.md).

### `drop_impacts` may be an orphan lane

The **Drop Proposals** lane is cited in this file as *the pattern to copy* for
experiment lanes, and `experiments/drop_detection/` is still in the tree and
still read as a cache by other experiments. But `drop_detection` has no entry of
its own in either archive file — the closest is
"Transition-FX and gesture phases", promoted as `gestures.py`. Either the lane
belongs to that promotion and should have been retired with it, or
`drop_detection` was never given a queue entry at all. Worth settling before the
next lane sweep; it is the one place where the record of what was run is
genuinely unclear.
