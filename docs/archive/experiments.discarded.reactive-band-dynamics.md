# Reactive band dynamics — local auto-gain instead of whole-song percentiles

[← archive index](experiments_archive.md)

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
