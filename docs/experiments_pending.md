
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
to the vocal stem** — not yet built.

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
