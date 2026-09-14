# Archive — discarded experiments

Things that were tried and did not earn a place in the pipeline, plus two that
were dropped before they ran. Nothing here is a live proposal.

**These are TLDRs.** Each entry keeps the number that decided it and the finding
worth not rediscovering, and nothing else. Where an `experiments/<topic>/`
directory survives it holds the full writeup and the raw tables; where it does
not, git history is the archive.

**A dropped un-run entry has no evidence behind it and must never be cited as
one.** It records a scoping decision, not a measurement.

Promoted experiments: [`experiments_promoted.md`](experiments_promoted.md).
Still open: [`../experiments.md`](../experiments.md).

| experiment | verdict | what decided it |
| --- | --- | --- |
| CLAP — section identity | ran, negative | MFCC-20 **0.73** AUC vs CLAP **0.68** |
| VocalParse | ran, negative | 3 of 4 gold songs hallucinated as Mandarin |
| Reactive band dynamics | ran, negative | at matched budget, incumbent **7/7** vs **4/7** @±0.5 s |
| Bar grid by consensus | ran, negative | consensus **3/7**, allin1 alone **4/7** |
| Section identity embedding | dropped un-run | reopens a closed negative; 0.73 is the bar |
| Music Flamingo | dropped un-run | non-commercial licence blocks promotion |
| Singer Identity | ran, negative | singer count **4/9** on declared songs; voiceness below whisperX on `Cinderella` |

---

## CLAP — section identity

<https://github.com/LAION-AI/CLAP>

**Archived** — ran, measured, negative. Nothing was promoted for identity.

This was half of one experiment. The other half — a **character/texture layer**
— is a different question, measured positive, and is still open in
[`../experiments.md`](../experiments.md).

**The claim.** Can a CLAP embedding say which sections are the same part
returning, where `sections/form.py`'s `repetition_group` shipped `null` on every
section of all 21 songs?

**The result.** Mean pairwise AUC at matching two occurrences of the same
section:

| MFCC-20 | CLAP raw | chroma | CLAP centred | duration control | time control |
| --- | --- | --- | --- | --- | --- |
| **0.73** | 0.68 | 0.62 | 0.61 | 0.59 | 0.46 |

Twenty MFCC coefficients beat a 512-dimensional CLAP embedding.

**Worth not rediscovering.** CLAP scores 0.83 at telling a section from *itself*
and 0.68 at matching two occurrences of the same part. That gap is the diagnosis:
identity needs a representation trained for **invariance between occurrences**,
not a bigger general-purpose embedding. **MFCC's 0.73 is the number any next
attempt must beat** — and this is the standing example of why every experiment
here measures against a cheap classical baseline.

**Detail:** [`experiments/clap/README.md`](../../experiments/clap/README.md)

---

## VocalParse — singing voice transcription (lyrics + melody)

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

---

## Reactive band dynamics — local auto-gain instead of whole-song percentiles

<https://www.geisswerks.com/milkdrop/milkdrop_preset_authoring.html>

**Archived** 2026-09-06 — ran, measured, negative on its own hypothesis.

**The claim.** MilkDrop normalises band energy against a local running mean
rather than whole-song percentiles. That should track a song's own dynamics
better than the incumbent's fixed percentile scaling.

**The result.** Budget-matched at ~29 accents/min, gold set, 7 drop impacts:

| normalisation | ±0.25 s | ±0.5 s | ±1.0 s |
| --- | --- | --- | --- |
| local running mean (2 s) | 2/7 | 4/7 | 5/7 |
| **whole-song percentile (incumbent)** | **5/7** | **7/7** | **7/7** |

**The incumbent wins outright — the opposite of the hypothesis.**

**Worth not rediscovering, and this is the real deliverable of the entry:** the
first pass applied the same *absolute* threshold to both curves and looked like a
strong positive. It was not a comparison. The local ratio is unbounded
(`power / running_mean`, spiking past 10) while the percentile ratio is clipped
to `[0, 2]` by construction, so any shared cutoff silenced the incumbent whatever
its quality. **Two curves on different scales cannot share a threshold.** Fixing
that inverted the result.

**Archived refuted on one claim and untested on the other.** The dense per-beat
stream was the intended deliverable and was never measured separately. Reopening
this means measuring that stream — not re-running the accent ablation. Note also
that the export ran 0.43–1.8 MB per song; nothing that size reaches an authoring
model, and which sources a projected form would keep was never decided.

**Detail:** [`experiments/reactive_bands/README.md`](../../experiments/reactive_bands/README.md)

---

## Bar grid and phrase grid by musical consensus

<https://github.com/CPJKU/beat_this>

**Archived** 2026-09-06 — ran, measured, negative.

**The claim.** Fuse several sources of musical evidence — kick placement, chord
changes, section starts, gestures — to resolve the downbeat phase better than any
single beat tracker, and derive a phrase grid from it.

**The result.** Downbeat phase, hits at ±0.25 s:

| essentia (shipped then) | beat-this | **allin1** | this consensus |
| --- | --- | --- | --- |
| 3/7 | 3/7 | **4/7** | 3/7 |

It ties two trackers and loses to the third. Its phrase grid is a clear loss:
0/7 at ±0.5 s against allin1's raw phrase edges at 3/7.

**Worth not rediscovering.**

- **Kick placement carries almost no downbeat-phase information** in
  four-on-the-floor repertoire — Titanium's per-phase histogram is
  `[77, 76, 65, 86]`. The plan had assumed it would be the strongest evidence
  signal; every weighting including kicks scored at or below chord evidence
  alone. An assumption obvious enough that it would otherwise be made again.
- **The problem is deeper than phase.** On `_test_song` all four hypotheses
  agree at confidence 1.0 and the resolved downbeat still misses the impact by
  0.66 s, because essentia's trusted beat *times* place no beat there at all.
  Choosing the right one of four phases cannot fix that.
- `unknown` on 15 of 21 songs may be the most useful thing the run produced:
  chord-change evidence alone is often too sparse to resolve a song's phase, and
  saying so beats snapping a confident wrong grid onto fifteen songs.

**Its carry-forward is already discharged**, which is what made it safe to
archive. The conclusion asked that allin1's downbeat *phase* be taken directly
rather than iterating on the fusion.
[`src/analyzer/stages/timing.py`](../../src/analyzer/stages/timing.py) does
exactly that, adopted in v3.0 item 8.

**Detail:** [`experiments/grid_consensus/README.md`](../../experiments/grid_consensus/README.md)

---

## Section identity from an invariance-trained embedding

<https://github.com/Liu-Feng-deeplearning/CoverHunter>

**Dropped un-run** 2026-09-06, on the operator's queue review. Scoped in the
2026-09-04 wave-2 batch, then skipped in that batch and the next. **No evidence
exists; this is a scoping decision.**

**What it would have asked.** Whether a cover-song-style embedding trained for
invariance between occurrences beats MFCC-20 at section identity — the
representation class the CLAP negative result pointed at.

**Why it was dropped rather than left pending.** It reopens a question already
closed negatively, against a bar of **0.73** that a 20-coefficient classical
baseline set, and it was the heaviest image build of the three pending entries:
several model downloads (CoverHunter/ByteCover, MuQ) behind one harness
alongside the DTW/MFCC baseline, on a 4 GB GTX 1650.

`experiments/` never held code for it. The full plan is in git history if this is
ever revived.

---

## Music Flamingo — timestamped musical description

<https://huggingface.co/nvidia/music-flamingo-hf>

**Dropped un-run** 2026-09-06, on the operator's queue review. Scoped in the
2026-09-04 wave-2 batch, then skipped in that batch and the next. **No evidence
exists; this is a scoping decision.**

**What it would have asked.** Whether an audio-language model can describe what
happens in a song with usable timestamps, cross-checked against the stems. It
was the frontier entry: highest ceiling, highest risk, heaviest to run.

**Why it was dropped rather than left pending.** The checkpoint is released for
**non-commercial research only**, so a positive result could not be promoted
without settling licensing first. That is the reach test failing before the
experiment starts — the run would be exploration that cannot reach the authoring
model.

`experiments/` never held code for it. The full plan is in git history. If the
licence question is ever settled this is worth reopening on its ceiling alone.

---

## CLAP voiceness — contrastive "singing" vs "flute, synth" differential

v3.5 item 5. Full writeup in
[`../experiments/clap_voiceness/README.md`](../experiments/clap_voiceness/README.md).

**Discarded 2026-09-13**, after the operator's by-ear review ("it misses most
phrases and indicates phrases where they aren't") matched the measurement.

**It is inverted, not merely weak** — that is the finding worth keeping.
Balanced accuracy `_test_song` 0.723 / `ayuni` 0.219 / `Queen of Kings` 0.409,
mean **0.451**, below the 0.500 chance line. On `ayuni` the score runs
monotonically *backwards* across the three ground-truth classes — true vocal
0.298, residual 0.479, no-voice **0.559** — and a direct AUC recomputation
against the promoted candidates confirms it: pos-vs-neg **0.213** on `ayuni`
and **0.443** on `Cinderella - Ella Lee`, against `whisperx_vad`'s 0.998 /
0.948 and the sibilance cue's 0.956 / 0.903. The sign convention in `model.py`
was checked and is correct as written, so this is CLAP's reading, not a code
defect; inverting it gives F1 0.477, still under the `arrangement_state`
incumbent's 0.581.

**Why the flute-leak framing did not rescue it.** The pair was chosen
specifically for the pitched-instrument confusion — *"a person singing"* vs
*"a flute, a synth lead"* — and `ayuni`'s flute leak is exactly where it
inverts hardest, scoring the leak (0.559) above real vocals (0.298). A
narrower, better-targeted prompt pair did not fix CLAP's weak vocal axis; that
is now measured twice, in two framings (see the CLAP character-layer entry's
Measurement 1, +0.36…+1.18).

**The honest case against it is unpredictability, not uniform failure.** At a
matched firing budget on `Armin - Revolution` it reaches recall 0.714 at FP-ub
0.423, within 0.13 of whisperX. A candidate competitive on one song and below
chance on another cannot be trusted per-song, which is the only property that
matters for a per-song gate.

**Do not re-run this as a prompt-engineering exercise.** Two different pairs,
two framings, both weak-to-inverted. If CLAP is revisited for vocals it needs a
different mechanism (fine-tuning, or a different audio tower), not a third
prompt.

## Singer Identity — ECAPA-TDNN speaker embeddings for "is this a voice, and whose?"

v3.5 item 8. `experiments/singer_identity/` deleted — this entry carries the
numbers.

**Discarded 2026-09-13** by the operator: the declared lead-vocalist counts
proved useless — they add noise to validation. Do not reintroduce singer
counts as ground truth.

**Method.** ECAPA-TDNN (`speechbrain/spkrec-ecapa-voxceleb`) embeddings over
1.5 s / 0.25 s vocal-stem windows gated by whisperX VAD >= 0.2, agglomerative
clustering, k chosen by silhouette with a k=1 collapse test; two outputs,
`voice_similarity` (voiceness) and `singer_change` (cluster-switch points).

**Singer count 4/9** on the 9 declared songs. All 5 misses are one-singer
songs over-split: `Chimera` k=2, `Titanium` k=3 (39 changes, 10.07/min),
`Sash` k=2, `Rapture` k=2 (9.47/min), `Born Slippy` k=2. Max centroid
similarity 0.33-0.48, silhouette 0.12-0.35 — no gate separates hits from
misses. A `MERGE_SIMILARITY` sweep reached 8/9 at 0.15-0.25, but that setting
then collapsed the duet `Only this moment` (0.438) — no single value works.

**`Armin`'s one marked singer handoff (~81.6 s) was missed** — its only two
change points fell at 12.6 s and 14.1 s.

**Voiceness also failed its own kill condition** (frame_acc / false_vocal
rate vs whisperX): `ayuni` 0.8905 / 0.0160 vs **0.9881 / 0.0056**;
`Cinderella - Ella Lee` 0.5918 / 0.0925 vs **0.8134 / 0.0510**.
