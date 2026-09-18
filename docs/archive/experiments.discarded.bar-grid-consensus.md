# Bar grid and phrase grid by musical consensus

[← archive index](experiments_archive.md)

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
