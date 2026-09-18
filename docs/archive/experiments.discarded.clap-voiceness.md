# CLAP voiceness — contrastive "singing" vs "flute, synth" differential

[← archive index](experiments_archive.md)

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
