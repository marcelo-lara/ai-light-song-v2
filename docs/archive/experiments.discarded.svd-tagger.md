# SVD Tagger — PANNs `Singing` class, stem vs mix

[← archive index](experiments_archive.md)

**Archived** 2026-09-17 — ran over all 23 songs, measured, negative. PANNs'
`Singing` posterior discriminates well in ranking (AUC 0.87-0.96) but reads at
too low a magnitude on a separated vocal stem to fire at any usable
threshold — raw frame_acc equalled the negative-class fraction because it
never spoke. Per-song `_p98` rescaling (declared before measuring) made it
fire, but not competitively: best rescaled frame_acc `ayuni`/`Cinderella`
0.8538/0.5125 against the shipped `whisperx_vad`'s 0.9881/0.8614, at 1.75-2.19
bounds/min against whisperX's 5-13. This was also the costliest candidate in
the voiceness family — its own sandbox image plus a 327 MB PANNs checkpoint
pin — for a result that never closed the gap to the incumbent. `experiments/
svd_tagger/` stays in the tree as the record; the `6. SVD Tagger` debugger
lane was removed.
