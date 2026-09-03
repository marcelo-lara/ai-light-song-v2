# Experiment — ACE-Step Transcriber for multilingual sung lyrics + structure

**Status: probed on 2 songs — strongly positive on lyrics + structure, timing
unsolved.** Full write-up in the queue entry:
[`../../docs/experiments_pending.md`](../../docs/experiments_pending.md)
(constitution §3.4). Nothing in `src/` reads anything here.

## Two-song probe result (CPU, thinker-only, bf16)

`Titanium - David Guetta ft Sia` — the song VocalParse turned into looping
Mandarin — came back as:

```
Intro → Verse 1 → Pre-Chorus → Chorus → Instrumental Break → Verse 2 →
Pre-Chorus → Chorus → Instrumental Break → Bridge → Chorus → Outro
```

with the chorus (*"You shoot me down, but I'm on fire / I am titanium"*) and
pre-chorus transcribed exactly, plus scene tags ("Synth lead melody over
driving beat") and backing vocals "(I am titanium)". `_test_song` was likewise
near-perfect. See `cache/*.acestep.json`.

**The gap: no timestamps.** The model emits ordered lines and `[tags]` with no
seconds. `align.py` anchors them to the whisper baseline's word timeline, but
that baseline is weak on CPU — the real fix is forced alignment of ACE-Step's
own transcript to the vocal stem, which is not built yet.

## The question

No lyric reaches the authoring model today, and a sung line is a cue (vocal
entry, title hook, a-cappella line, the last word before a drop). ACE-Step
Transcriber is the stronger of the two singing-transcription candidates for this
corpus — see the sibling [`../vocalparse/`](../vocalparse/README.md), which is
Mandarin-biased.

> Does ACE-Step transcribe this corpus's lyrics with usable timing, and is its
> **song-structure** output competitive with `allin1` and better than the
> incumbent segmentation?

## What ACE-Step Transcriber is

<https://huggingface.co/ACE-Step/acestep-transcriber> — a Qwen2.5-Omni-7B
fine-tune (~11B params, 22 GB weights) the ACE-Step team built as their own
training-data annotator. Speech + singing, 50+ languages. Prompted with
`"Transcribe this audio in detail"`, it returns:

    # Languages
    en

    # Lyrics
    [Intro - Acoustic Guitar]
    [Verse 1]
    <line>
    [Chorus]
    ...

— lyrics **and** section tags (`[Intro] [Verse] [Chorus] [Bridge] [Outro]`),
optionally naming the instruments per section. It does not emit reliable
per-line seconds; ACE-Step 1.5 generates LRC timing in a separate alignment
stage.

## Design

| step | module | what it does |
| --- | --- | --- |
| baseline | `whisper_baseline.py` | `whisper-large-v3`, `word_timestamps=True`, over the vocal stem — the lyric + timing floor to beat |
| model | `model.py` | ACE-Step on the **mix** (it uses the backing track for structure); raw text cached, parsed to `{languages, sections:[{tag, instruments, lines}]}` |
| align | `align.py` | monotonic text-similarity match of ACE-Step lines to Whisper line spans; `[Section]` spans derived from the lines they hold. Below 50 % line matches → `alignment: "unavailable"`, lines spread evenly with `approx: true` — flagged, never presented as measured (constitution §2) |
| export | `export.py` | writes the `ACE-Step …` and `whisper-…` rows into `reference/proposals/vocal_transcription.json` (shared with `../vocalparse`, keyed by model) |
| score | `score.py` | lyric WER vs `_test_song` Moises reference; `[Section]` boundary recall vs hand-marked drop impacts and vs `allin1` transitions, at ±1.0 s |

## How to run it

```bash
docker build -f experiments/drop_detection/research/Dockerfile.acestep \
             -t ai-light-song-v2-acestep:dev .

# whisper baseline (shared with experiments/vocalparse, cached at
# experiments/.whisper_baseline_cache/) — run with float32 for a usable anchor
WHISPER_COMPUTE=float32 ./experiments/acestep_transcriber/run_in_container.sh \
  python -m experiments.acestep_transcriber.run cache-baseline

# the transcriber itself
./experiments/acestep_transcriber/run_in_container.sh python -m experiments.acestep_transcriber.run cache
python -m experiments.acestep_transcriber.run export
python -m experiments.acestep_transcriber.run score
```

**Confirmed on the 2026-09 probe:** the checkpoint is
`Qwen2_5OmniForConditionalGeneration`; `model.py` loads the **thinker only**
(`Qwen2_5OmniThinkerForConditionalGeneration`, 8.9 B params, bf16) since the
talker and token2wav vocoder are not needed for transcription and don't fit.
Needs `torchvision` (Qwen2.5-Omni imports it even for audio-only) and
transformers ≥ 4.52. **No GPU path on the 4 GB dev box** — runs on CPU,
`ACESTEP_MAX_NEW_TOKENS` controls the cap (320 for a short song, ~1024 for a
full one; ~13 min and ~40 min respectively). There is **no native timestamped
decode** in this checkpoint — timing is `align.py`'s problem.

## Ground truth

`_test_song` `reference/moises/lyrics.json` for word-level lyrics (one song).
Structure is scored against the 7 hand-marked drop impacts across 4 songs and
against the `allin1` experiment's transitions — run that experiment's `export`
first if you want the structure comparison populated.

## Reach test

If promoted, the lyric side adds a top-level `lyrics.json` to the deliverable
contract (constitution §9) with an MCP handoff note. The structure side would
feed section *naming* rather than ship as its own file — it is a third form read
next to the incumbent and `allin1`, not a new deliverable.

## Results

_None yet._
