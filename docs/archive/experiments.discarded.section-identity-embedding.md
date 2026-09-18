# Section identity from an invariance-trained embedding

[← archive index](experiments_archive.md)

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
