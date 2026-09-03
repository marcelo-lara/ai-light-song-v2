# Experiment — VocalParse for sung lyrics with timing (and vocal melody)

**Status: concluded, negative.** VocalParse hallucinates Mandarin on real
non-Mandarin vocals and its melody head collapses on every song. Not usable for
this corpus. Full write-up in the queue entry:
[`../../docs/experiments_pending.md`](../../docs/experiments_pending.md)
(constitution §3.4). Nothing in `src/` reads anything here.

## Result (CPU run, four gold songs, vs. `reference/moises/lyrics.json`)

| song | VocalParse lyric WER | whisper baseline WER (float32, VAD off) |
| --- | --- | --- |
| `_test_song` (synthetic) | 0.12 | **0.04** |
| `Titanium` | 1.00 (hallucinated Chinese) | 0.32 |
| `Hideaway` | 1.00 ("ah ah ah…") | 0.97 (hallucinated captions) |
| `Armin - Revolution` | 1.00 | 0.99 (hallucinated captions) |

`melody_status` is `degenerate`/`empty` on 4/4 — the interleaved `<P_#>` span
collapses to repeated `<P_0>` then junk tokens. The only usable output is the
`<asr_text>` lyric prefix, and only on the one synthetic English track. See
[`out/score.txt`](out/score.txt) and the per-song `cache/*.vocalparse.json`.

## The question

No lyric reaches the authoring model today. A sung line is a cue — the vocal
entry after an instrumental stretch, the title hook, an a-cappella line, the
last word before a drop. The operator already marks these by hand
(`_test_song`: three `Vocal outro` phrases, a `Finale`; `Armin - Revolution`:
the "Breath" block).

> Can VocalParse transcribe this corpus's lyrics with usable word timing, and
> does its **vocal melody** output (MIDI pitch per syllable) add a signal the
> pipeline does not already have?

## What VocalParse is

<https://huggingface.co/pymaster/VocalParse> — a Qwen3-ASR-1.7B fine-tune for
singing-voice transcription. Input: 16 kHz mono. Output: an interleaved token
stream, `感 <P_68> <NOTE_4> 受 <P_60> … <BPM_89>`, lyric tokens spliced with
pitch (`<P_#>`, MIDI), note value (`<NOTE_#>`, log2 of a whole note), and one
global tempo token.

Two limitations that shape the experiment:

- **No timestamps.** The model emits note *values* and a global BPM, not
  onsets in seconds.
- **Mandarin-biased.** Trained "primarily on Mandarin Chinese singing"; this
  corpus is almost all English and European. A poor lyric result is a plausible,
  reportable outcome — in which case the melody signal is what is on trial.

## Design (from LyricWhiz, 2306.17103)

LyricWhiz's lesson: Whisper is a strong *ear* for sung lyrics once it is fed
isolated voice and prompted toward transcription. We already have the vocal
stem, so:

| step | module | what it does |
| --- | --- | --- |
| baseline | `whisper_baseline.py` | `whisper-large-v3`, `word_timestamps=True`, prompt `"lyrics:"`, over `artifacts/stems/vocals.wav` — lyric lines with per-word onsets in seconds |
| model | `model.py` | VocalParse on the same stem; raw string cached, parsed to `{lyrics, syllables:[{text,midi,note_value}], bpm}` |
| align | `align.py` | VocalParse has no clock — its syllables are spread over the Whisper word timeline by sequence position. If VocalParse's text and Whisper's disagree (language mismatch, garbage), the row is marked `alignment: "span"` / `"unavailable"` and carries **no per-word times** (constitution §2 — no invented onsets) |
| export | `export.py` | writes the `VocalParse …` and `whisper-…` rows into `reference/proposals/vocal_transcription.json` (shared with `../acestep_transcriber`, keyed by model) |
| score | `score.py` | lyric WER + word-onset MAE against `_test_song`'s `reference/moises/lyrics.json` |

## How to run it

```bash
docker build -f experiments/drop_detection/research/Dockerfile.vocalparse \
             -t ai-light-song-v2-vocalparse:dev .

./experiments/vocalparse/run_in_container.sh python -m experiments.vocalparse.run cache-baseline
./experiments/vocalparse/run_in_container.sh python -m experiments.vocalparse.run cache
python -m experiments.vocalparse.run export
python -m experiments.vocalparse.run score
```

`model.py` downloads the checkpoint with `snapshot_download` (VocalParse's
`load_model` wants a local dir, not a repo id) and lets it resolve the
Qwen3-ASR-1.7B base model. Runs on CPU (`VOCALPARSE_DEVICE=cpu`, baked into the
image) — the 1.7B model does not fit this box's 4 GB card.

## Ground truth

`reference/moises/lyrics.json` — word-level Moises transcripts, present for all
four gold songs (`_test_song`, `Titanium`, `Hideaway`, `Armin - Revolution`).
Corpus-wide quality beyond those is judged by ear in the **Vocal Transcription**
lane (rendered directly before **allin1 Sections**).

## Reach test

If promoted: a top-level `lyrics.json` joins the deliverable contract
(constitution §9) with a handoff note to the MCP server, projected next to
`hints.json` in the section read. Melody, if it survives, is a second field on
each line. Nothing here ships until then.

