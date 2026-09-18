# Voice Multiplicity — stereo width + L/R correlation on the vocal stem

[← archive index](experiments_archive.md)

**Archived** 2026-09-17 — ran over all 23 songs, measured, **positive on one
song**, not promoted. Per-frame `multiplicity` (mid/side width + L/R
correlation, per-song z-scored) scored AUC **0.951** against the operator's
labelled lead-vs-chorus spans on `Queen of Kings`, and an adversarial control
passed — a documented one-take vocal (`Underworld - Born Slippy`) produced
only 2.4 s of false "stacked" across the whole track, because per-song
z-scoring normalises constant stereo effects away. Not archived for a
negative result: it is **data-starved**, not contradicted — `Queen of Kings`
is the only song in the corpus carrying `voices` labels, so the 23-song sweep
produced data but no second scoreable song. The block layer also needed more
work (smoothing, per-song percentile cuts) before it would be usable.
`experiments/voice_multiplicity/` stays in the tree as the record; the
`Voice Multiplicity` debugger lane was removed.
