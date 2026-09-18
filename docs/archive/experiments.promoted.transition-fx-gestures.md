# Transition-FX and gesture phases — riser, downlifter, snare roll, pre-drop gap, impact

[← archive index](experiments_archive.md)

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
