# All-In-One (`allin1`) — named song form

[← archive index](experiments_archive.md)

<https://github.com/mir-aidj/all-in-one>

**Promoted** in v3.0 item 7 → `src/analyzer/stages/segmentation.py`. Deleted
`src/analyzer/stages/sections/` — a 1,403-line deterministic-DSP segmenter plus
its 13-value invented `section_character` vocabulary. Changed `sections.json`.

**The claim.** The old segmenter labelled sections with invented mood adjectives
("Momentum Lift", "Vocal Spotlight"), so nothing said *which part of the song* a
section is — and its boundaries measured at chance. allin1 was the one model in
the 2026-09 survey emitting *named* functional structure (Harmonix vocabulary:
`intro verse chorus bridge inst solo break outro`) for pop/EDM.

**The result**, against 38 Moises boundaries at ±1.0 s:

| | recall | precision | F1 | bounds/min |
| --- | --- | --- | --- | --- |
| **allin1 merged sections (shipped)** | 0.53 | **0.91** | **0.67** | **1.6** |
| allin1 raw phrase edges | 0.84 | 0.76 | 0.80 | 3.3 |
| old `sections/` segmenter | 0.32 | 0.27 | 0.29 | 3.6 |

Merged runs ship rather than raw phrase edges: a boundary the cue author can
trust is worth more than one more recalled boundary.

**Worth not rediscovering.**

- **Seeding is mandatory, not an optimisation.** Unseeded, allin1 shells out to
  its own demucs and disagrees with itself on 14 of 21 songs. Seeded with the
  pipeline's stems it is byte-identical across three runs. The earlier survey's
  "degenerates on instrumental trance" verdict was an unseeded-demucs artifact,
  not a property of the model.
- **Its beat grid is not usable.** 4 of 21 corpus songs sit a clean half-beat off
  essentia's and one halves the tempo. Take structure only; keep essentia's grid.

**Shipped unresolved.** Section *identity* — `same_label_as` is label repetition,
not acoustic identity.

**Detail:** [`experiments/allin1/README.md`](../../experiments/allin1/README.md)
