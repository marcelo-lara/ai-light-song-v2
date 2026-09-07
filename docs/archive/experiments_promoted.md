# Archive — promoted experiments

Experiments that beat the incumbent and moved into `src/`. One short entry each:
what it replaced, the numbers that justified it, and the caveat it shipped with.

**These are TLDRs.** The full writeup and the raw tables live in
`experiments/<topic>/README.md`, which stays in the tree as current material —
measured evidence does not go stale. Read that before extending the stage.

Discarded experiments: [`experiments_discarded.md`](experiments_discarded.md).
Still open: [`../experiments.md`](../experiments.md).

| experiment | replaced | headline |
| --- | --- | --- |
| All-In-One | `stages/sections/`, 1,403 lines | boundary F1 **0.67** vs incumbent **0.29** |
| Transition-FX gestures | the `event_*` stack, ~3,800 lines | impacts **4/7** @±0.5 s vs incumbent **1/7** |

---

## All-In-One (`allin1`) — named song form

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

---

## Transition-FX and gesture phases — riser, downlifter, snare roll, pre-drop gap, impact

<https://www.ujam.com/tutorials/how-to-create-huge-edm-transitions/>

**Promoted** in v3.0 item 9 → `src/analyzer/stages/gestures.py`. Deleted the
whole Epic-5 `event_*` stack (`event_rules/`, `event_machine/`,
`event_features/`, `event_timeline.py`, `event_review.py`,
`event_identifiers.py`, `review_queue.py`, `event_contracts.py`, ~3,800 lines).
Changed `song_event_timeline.json`.

**The claim.** A drop has an approach, a build, a tension span, an impact and a
release, and each phase becomes a different look. The `event_*` stack claimed to
do this and measured at chance, because it inferred gestures from raw features
with no named structure to hang them on. This builds one detector per named,
conspicuous sound-design device instead, and assembles them into composite
gestures with named internal phases.

**The result**, gold set, 7 drop impacts:

| method | ±0.25 s | ±0.5 s | ±1.0 s | events/min |
| --- | --- | --- | --- | --- |
| gesture impact phase | 2/7 | **4/7** | 4/7 | 14.1 |
| incumbent `event_*` stack | 0/7 | 1/7 | 2/7 | 1.5 |
| RMS-derivative peak-picker (baseline) | **3/7** | **6/7** | **7/7** | 40.8 |

**It beat the incumbent and lost to the cheapest possible baseline on raw
recall.** It was promoted anyway, on the structural requirement rather than the
number: the baseline fires ~3× as often and emits no phases, no evidence, and no
claim that can be wrong, while the gesture stage assembled 12 gestures from 35
primitives on `_test_song` alone, each phase carrying its own span, confidence
and per-primitive evidence string.

**Shipped unresolved — two known gaps, both still open.**

- **Per-primitive precision was never audited.** The plan called for a
  hand-audit by ear over 20–30 spans; it was not run before promotion. A phantom
  riser does not move an impact-recall metric at all, but it fires a cue that
  contradicts the song. Tracked in [`../issues.md`](../issues.md).
- **Coverage of non-drop hints is weak.** Every miss on Armin's "Breath" and
  `_test_song`'s vocal outro phrases was vocal- or texture-driven with no
  riser/roll/transient signature — complementary to the texture work, not
  overlapping with it.

**Detail:** [`experiments/gestures/README.md`](../../experiments/gestures/README.md)
