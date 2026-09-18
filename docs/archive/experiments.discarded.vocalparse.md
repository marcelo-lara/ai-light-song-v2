# VocalParse — singing voice transcription (lyrics + melody)

[← archive index](experiments_archive.md)

<https://huggingface.co/pymaster/VocalParse>

**Archived** 2026-09-06 — ran, measured, negative. Nothing reached the reach
test; `lyrics.json` was never proposed.

**The claim.** Singing-voice transcription giving lyrics *and* melody — the one
thing the pipeline has no source for.

**The result.** Run on CPU over the four gold songs. Three came back as
**hallucinated Mandarin** on non-Mandarin vocals; the one success is the
synthetic `_test_song`. The melody head — the part that would have been novel —
collapsed on every song.

**Worth not rediscovering.** It is not a tuning problem: this needs a model
trained on Western pop, on a GPU. If singing-voice melody is wanted again, start
there rather than here.

**Still in use, and deliberately not retired with this entry:** the
`reference/proposals/vocal_transcription.json` schema and the **Vocal
Transcription** debugger lane, both shared with the open ACE-Step entry. The
`whisper-large-v3`-on-the-vocal-stem baseline also survives as the standing
lyric-timing candidate if a GPU box appears.

**Detail:** [`experiments/vocalparse/README.md`](../../experiments/vocalparse/README.md)
