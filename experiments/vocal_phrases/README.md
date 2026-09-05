# Experiment — Vocal phrase blocks

**Status: measured, PART A only, not promoted.** Nothing in `src/` reads
anything in here. Queue entry, with the same numbers in summary form:
[`../../docs/experiments.md`](../../docs/experiments.md)
(docs/experiments.md).

## The question

Auditing every operator hint boundary in the gold set against the onset and
offset of every sung line in `reference/moises/lyrics.json` (rebuilt with
genuine word-level timing on `_test_song`, 2026-09-04) found the operator
marking vocal-phrase edges at up to **11× chance**. The whole `_test_song`
outro — four consecutive hints with four distinct fixture behaviours — is
exactly the vocal-activity timeline; `hint-009` "Synth Pad" is defined by
nothing but the *absence* of voice, and the `hint-010`/`hint-011` split is a
0.63 s breath inside a single sung line. Nothing in the pipeline emits this.

> Can a vocal-activity detector over the trusted vocal stem — no model, local
> auto-gain, a breath split, a sustained-note pass — find these edges better
> than the shipped `sections.json` and a naive mix-RMS threshold?

Two halves were planned: **A**, the detector (this run); **B**, forced
alignment of a transcript to real per-word onsets (not run — see *What's not
done* below).

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.vocal_phrases.run detect
docker compose run --rm --no-deps app python -m experiments.vocal_phrases.run export
docker compose run --rm --no-deps app python -m experiments.vocal_phrases.run score
```

`detect` reads `artifacts/stems/vocals.wav`, computes a local-auto-gain RMS
envelope (2 s running mean, hysteresis on/off ratio 1.4/0.9) plus a pYIN pitch
track, and caches both. `export` derives `vocal_phrase` / `instrumental_gap` /
`sustained_note` blocks and writes
`reference/proposals/vocal_phrases.json`. `score` reproduces
[`out/score.txt`](out/score.txt).

## Results

Full tables in [`out/score.txt`](out/score.txt). Gold set, 94 hint boundaries.

| method | ±0.1s | ±0.25s | ±0.5s | bounds/min |
| --- | --- | --- | --- | --- |
| **vocal_phrases** | **28/94** | **42/94** | **66/94** | 44.9 |
| shipped `sections.json` (incumbent) | 5/94 | 5/94 | 10/94 | 3.6 |
| mix-RMS threshold (cheap baseline) | 25/94 | 37/94 | 51/94 | 61.2 |

**Clearly beats the incumbent** — 5-6× the recall at every tolerance. **Does
not clearly beat the cheap baseline** once its higher firing rate is
accounted for: the mix-RMS threshold fires 61 times/min against
vocal_phrases' 44.9, so at ±0.1s it edges vocal_phrases out (25 vs 28 — close)
and the gap only opens up at looser tolerances. This is an honest,
non-triumphant result: a stem-gated hysteresis detector is not yet proven to
beat a naive threshold at a matched firing budget. A budget-matched
comparison (see the `reactive_bands` sibling experiment, which caught the
same class of issue) is the natural next check before promotion is even
discussed.

**breath_s sweep** (on `_test_song`, the one song with trustworthy word-level
offsets): onset MAE is flat at 0.022 s across every breath threshold tried
(0.3-1.0 s) — the detector finds where a phrase *starts* reliably regardless
of the breath setting. Offset MAE degrades slightly, 0.145s at 0.3s to
0.164s at 0.5-1.0s, as looser breath thresholds merge more trailing
reverb/decay into the phrase. 0.5s (the shipped default) is a reasonable
middle point, not a clear winner — a smaller breath threshold trades a few
more (correctly split) phrases for a tighter offset.

**A real, documented limitation:** `sustained_notes` came back empty on
`_test_song`, where the manual audit (see `docs/experiments.md`)
notes a note held for 2.78 s straight through the drop build. Root cause,
confirmed by inspection: the held note's own natural amplitude decay dips
below the hysteresis OFF threshold mid-note, splitting the phrase — and
therefore the sustain scan, which only looks *within* one merged phrase span
— in two before either half reaches the 1.5 s minimum. Bridging on pitch
continuity through a low-energy dip (not built) would fix this; it is a
genuine gap in the current detector, not a tuning issue.

## What's not done

**Part B — forced alignment.** The plan calls for aligning ACE-Step
Transcriber's transcript to the vocal stem (whisperX / wav2vec2 CTC forced
alignment), which would (1) give real per-word onsets on the three gold songs
where Moises currently lumps a line's last word across the following
instrumental, and (2) solve the ACE-Step Transcriber entry's one open
problem. Not built: `transformers` is not installed in the `app` image and
`torchaudio` in that image reports a CUDA-version mismatch with `torch`
(2.1.2+cu121 vs a CUDA-11.8 torchaudio build), so this needs a new sandbox
image, matching the pattern of `experiments/vocalparse` and
`experiments/acestep_transcriber`. Scoped but not attempted in this run.

## Reach test

If promoted: `vocal_phrase` / `instrumental_gap` / `sustained_note` become
events in `song_event_timeline.json`, which is already projected. Nothing
joins the top-level contract. Given the unresolved baseline comparison above
and Part B being unbuilt, this is **not ready to promote** — the honest next
steps are a budget-matched ablation against the mix-RMS baseline, and Part B.
