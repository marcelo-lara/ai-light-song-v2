# Experiments

One entry per experiment, carrying its plan, its measured results and its
conclusion. An entry leaves this file only when the operator picks **archive**
or **promote**. Promoted ones go to
[`archive/experiments_archive.md`](archive/experiments_archive.md), the rest to
the same [`archive/experiments_archive.md`](archive/experiments_archive.md)
index, discarded — which also holds entries stopped before they ever ran,
said so explicitly rather than implied as a result. Every entry is a TLDR: the
full writeup stays in `experiments/<topic>/README.md` where the experiment
lived.

[Loose ends](#loose-ends) at the foot of this file holds the open questions the
queue *depends* on but which are not themselves experiments.

`experiments/truth_common.vocal_presence/` is shared scaffolding, not an experiment: one
proposal schema and one scorer (frame voiceness accuracy, false-vocal rate,
boundary F1 @ ±0.25/0.5/1.0 s, bounds/min) against `type: "vocal"` human
hints, plus the three incumbents (`arrangement_state`, `vocal_phrases`,
mix-RMS baseline) every candidate is measured against. `vocal_voiceness`,
`clap_voiceness`, `svd_tagger` and `whisperx_vad` all import it directly —
check there before writing another scorer for the same metric.

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
[`archive/experiments.discarded.clap-section-identity.md`](archive/experiments.discarded.clap-section-identity.md).
This entry is the other
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

**Verdict (v3.6):** keep — 7/10 non-drop hints covered by a character block;
the calm-axis ablation is specific where stems alone are not (stems+CLAP 28
blocks / 241 s / 41% of corpus vs stems-alone 81 blocks / 973 s / 73%, both
find the reference block). Still blocked on ground truth, not on method.

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
([`archive/experiments.promoted.arrangement-state.md`](archive/experiments.promoted.arrangement-state.md)): this
experiment's `smooth_s: 2.0` / `min_block_s: 4.0` is why it
emits only three blocks on `_test_song` and misses the 16 s vocal entry, the
36.5 s `Spacer` and the whole outro structure. **The smoothing was the cost, not
the stems.**

---

## allin1's label posterior — the structure it already computes and throws away

<https://github.com/mir-aidj/all-in-one>

### Status

**[OPEN — run 2026-09-18. Item 1 turns out already shipped; item 2 is a
negative result.]** Built as `experiments/allin1_posterior/` (no README yet).
No UI lane yet — the entry's own reach test said item 1 needs none (a field
on `sections.json`, not a timeline claim), but item 2's shadow labels are
boundaries and do need one per the UI-lane rule; not built.

**Verdict:** the entropy-as-confidence idea (item 1) turns out to already be
shipped — `segmentation.py::_function_confidence_for_span` (`1 - mean
posterior entropy` per section) already backs `sections.json`'s
`function_confidence` field. This entry's "not yet run" status was stale.
Shadow labels (item 2) reproduce the `Armin` worked example closely but
**lose to a plain even-grid baseline on boundary recall on 3 of 4 gold
songs** — a negative result, not a promotion candidate as scoped.

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

Built as `experiments/allin1_posterior/`, reading the committed
`analyzer.allin1_cache` caches as data — no model run, plain `app` service.
Time-bearing output (shadow labels) goes to
`reference/proposals/allin1_posterior.json`; the debugger lane it needs per
the UI-lane rule is not yet built.

1. **Entropy as a real confidence.** Turned out to be moot — see Status.
   `segmentation.py::_function_confidence_for_span` already computes and
   publishes exactly this measure as `function_confidence`.
2. **Shadow labels.** Find spans where a non-argmax label holds a sustained
   share of the posterior, score their boundaries against `sections.json`
   (incumbent) and an even grid at matched boundary budget (baseline). Built
   and run.
3. **Reach test.** Unchanged from the original plan — no new file, entropy
   already lands on `sections.json`, shadow labels would land there too if
   promoted.

### Results evidence

`out/score.json` in `experiments/allin1_posterior/`, gold set, boundary
recall count (of `n_hint_boundaries`) at matched `bounds_per_min`:

| song | hint boundaries | shadow @0.1/0.25/0.5s | sections incumbent @0.1/0.25/0.5s | even-grid baseline @0.1/0.25/0.5s |
| --- | --- | --- | --- | --- |
| `_test_song` | 21 | 0/0/2 | 5/7/9 | 1/3/7 |
| `Hideaway - Kiesza` | 6 | 0/1/3 | 0/0/0 | 1/2/3 |
| `Armin - Revolution` | 28 | 5/7/8 | 8/11/13 | 6/7/8 |
| `Titanium - David Guetta ft Sia` | 18 | 0/2/6 | 0/0/0 | 1/2/4 |

Shadow labels lose to the even-grid baseline on `_test_song`, `Hideaway` and
`Armin`; only beats it on `Titanium` at ±0.5 s (6 vs 4). The `sections.json`
incumbent — a different comparison, boundaries it already has reason to place
well — still wins outright on `_test_song`/`Armin` and is empty on
`Hideaway`/`Titanium` (both `0/0/0`, the same songs `arrangement_state`
struggles on elsewhere in this file).

**Armin worked example reproduced closely:** detected `break` spans
144.31–155.53 s and 155.57–168.16 s (mean share 0.32-0.32) against the
original 143.4–175.0 s / 0.30 observation — both spans have zero overlap with
any published section (`published_overlap: 0.0`), confirming the argmax
genuinely discards this.

### Conclusion

**Item 1 needs no action — it shipped independently of this entry.** Item 2
is a **negative result**: shadow labels reproduce the interesting worked
example but do not clear a trivial even-grid baseline on boundary recall at
matched budget on 3 of 4 gold songs, so they are not ready to become a
published field. Not proposing promotion. If kept open, the UI lane for
shadow labels is the next concrete step, followed by a second look at
*why* the even-grid baseline wins — likely the same lesson as elsewhere in
this file: a naive high-firing-rate method wins recall at a matched budget
unless the signal is specific, and shadow-label share alone may not be.

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

**Verdict (v3.6):** keep — item 3's whisper_baseline word-onset timing IS
ACE-Step's onset score (it emits no seconds of its own). Rhythm (vs trusted
word-onset truth): `Queen of Kings` F1 0.14/0.26 @50/100ms (97 pred / 257
truth onsets), phrase-edge F1 0.35; `_test_song` F1 0.09/0.38 (23/24),
phrase-edge F1 0.55 — weak, and adds nothing beyond whisper_baseline for
rhythm. Presence (`Cinderella`, circularity-restricted to `false_vocal_rate`
only): 0.2224 — far worse than `arrangement_state` (0.0035) and
`vocal_voiceness` (0.0106), near the `mix_rms_baseline` floor (0.2568). Its
unique value stays lyrics + named structure-sequence (WER 0.23 vs baseline's
0.32 on `Titanium`); `Queen of Kings` whisper_baseline cache computed fresh
for this rescore (CPU faster-whisper, not the 8.9B ACE-Step model).

### Why? What for?

Same goal as [VocalParse](archive/experiments.discarded.vocalparse.md):
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

**[OPEN] — the decision path's own next step is now run, and it settles the
question in the detector's favor.** Part A concluded: the detector finds the
operator's vocal-phrase edges 5–6× better than the shipped `sections.json`.
Against `arrangement_state`'s vocal edges the standalone detector also wins
clearly (see prior verdict below). The one thing still open after that —
whether the win against mix-RMS was really about the stem gate, or just a
higher firing rate — is now measured too.

**Verdict (2026-09-18): the budget-matched ablation is run.** Sweeping the
mix-RMS threshold until its firing rate matches `vocal_phrases`'s ~50
bounds/min (aggregate 50.37 vs 50.53), `vocal_phrases` beats matched mix-RMS
at every tolerance on the 104-boundary gold set: **34/104 vs 24/104 @±0.1s,
59/104 vs 31/104 @±0.25s, 84/104 vs 36/104 @±0.5s.** The stem gate is doing
real work, not just firing more often — this closes the open question the
entry was scoped around. Only Part B (forced alignment, still unbuilt) stands
between this and a promotion discussion.

**Verdict (v3.6, still holds):** rescored against the current 104-boundary
hint set (4 gold songs): `vocal_phrases` recalls 34/104 @±0.1s, 59/104
@±0.25s, 84/104 @±0.5s (44.9 bounds/min) vs the shipped `arrangement_state`
vocal edges at 9/104, 15/104, 25/104 (6.9 bounds/min) — the standalone
detector wins clearly at every tolerance, so `arrangement_state` does not
match or beat it.

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

**Budget-matched ablation (2026-09-18), added to `score.py`.** Mix-RMS
threshold swept to `threshold_ratio=1.269`, matching `vocal_phrases`'s
aggregate 50.37 bounds/min (50.53 achieved):

| song | method | ±0.1s | ±0.25s | ±0.5s | bounds/min |
| --- | --- | --- | --- | --- | --- |
| `_test_song` | vocal_phrases | 10/26 | 16/26 | 21/26 | 23.74 |
| `_test_song` | mix-RMS matched | 12/26 | 13/26 | 14/26 | 41.29 |
| `Hideaway - Kiesza` | vocal_phrases | 2/10 | 2/10 | 8/10 | 55.07 |
| `Hideaway - Kiesza` | mix-RMS matched | 0/10 | 0/10 | 0/10 | 38.14 |
| `Armin - Revolution` | vocal_phrases | 15/38 | 27/38 | 31/38 | 56.29 |
| `Armin - Revolution` | mix-RMS matched | 4/38 | 5/38 | 6/38 | 45.15 |
| `Titanium` | vocal_phrases | 7/30 | 14/30 | 24/30 | 46.99 |
| `Titanium` | mix-RMS matched | 8/30 | 13/30 | 16/30 | 70.74 |
| **aggregate, 104 boundaries** | **vocal_phrases** | **34/104** | **59/104** | **84/104** | — |
| **aggregate, 104 boundaries** | **mix-RMS matched** | **24/104** | **31/104** | **36/104** | — |

`vocal_phrases` wins at every tolerance on every song except `_test_song`
@±0.1s and `Titanium` @±0.1s, where matched mix-RMS is marginally ahead
(12/26 vs 10/26; 8/30 vs 7/30) — both close, both reversed by ±0.25s. On
`Hideaway`, the dense-mix song where the unmatched comparison already showed
the stem gate earning its keep, matched mix-RMS finds **nothing** (0/10 at
every tolerance) while `vocal_phrases` still finds 8/10 at ±0.5s.

A `score.py` schema-drift bug was fixed alongside this: `_shipped_boundaries`
read `sections.json` as a bare list; it is now `{field_sources, sections}`
per the v3.6 publish-phase shape, and was silently returning zero incumbent
boundaries before the fix.

### Conclusion

The premise holds: the operator marks vocal edges, nothing in the pipeline
emits them, and a stem-gated hysteresis detector finds them far better than
the shipped segmentation does. The claim the entry rested on — that the
stem gate and hysteresis are doing real work, not just firing more often —
is now established: at a matched firing budget, `vocal_phrases` beats mix-RMS
at every tolerance in aggregate, decisively on the dense mixes. One thing
stands between this and a promotion discussion: Part B (forced alignment),
which is also the ACE-Step entry's blocker.

---

## Demucs variant ablation — `htdemucs` vs `htdemucs_ft` vs `htdemucs_6s`

*(no external model beyond the three Demucs checkpoints already used by `stems.py` — https://github.com/facebookresearch/demucs)*

### Status

**[OPEN — measured on all 5 scoring-corpus songs, still no clear winner].**
v3.5 item 3. Built as
[`../experiments/demucs_ablation/`](../experiments/demucs_ablation/README.md).
No UI lane — this item reports numbers only, no timeline claim.
`Hideaway - Kiesza` and `Armin - Revolution` — previously killed by the
harness for system memory pressure mid-run — finished 2026-09-18, run one
variant/song at a time. `src/analyzer/stages/stems.py` and
`DEMUCS_MODEL_NAME` are untouched — still pinned to `htdemucs`.

**Verdict (v3.6):** keep — no kill condition, still no clear winner, now
complete on all 5 songs. `ayuni` and `Armin` carry declared three-class
ground truth ([Vocal ground truth inventory](#vocal-ground-truth-inventory)),
so their `false_vocal_rate` is real, not the `voiced_duration_fraction` proxy:
`ayuni` htdemucs 0.1745, `htdemucs_ft` 0.2004, `htdemucs_6s` 0.2223 — `htdemucs`
wins (lowest false-vocal rate); `Armin` all three variants score **0.0000**
(its 7 vocal spans have no declared negatives, so nothing distinguishes them
here). `voiced_duration_fraction` (no ground truth, proxy only) on the
remaining three: `_test_song` 0.628/0.641/0.637, `Hideaway` 0.851/0.820/0.850,
`Titanium` 0.777/0.775/0.787 (htdemucs/ft/6s) — `htdemucs_6s` wins `Titanium`,
`htdemucs` wins `_test_song` and `Hideaway`. Mixed across songs and metrics;
still not a re-pin decision.

`experiments/demucs_ablation/score.py` had a schema-drift bug found and fixed
2026-09-18: it built the synthetic loudness doc in the pre-v3.6-item-8 nested
`metadata.source_order` shape, which silently broke every score against the
now-flat `source_order`/`interval_ms` production shape. `out/score.json` now
also hard-fails rather than silently proxying `false_vocal_rate` for a song
with no declared ground truth (`_test_song`/`Hideaway`/`Titanium` all raise —
their numbers above came from a direct call to the un-gated block function,
not the committed `score.json`, which now lists `ayuni`/`Armin` only).

### Why? What for?

Refinement doc question: how much of `ayuni`'s false vocal presence
(`arrangement_state.json` reports `vocals` 40.8 % of the song) is separation
error, how much is the self-normalisation the same doc describes.
`htdemucs_6s` adds `guitar`/`piano` sources that could pull melodic leakage
(a flute, here) out of `vocals`; `htdemucs_ft` is a fine-tuned `htdemucs`.
Cheapest measurement in the release — a model-pin swap, no new dependency —
and ordered first so items 4-7 build on a settled stem choice.

### Experiment Plan

`compute --song <name> --variant <htdemucs|htdemucs_ft|htdemucs_6s>` runs
Demucs separation with the model name overridden per-call, caching stems
under `experiments/demucs_ablation/cache/` (never
`data/analysis/*/artifacts/stems/`). `export` reuses
`analyzer.stages.arrangement_state.detect()`/`blocks()` **unmodified** — the
exact per-song-threshold + hold-gate rule live in production today — fed a
synthetic loudness doc built from the variant's own `vocals.wav` RMS series
instead of the published, `htdemucs`-only `loudness.json`.

**Ground truth gap found while building this.** Item 1 added the `type:
"vocal"` human-hint schema but explicitly left marking real spans to the
operator. Checked directly: every one of the four gold songs and `ayuni` has
**zero** `type == "vocal"` rows in this environment. So
`truth_common.vocal_presence.scorer.score()`'s `false_vocal_rate` against an empty
marked-span set is mathematically identical to "fraction of the song the
rule calls voiced" — reported below as `voiced_duration_fraction`, an honest
proxy for the false-vocal rate the plan specifies, not the validated metric.
Re-running `export` after the operator marks spans recomputes the real
number with no code change.

### Results evidence

Full detail and the `ayuni` 49.2 % vs shipped 40.8 % discrepancy note (loader/windowing variance, not a re-measurement of the shipped figure):
[`../experiments/demucs_ablation/README.md`](../experiments/demucs_ablation/README.md).

**`false_vocal_rate` — real, declared ground truth (`ayuni`, `Armin - Revolution` only):**

| song | htdemucs | htdemucs_ft | htdemucs_6s |
| --- | --- | --- | --- |
| `ayuni` | **0.1745** | 0.2004 | 0.2223 |
| `Armin - Revolution` | 0.0000 | 0.0000 | 0.0000 |

`Armin` has 7 declared positive spans and zero declared negatives, so every
variant scores 0 — the metric has nothing to discriminate on there yet.

**`voiced_duration_fraction` (proxy — no declared ground truth for these three):**

| song | htdemucs | htdemucs_ft | htdemucs_6s |
| --- | --- | --- | --- |
| `_test_song` | **0.628** | 0.641 | 0.637 |
| `Hideaway - Kiesza` | **0.851** | 0.820 | 0.850 |
| `Titanium - David Guetta ft Sia` | 0.777 | 0.775 | **0.787** |

All three checkpoints fetched successfully in this environment (`htdemucs_ft`
and `htdemucs_6s` via Demucs's own HuggingFace-hub fallback, no local
mirror). `Hideaway`/`Armin` finished 2026-09-18 by running one variant/song
at a time rather than batching — the earlier OOM was a batching problem, not
a checkpoint-availability one.

### Conclusion

No kill condition (none specified for this item) and no clear winner now
that all 5 scoring-corpus songs are measured. `htdemucs` wins on
`false_vocal_rate` (`ayuni`, the only song where the variants actually
differ) and on two of the three proxy songs (`_test_song`, `Hideaway`);
`htdemucs_6s` wins the proxy on `Titanium`; `Armin`'s metric is uninformative
until it gets declared negative spans. This stays a **measured
recommendation against `htdemucs` re-pinning, not a case for it**:
`htdemucs_6s` was the entry's working hypothesis (it adds `guitar`/`piano`
sources that could pull melodic leakage out of `vocals`) and it does not win
on the metric that actually has ground truth. Re-pinning `DEMUCS_MODEL_NAME`
is not proposed — per the promotion gate a re-pin is a separate,
explicitly-asked-for decision because it invalidates every cached stem in the
corpus, and the one real number here argues against it anyway. Getting
`Armin` (and ideally `_test_song`/`Hideaway`/`Titanium`) declared negative
spans is the only thing that would make this measurement complete.

---

## The vocal cue set — what each cue answers, and what breaks it

Cross-cutting result of items 4-7 plus the voice-multiplicity entry. No single
cue answers more than one question, and **every one of them is a per-song
quantity**.

| question | cue | best evidence | breaks on |
| --- | --- | --- | --- |
| is this a voice at all? | sibilance | AUC 0.813-0.990, 3 songs | near-silence (floor ~0.13); chatter |
| where are the phrases? | whisperX @ ~0.2 | 4 labelled songs | filtered/held vocals at 0.5; chatter |
| one voice or many? | stereo width + L/R corr | AUC 0.951, 1 song | diffuse chatter reads as stacked |
| male or female? | f0 height, within-song | AUC 0.802, 1 song | pYIN octave errors; rap; silence |
| lead or chatter? | `whisperX - pitch-lock` | 1 song, unlabelled | untested |

### Everything derived from a produced vocal stem is per-song

Three independent instances. Treat it as the default assumption rather than
rediscovering it:

- CLAP needed two centrings before its differential meant anything.
- Stereo width needed per-song z-scoring — which is exactly why `Born Slippy`
  did not false-positive.
- f0 has no cross-song absolute scale. A single female lead reads median
  **523.3 Hz** on `Hideaway` and **392.0 Hz** on `Titanium`: pYIN is
  systematically tracking harmonics, not fundamentals, on this corpus. The
  male/female contrast survives only *within* a recording (`Armin`: male
  185 Hz vs female 372 Hz, AUC 0.802), and **octave-folding destroys it**
  (AUC 0.358) — the discrimination lives entirely in absolute octave position,
  so pYIN's octave errors are directly damaging. A formant or spectral-centroid
  cue would likely be more robust, having no octave to get wrong.

### f0 and sibilance both need a level gate

pYIN hallucinates pitch on silence: the 184-208 s tail of
`What a Feeling - Courtney Storm` sits at level 0.0001 yet reports pitch-lock
0.32-0.46 at ~400 Hz. Sibilance reads 0.129 on that same silence. Neither is
usable as a presence gate on its own.

### Chatter — the failure that is also the cue

`whisperx_vad` is a speech VAD: it fires on chatter and goes quiet on singing.
Pitch-lock does the opposite. On `What a Feeling - Courtney Storm` the
difference separates them with no overlap — `whisperX - pitch-lock` runs
+0.27…+0.53 across the spoken opening and -0.65…-0.79 on the sung passages.

**Unverified.** That song carries no hints. The predictions awaiting the
operator's ear: 0-32 s is chatter; 48-56 s and 128-152 s are sung lead.

---

## Vocal ground truth inventory

What can actually be scored. This **supersedes** the "no song in this
environment carries `type: "vocal"` ground truth" claim repeated in items 3-7.

| song | source | content |
| --- | --- | --- |
| `ayuni` | `human_hints.json` | 7 `type: "vocal"` spans (32.0 s), explicit "no vocals" negatives (102.6 s), 2 residual-vocal spans (29.4 s). **Exhaustive** — 0.7 s of the 164.8 s is unmarked |
| `Cinderella - Ella Lee` | `human_hints.json` | v3.5 item 12 re-mark: 22 `type: "vocal"` spans (167.3 s), 5 hard negatives (72.1 s, instrument leaked into the vocal stem), 3 `unknown` (7.1 s). No longer sparse: 93.0 s of the 339.5 s is unmarked. **Circular positives**: 15 of the 22 positive spans were captured from `whisperx_vad`'s own lane (`captured_from` field) — whisperX's recall/F1 on `Cinderella` is not an independent measurement; only `false_vocal_rate` on the 5 operator-marked negatives compares fairly |
| `Armin - Revolution` | `human_hints.json` | 7 `type: "vocal"` spans (35.3 s); male 30.0-55.8 s, female 81.6-88.0 s. No "no vocals" hints — unlabelled time is **not** confirmed instrumental, so its FP column is an upper bound |
| `Queen of Kings - Alessandra` | `reference/human/lyrics.json` | trusted word timings, 257 words / 37 lines, 1.0-142.9 s — **whole song**, superseding the earlier `reference/moises/lyrics.json` 0-127.2 s trust window |
| `_test_song` | `reference/moises/lyrics.json` | curated, 24 words / 5 lines, 15.9-54.7 s; 36 s of real instrumental including deliberate traps (an acid-synth-bass block, an ambient pad between two vocal lines) |
| `In da name of love - Anita and Ray` | `human_hints.json` | 11 hints, 10 of them `type: "vocal"`; 1 residual (hint-008, a vocal loop). **No hard negatives** — unmarked time is not confirmed instrumental. Classified 2026-09-13; also the corpus's only declared 2-singer song |
| `What a Feeling - Courtney Storm` | `human_hints.json` | 2 hints only — 1 `type: "vocal"`, 1 residual (hint-002, sampled chatter). Very sparse; useful for the residual firing rate, not for recall |

### Ground truth is three classes, not two

Positives are `type: "vocal"` spans. Hints whose text describes an
inferable-but-not-lead vocal ("FILTERED VOCALS…", "(filtered) Vocal as loop")
are **neither credit nor error** — exclude them and report their firing rate
separately as a diagnostic. "No vocals" hints are hard negatives, and that
includes **"vocal stem noise"**, which means instrument bleed with *no voice at
all*.

Scoring the residual class as negatives moves the numbers materially: on
`ayuni` those spans are 29.4 s against 32.0 s of true vocal, and correcting the
error raised whisperX's F1 from 0.822 to 0.919. Those two figures were measured
against the earlier 28.0 s marking (5 spans); the operator has since added two
~2 s vocal spans, and `scorer.py` has since been rewritten to the three-class
contract (residual excluded, unreviewed time excluded, `frame_accuracy` /
`false_vocal_rate` / `bounds_per_min` denominators all narrowed to the evaluable
region). **Rescored 2026-09-13** on the three-class scorer and the 5 declared
songs: whisperX `ayuni` frame_acc 0.9881 / false_vocal 0.0056, residual firing
0.24 — the per-item tables above carry the current numbers. Only `ayuni` and
`Cinderella` declare negatives; `Armin` and `In da name of love` declare none
and `What a Feeling` has 2 s evaluable, so a 5-song mean rewards an always-on
detector and must not be quoted.

### A level gate cannot separate the leak — and the shipped threshold is already optimal

Measured 2026-09-12 on the vocal stem (`artifacts/stems/vocals.wav`, 50 ms
frames, mono sum), classified by the three-class ground truth above. This
settles the recurring "remove anything below X dB" proposal. **Predates the
item-12 `Cinderella` class-map repair** (4 pos / 4 neg spans at measurement
time, now 22 pos / 5 neg) — not re-measured here; only the stale hint id below
is corrected.

| | `ayuni` | `Cinderella - Ella Lee` |
| --- | --- | --- |
| vocal-stem dBFS median — positive / residual / negative | -24.7 / -31.2 / **-69.3** | -24.0 / — / **-69.6** |
| level-only AUC, positive vs negative | 0.960 | 0.968 |
| best single threshold (oracle) | **-38.1 dB** | -35.3 dB |
| balanced accuracy at that threshold | 0.927 | 0.895 |
| `arrangement_state`'s own threshold (p98 - 18 dB) | **-38.2 dB** | -31.5 dB |

**On `ayuni` the shipped per-song rule already sits 0.1 dB from the best single
threshold that exists.** There is no threshold left to find: 0.927 balanced
accuracy is the *ceiling* for any level rule on that song, and the rule reaching
it still calls 40.2 % of frames voiced (the shipped 40.8 % figure).

Where a gate fails, per hint, as % of frames above the oracle threshold:

| hint | class | % above gate | max dBFS | note |
| --- | --- | --- | --- | --- |
| `ayuni` hint-009 "Vocal Stem noise" | negative | **54.6 %** | **-14.8** | the flute leak — louder than hint-008 (-27.7 median) and hint-017 (-28.9), both true vocal |
| `ayuni` hint-013 "Tension break" | negative | 51.9 % | -24.0 | "close to zero sound" by ear, -37.5 median in the stem |
| `Cinderella` hint-007 "Plucked guitar" | negative | 38.5 % | -28.3 | overlaps hint-001's vocal median (-29.3) |
| `Cinderella` hint-001 "Cinderella sample" | positive | 71.5 % | -13.5 | so a gate also **silences 28.5 % of a real vocal** |

Two things follow, and they point in opposite directions:

- **No gate, at any level, separates an audible leak from a voice.** The loud
  tail of the negative class overlaps the quiet half of the positive class on
  both songs. whisperX reports 0.00 on `ayuni`'s flute span, so timbre already
  solves what level provably cannot.
- **An absolute floor is still worth publishing** — not as a stem rewrite (the
  stem is never rewritten) but as a cheap "is there audible content in this stem
  at all" precondition. 9 of the 13 negative spans sit at -60…-78 dB, i.e. most
  negative *time* is sub-audible bleed, and the two songs' oracle thresholds
  differ by only 2.8 dB against a per-song rule whose own docstring says nothing
  transfers between songs.

### v3.5 item 12 fusion sweep — the rule item 13 must decide on

Measured 2026-09-13 against the repaired `Cinderella` class map, on the 50 ms
grid, via `truth_common.vocal_presence.scorer` (throwaway script, not committed).
frame_acc / false_vocal_rate / residual firing / recall on positives /
bounds-per-min:

| rule | `ayuni` | `Cinderella` |
| --- | --- | --- |
| `whisperX >= 0.5` | 0.9881 / 0.0056 / 0.24 / 0.974 / 5.12 | 0.8614 / 0.0290 / 0.00 / 0.843 / 15.54 |
| `whisperX >= 0.2 AND stem >= -38 dBFS` | 0.9814 / 0.0089 / 0.39 / 0.960 / 30.36 | **0.8887 / 0.0265** / 0.00 / 0.879 / 39.10 |
| `whisperX >= 0.2 AND sibilance >= 0.20` | 0.9759 / 0.0063 / 0.13 / 0.925 / 20.48 | 0.8355 / 0.0134 / 0.00 / 0.784 / 47.62 |
| `whisperX >= 0.5 OR (whisperX >= 0.10 AND sibilance >= 0.20)` | 0.9558 / 0.0393 / 0.41 / 0.980 / 21.22 | 0.8791 / 0.0365 / 0.00 / 0.879 / 20.30 |
| `arrangement_state` incumbent (`vocals` channel) | 0.9042 / 0.0891 / 0.82 / 0.972 / 6.58 | 0.9342 / 0.0035 / 0.00 / 0.911 / 6.52 |

Sibilance read off `experiments/vocal_voiceness/features.py::compute_sibilance`'s
cached 50 ms series — the formula `src/analyzer/stages/ui_data.py::_sibilance_curve`
ported verbatim at promotion, so this is the series `src/` actually publishes
(per-phrase mean only there; this sweep needs the full frame series). Vocal-stem
dBFS: mono sum of `artifacts/stems/vocals.wav`, 50 ms RMS frames.

**`whisperX >= 0.2 AND stem >= -38 dBFS` wins `Cinderella` outright** (best
frame_acc and false_vocal_rate of the four whisperX-based rules) while costing
`ayuni` only 0.007 frame_acc against plain `whisperX >= 0.5`. No rule beats the
`arrangement_state` incumbent's false_vocal_rate on `Cinderella` (0.0035) — its
6.52 bounds/min budget is far lower, so the comparison is not apples-to-apples.
**`Cinderella`'s recall/F1-shaped numbers above are circular** for whisperX-based
rules: ~15 of 22 positive spans were captured from `whisperx_vad`'s own lane
(`captured_from` in `human_hints.json`). `false_vocal_rate` (measured only
against the operator's own 5 negative spans) is the fair comparison; recall and
frame_acc are reported for completeness, not as independent evidence.

### `confidence: "0.99"` marks curation only when the whole file carries it

`Queen of Kings` (all 235 rows) and `_test_song` qualify. `Hideaway - Kiesza`
spreads continuously 0.05-0.99 with median 0.54 — there 0.99 is simply Moises
being confident, and those rows are **not** ground truth. Test the file's
distribution, not the row.

Hideaway also shows how bad the raw inference gets, which is why unmarked
Moises rows are a comparison baseline and never a label: `'let'` spans
**29.33 s** at its own confidence 0.93, six words exceed 5 s, and coverage is
49% of the song. Beating it there is a real but low bar — `vocal_voiceness` and
`whisperx_vad` both do.

---

## Loose ends

Open questions this queue depends on that are **not themselves experiments**.
They are recorded here rather than acted on, because each is a decision, not a
task.

### The gold set has almost no non-drop ground truth

**Resolved (v3.6 item 2 corpus, checked 2026-09-14).** The texture/character
family now scores against untyped, non-drop hints on four songs: `Queen of
Kings` 16, `ayuni` 11, `Cinderella` 8, `_test_song` 8 — see
`docs/product-refinement-v3.6.md` section 2's corpus table. This is the
current corpus for the **CLAP character layer** entry and any other
texture/character candidate; `issues.md`'s older "Texture hints missing"
count predates this marking pass.

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
| `drop_impacts` | **retired v3.6 item 7** — see below |
| `vocal_voiceness`, `svd_tagger` | **retired 2026-09-17** — see below |
| `phrase_periodicity`, `voice_multiplicity` | **retired 2026-09-17** — see below |

### `phrase_periodicity` and `voice_multiplicity` lanes — retired

**Archived 2026-09-17.** Neither was a negative result — `phrase_periodicity`
passed its own kill condition (bar-sequence autocorrelation separated the two
known-8-bar songs from the rest) and `voice_multiplicity` scored AUC 0.951 on
`Queen of Kings` — but neither cleared the bar for promotion into `src/`.
`phrase_periodicity` classifies block *character* (through-composed / bar-loop
/ half-bar), not a top-level field the MCP contract projects, and its own
known limit (needs ≥ 2 bars per block) rules out sub-second cues.
`voice_multiplicity` stayed data-starved: only `Queen of Kings` in the whole
corpus carries `voices` labels, so the one positive score never became
corpus-wide evidence. Full TLDRs in
[`archive/experiments.discarded.phrase-periodicity.md`](archive/experiments.discarded.phrase-periodicity.md)
and
[`archive/experiments.discarded.voice-multiplicity.md`](archive/experiments.discarded.voice-multiplicity.md).
The `3. Phrase Periodicity` and `Voice Multiplicity` debugger lanes were removed
via Recipe B; `experiments/phrase_periodicity/` and
`experiments/voice_multiplicity/` stay in the tree as the record.

### `vocal_voiceness` and `svd_tagger` lanes — retired

**Archived 2026-09-17.** Both were voiceness-presence candidates in the same
family as `whisperx_vad`, which beats both on every song measured (frame_acc
`ayuni`/`Cinderella` 0.9881/0.8614 vs `vocal_voiceness` 0.8708/0.5480 and
`svd_tagger`'s best per-song rescale 0.8538/0.5125) at far lower cost —
`svd_tagger` alone needed its own sandbox image and a 327 MB model pin.
Full TLDRs in
[`archive/experiments.discarded.vocal-voiceness.md`](archive/experiments.discarded.vocal-voiceness.md)
and
[`archive/experiments.discarded.svd-tagger.md`](archive/experiments.discarded.svd-tagger.md).
**Sibilance is unaffected** — `vocal_voiceness`'s one measured-strong cue was
already promoted into `src/` (`vocals_phrase[].sibilance`,
`arrangement_state.json`) and stays there; only the rest of that entry (the
noisy-OR voiceness curve, vibrato/portamento) and all of `svd_tagger` are
archived. The `4. Vocal Voiceness` and `6. SVD Tagger` debugger lanes were
removed via Recipe B; `experiments/vocal_voiceness/` and
`experiments/svd_tagger/` stay in the tree as the record (`truth_common`'s
shared scorer still imports fine with both gone).

### `drop_impacts` orphan lane — retired

**Settled 2026-09-14 (v3.6 item 3 rescore, retired item 7).**
`experiments/drop_detection/` never had a queue entry, and its candidate
proposals lose to the shipped `gestures.py` stage on the drop-stage family
(see `docs/archive/experiments.discarded.drop-proposals.md`). The
`dropProposals` debugger lane was removed via
Recipe B; `experiments/drop_detection/` stays in the tree as a cache other
experiments still read, and its `reference/proposals/drop_impacts.json`
output is unaffected — only the lane and its own `reference/proposals/
{clap_voiceness,reactive_bands,grid,gestures}.json` inputs (item 4's
"no reader" list) were removed.
