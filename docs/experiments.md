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

The queue runner (`./analyze --include-experiments`, or `./experiment`) runs an
experiment's `compute`/`export` for any song, so its `reference/proposals/` lane
becomes reviewable across the whole corpus — useful for eyeballing behaviour.
*Scoring* still only means something on the four gold songs; the rest have no
ground truth to compare against.

### Make it reviewable — add a UI lane

Musical output has to be *heard against the song*, not read as a table. Anything
time-bearing — boundaries, regions, events, curves — gets its own lane in the
debugger, played against the waveform and the human hints. The mechanics to
copy: `experiments/drop_detection` writes
`data/analysis/{song}/reference/proposals/drop_impacts.json`, and the UI renders
it as a lane directly beneath **Human Hints**.

- **The lane title must match the experiment that writes it.** Either identical
  short names — `experiments/phrase_periodicity` renders as *Phrase
  Periodicity* — or the lane title carries the experiment's item number in
  front: *3. Phrase Periodicity*. The directory name, the experiment's own
  header and the lane label are **one name written three places**; rename them
  together or not at all.

  This is a strict rule, and `drop_detection` is the counter-example that
  prompted it: its lane reads **Drop Proposals**, which points at no directory.
  A reviewer who hears something wrong in a lane should never have to search
  `experiments/` to find out what produced it.

- **One lane per distinct claim — never consolidate.** If a signal can be
  independently right or wrong, it gets its own lane. Do not fold a derived
  output into a related lane as an extra field, do not merge lanes to reduce
  clutter, and do not hide variants behind a selector. Producing four per-stem
  artifacts means adding four lanes, not enriching one. Combining is allowed
  only where *strictly* necessary, and that has to be argued rather than
  assumed.

  The reason is the debugger's whole purpose: it is the only instrument for
  judging whether a claim is correct. A classification folded in as a field
  rides along invisibly inside a lane whose own numbers look fine, and nobody
  ever catches it being wrong. Screen space is cheaper than an unaudited claim.

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

### The queue runner

`experiments/queue.toml` is the list the queue runner walks. One `[[experiment]]`
table per experiment:

| Field | Meaning |
| --- | --- |
| `name` | experiment dir name, also its UI lane title |
| `command` | template run once per song; placeholders `{song_name}`, `{analysis_dir}`, `{song_path}`; ` && ` chains steps; runs as subprocesses, no shell |
| `image` | compose service the command belongs to; only `app` runs in-container, others are `skipped(reason)` |
| `enabled` | bool; a disabled row is listed `skipped(disabled)` |

Seeded convention: each experiment's `run.py` has `compute` then `export`
subcommands keyed by `--song <name>`, so a row is
`... compute --song {song_name} && ... export --song {song_name}`.

Adding or removing an experiment from the queue is a one-row edit to
`queue.toml` — no code change. Runner usage and failure semantics:
[`reference/cli.md`](reference/cli.md#experiment-queue).

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
Mark texture on `Titanium` and `Hideaway` first; the shipped
`detect-arrangement-state` stage's corpus number is stuck at the same label
noise floor ([`issues.md`](issues.md)), and one marking session unblocks both.

One warning for whoever tunes this next, from the shipped
`detect-arrangement-state` stage's Measurement 1
([`archive/experiments_promoted.md`](archive/experiments_promoted.md)): this
experiment's `smooth_s: 2.0` / `min_block_s: 4.0` is why it
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
test now exists and probably settles it. `arrangement_state` — shipped in v3.2 as
the `detect-arrangement-state` phase-3 stage — emits `+vocals` / `-vocals` edges
from the same per-stem RMS series, and its Measurement 1
([`archive/experiments_promoted.md`](archive/experiments_promoted.md)) shows that
hysteresis-plus-smoothing, which is exactly this entry's method, **halves** F1 on
`_test_song` (0.59 → 0.27) and displaces a hand-marked boundary by 6 s. So the
decision path is:

> Score the shipped `detect-arrangement-state` stage's vocal edges against this
> entry's existing 94-boundary scorer. If the stage that shipped anyway matches
> or beats this detector, this entry archives with **zero** new production code.

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

## Texture Novelty — self-similarity novelty over spectral features

*(no external model — classical cosine SSM + Foote checkerboard novelty)*

### Status

**[CLOSED — FAILED kill condition, kill candidate].** v3.4 item 6. Built as
[`../experiments/texture_novelty/`](../experiments/texture_novelty/README.md).
The debugger lane exists — **`2. Texture Novelty`**, under Human Hints, flask
badge, reads `reference/proposals/texture_novelty.json` — kept for **one
operator review pass**, then removed by Recipe B if the operator agrees. Do not
tune to manufacture a pass.

### Why? What for?

`sections.json` has no boundary at the `Queen of Kings` 48.7 s drop, and its
boundary F1 vs operator hints is weak corpus-wide. The refinement doc (item 2)
measured that self-similarity novelty over the 7 FFT bands has recall 0.80–1.00
against operator hints on every gold song but precision 0.05–0.50 (64–114 fires
per song). Question: does a *feature choice* keep the recall and lift precision
above 0.5 — beating `sections.json` and `arrangement_state.json`?

### Experiment Plan

Method held fixed: cosine self-similarity matrix → Foote checkerboard novelty
kernel, 1.0 s half-window → peak-pick (`mean + 1·std`, ≥ 2.0 s apart). Only the
feature changes. Feature sets, tried IN ORDER: (1) raw 7-band mix vector from
`fft_bands.json` — the measured baseline; (2) librosa chroma on the **mix**
(never the harmonic-stem `hpcp.json` — D6.1) concatenated with the mix's
percussive-band weight; (3) per-stem band weight, 28-dim, from
`fft_bands.<stem>.json` (item 1). Cheap baselines: mix-RMS delta, MFCC novelty.
Metric: boundary F1 @ ±1.0 s vs `human_hints.json` block edges on the four gold
songs.

### Results evidence

Full tables: [`../experiments/texture_novelty/out/score.txt`](../experiments/texture_novelty/out/score.txt),
reproduced by `run score`. 48 pooled human-hint block edges.

**Pooled (4 gold songs), boundary F1 @ ±1.0 s:**

| method | P | R | F1 |
| --- | --- | --- | --- |
| feat 1 — raw 7-band MIX vector | 0.12 | 0.19 | 0.14 |
| feat 2 — chroma(MIX) + percussive weight | 0.12 | 0.23 | 0.16 |
| feat 3 — per-stem band weight (28-dim) | 0.20 | 0.35 | 0.26 |
| baseline — mix-RMS delta | 0.15 | 0.42 | 0.22 |
| baseline — MFCC novelty | 0.21 | 0.38 | 0.27 |
| incumbent — `sections.json` | 0.31 | 0.17 | 0.22 |
| incumbent — `arrangement_state.json` | 0.14 | 0.44 | 0.22 |

**Per-song F1 (the three feature sets vs incumbents):**

| song | feat 1 | feat 2 | feat 3 | `sections.json` | `arrangement_state` |
| --- | --- | --- | --- | --- | --- |
| `_test_song` | 0.44 | 0.29 | 0.64 | 0.00 | 0.62 |
| `Titanium` | 0.06 | 0.00 | 0.10 | 0.24 | 0.08 |
| `Hideaway` | 0.09 | 0.11 | 0.11 | 0.31 | 0.12 |
| `Armin` | 0.13 | 0.34 | 0.33 | 0.30 | 0.23 |

**Kill condition (precision > 0.5 at recall ≥ 0.8): FAIL for every feature set**,
pooled and per song. Best pooled precision is feat 3 at 0.20. The one strong
cell — feat 3 on the synthetic `_test_song` (P 0.88 / R 0.50) — does not
generalise (F1 0.10–0.33 on the three real songs). Loosening the peak-picker
back toward the refinement doc's dense regime trades precision down toward 0.05
as recall rises — the refinement doc's own finding, reconfirmed. On the two real
vocal-pop songs `sections.json` is the best method in the table.

### Conclusion

Killed on the metric. The failure is structural: the texture-change signal is
real everywhere, which is exactly why precision cannot rise — it changes at
non-boundaries just as often. This reconfirms the refinement doc's measurement
rather than overturning it. Lane kept for one review pass; if anything survives
it is the per-stem feature direction (feat 3), which belongs to Structural vs
Micro (item 8), not here.

---

## Phrase Periodicity — bar-sequence autocorrelation of per-stem energy shape

*(no external model or repo — classical bar-sequence autocorrelation, numpy)*

### Status

**[OPEN — PASSED its kill condition].** v3.4 item 7. Built as
[`../experiments/phrase_periodicity/`](../experiments/phrase_periodicity/README.md).
Nothing in `src/` reads anything here. The debugger lane exists —
**`3. Phrase Periodicity`**, under Human Hints, flask badge, reads
`reference/proposals/phrase_periodicity.json`.

### Why? What for?

The pipeline emits **no periodicity signal at all**. Question: what is the
repetition period of a passage, and does its strength classify what kind of
passage it is (drumless long-phrase / bar loop / dense half-bar loop)?

### Experiment Plan

Method held fixed, not swept:

1. bar grid from `beats.json` downbeats — **period only, never phase**.
2. per-stem envelope: `fft_bands.<stem>.json` broadband energy (mean of the 7
   per-song-normalised band levels); documented fallback `loudness.json` 20 ms
   per-stem RMS where a song lacks per-stem FFT (`Chimera - Hana` needed
   `--stage extract-fft-bands` first).
3. collapse each bar to a 16-slot energy profile; **z-normalise per bar** (shape
   not level — load-bearing).
4. cosine-similarity autocorrelation of the bar sequence at 1–16 bar lags.
   Phrase length = peak lag in 2–16; `prominence` = peak minus neighbouring
   lags (honest confidence); prominence `< 0.05` ⇒ "no phrase structure
   detected". Regime per operator block from `rep@bar` / `rep@beat` on the
   4-stem composite.

**Cheap baseline (named ablation):** same pipeline, step 3 removed (raw
envelope). **Songs:** the four gold songs + `Chimera - Hana` + `Queen of Kings`.

### Results evidence

Full tables: [`../experiments/phrase_periodicity/out/score.txt`](../experiments/phrase_periodicity/out/score.txt),
reproduced by `run score`.

**Phrase length — z-norm vs the raw ablation (bass, prominence):**

| song | z-norm period | z-norm prom | raw prom |
| --- | --- | --- | --- |
| `Chimera - Hana` | **8** | **+0.168** | +0.004 |
| `Hideaway - Kiesza` | 2 | **+0.118** | +0.007 |
| `Armin - Revolution` | 2 | +0.081 | +0.008 |
| `Queen of Kings` | — | +0.041 | +0.007 |
| `Titanium` | — | +0.028 | +0.002 |
| `_test_song` | — | +0.005 | +0.004 |

The raw-envelope ablation finds **no phrase on any stem of any song** (every
prominence ≤ 0.03) — the per-bar z-normalisation is the whole method.
`Chimera - Hana`'s operator-stated 8-bar bass phrase is recovered on **three
stems independently** (bass +0.168, harmonic +0.101, vocals +0.248).
`Hideaway` bass reports 2 bars: the 8-bar phrase is a weaker secondary local
max, a 2-bar sub-loop dominates the curve — the experiment does not force the
operator's number.

**Kill condition — PASS.** `min(known 8-bar prominence) = +0.118 (Hideaway) >
max(rest) = +0.081 (Armin)` — prominence separates `Chimera - Hana` and
`Hideaway` bass from the four songs with no such phrase.

**Block regime — `Queen of Kings`, 3/7 marked blocks:** the two intro/bridge
blocks (through-composed) and the first percussion loop (bar-loop) classify
correctly; `Post-Intro + Harmony` reads half-bar (rep@beat 0.60) where the
operator marked bar-loop; the three ~3.4 s chorus blocks read through-composed
because each is ≈ 1.7 bars — below the ≥ 2 bars `rep@bar` needs.

### Known limit

Needs **≥ 1 bar, ideally 2**. Seven of the sixteen `Queen of Kings` blocks are
shorter (all four micro-events). This classifies block **character**, not
sub-second cues — that is item 8 (`structural_vs_micro`).

### Conclusion

**Passed on the metric.** z-normalised bar-sequence autocorrelation recovers the
operator-stated 8-bar bass phrase on `Chimera - Hana` (three stems) and phrase
prominence cleanly separates the two known-8-bar songs from the rest; the raw
ablation finds nothing. Regime classification works on blocks ≥ 2 bars and
degrades to through-composed on shorter ones, as the known limit predicts. Not
promoted, no top-level file. Kept as a proposal lane to audition against Human
Hints.

---

## Structural vs Micro — 4-bar phrase-grid fit of the operator's block edges

*(no external model or repo — classical 4-bar phrase-grid fit, numpy)*

### Status

**[CLOSED — FAILED kill condition, kill candidate].** v3.4 item 8. Built as
[`../experiments/structural_vs_micro/`](../experiments/structural_vs_micro/README.md).
The debugger lane exists — **`4. Structural vs Micro`**, under Human Hints, flask
badge, reads `reference/proposals/structural_vs_micro.json`; `micro` blocks carry
a distinct per-block tint. Kept for **one operator review pass**, then removed by
Recipe B if the operator agrees. **Do not tune to manufacture a pass.**

**This is NOT a precision filter for item 6 (Texture Novelty).** Averaged over
all operator edges the phrase-grid prior beats chance by only ~1.7–2.25×
(refinement doc item 4; this run measured 1.7–6.8× per song, mean 3.8×, the two
Eurovision-shaped songs pulling the top). It is a **two-class split the pipeline
currently cannot express**: a structural boundary that lands on the phrase grid
vs a micro cue that lives inside a phrase. **Do not re-open** `vocal_phrases`,
`grid_consensus` or `reactive_bands` — measured, none promoted, out of scope.

### Why? What for?

The operator marks both structural section edges and sub-bar micro-cues (a
pre-drop, a near-silence, a 'hey', the tension/impact/release gesture phases) in
one `human_hints.json`, and nothing downstream tells the two apart. Question:

> Does a 4-bar phrase-grid fit label operator blocks `structural` vs `micro`
> better than block duration alone?

### Experiment Plan

Method held fixed, not swept. Bar length = median downbeat spacing
(`beats.json`). Boundary set = union of items 6 + 7 proposal-block edges (the
"combination" of the two parent lanes), merged within 0.5 s. A 4-bar phrase grid
is fit by sweeping the phase offset to minimise the median edge-to-line distance
over that set. Each operator block → `kind` (`structural` if the better-locking
edge is ≤ 0.12 bars from a grid line, else `micro`) + `grid_fit_bars`. Cheap
baseline: block duration alone (`< 1 bar ⇒ micro`). Operator-truth `kind` from a
hand-checked title-keyword map with a duration fallback (`truth.py`). Metric:
per-class P/R/F1 + accuracy, pooled over the four gold songs. `Queen of Kings`
reported separately (the edge-lock table).

### Results evidence

Full tables: [`../experiments/structural_vs_micro/out/score.txt`](../experiments/structural_vs_micro/out/score.txt),
reproduced by `run score`. 45 pooled operator blocks (23 structural / 22 micro).

**Block-kind agreement — pooled, 4 gold songs:**

| method | acc | macro-F1 | structural P/R/F1 | micro P/R/F1 |
| --- | --- | --- | --- | --- |
| phrase-grid (4-bar fit) | 0.42 | **0.41** | 0.41 / 0.30 / 0.35 | 0.43 / 0.55 / 0.48 |
| duration-only (`< 1 bar ⇒ micro`) | 0.80 | **0.80** | 0.77 / 0.87 / 0.82 | 0.84 / 0.73 / 0.78 |

Per-song phrase-grid accuracy: `_test_song` 0.27, `Titanium` 0.47, `Hideaway`
0.40, `Armin` 0.60 — the baseline is 0.80 on all four.

**`Queen of Kings` — 7 of 16 operator edges lock to the fitted 4-bar grid**
(`bar_len` 1.910 s, `phrase_len` 7.640 s): the six edges the refinement doc
names (1.11, 16.32, 23.94, 31.57, 39.21, 62.16 s) lock at 0.06–0.11 bars; a
seventh (46.52 s) is marginal at exactly the 0.12 threshold; the nine misses are
the sub-bar micro-events, as predicted.

**Kill condition — FAIL.** phrase-grid pooled macro-F1 0.415 < duration-only
0.798. The distinction is real on `Queen of Kings`, but on the gold corpus the
operator's block *lengths* already carry it — a micro-event is short, and that is
enough. The phrase grid adds a weak prior that, pooled, hurts more than it helps.

### Conclusion

Killed on the metric. The 4-bar phrase-grid fit does not beat block duration at
labelling operator blocks `structural`/`micro` (macro-F1 0.42 vs 0.80). What
survives review: `grid_fit_bars` is an honest per-edge signal, and the
`Queen of Kings` edge-lock table reproduces the refinement doc's finding.
Neither is promotable on this result. Lane kept for one review pass; **not
tuned**.

---

## Loose ends

Open questions this queue depends on that are **not themselves experiments**.
They are recorded here rather than acted on, because each is a decision, not a
task.

### The gold set has almost no non-drop ground truth

The counted table now lives in [`issues.md`](issues.md) ("Texture hints missing
on three gold songs"): 12 non-drop hints in the whole gold set, 10 of them inside
the 58-second synthetic `_test_song`. This loose end stays here because the gap
still blocks the **CLAP character layer** entry above — its thresholds are
hand-set against those absent labels, and it does not disappear now that
`arrangement_state` has left the queue. One texture-marking session on
`Titanium` and `Hideaway` unblocks both.

### One sandbox image unblocks the two best open entries

ACE-Step Transcriber's only gap is timing — it emits ordered lines and `[tags]`
with no seconds — and the vocal-phrase entry's unbuilt Part B is forced
alignment. **These are the same missing forced-aligner image.** `transformers`
is absent from the `app` image and that image's `torchaudio` reports a CUDA
mismatch against `torch` (2.1.2+cu121 against a CUDA-11.8 build), so it needs a
new sandbox image on the `experiments/vocalparse` pattern. Building it once
turns the queue's highest-ceiling result into something measurable.

### Debugger lanes outlive their experiments

The UI-lane rule above says a lane is removed when its experiment is abandoned or
promoted. The two lanes stranded by the 2026-09-06 archive decisions —
`reactive_bands` and `grid_consensus` — were retired via Recipe B in git history.
The remaining `reference/proposals/` lanes are all wanted:

| lane | state |
| --- | --- |
| `vocal_transcription` | VocalParse archived, but **keep** — shared with the open ACE-Step entry |
| `character`, `vocal_phrases` | entries still open — keep |
| `drop_impacts` | see below |

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
