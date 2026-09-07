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
| Arrangement state | nothing — new stage | `_test_song` F1 **0.59** @0.5 s vs `sections.json` **0.00** |

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

---

## Arrangement state — *who is playing*, from a file the pipeline already publishes

No model, no repo. The detector is arithmetic over
`data/analysis/{song}/loudness.json`.

**Promoted** in v3.2 plan items 1-2 → `src/analyzer/stages/arrangement_state.py`
(detection) and `publish_arrangement_state` in `ui_data.py` (the top-level
`arrangement_state.json`). Replaced nothing — the pipeline had no
arrangement-state stage. Unlike the other two entries there is **no surviving
`experiments/` README**: it was deleted in the same change, so everything worth
keeping is reproduced here.

**The claim.** Every producer of published structure reads something other than
the stems — `segmentation.py` a mix spectrogram quantised to 8 bars,
`harmonic.py` HPCP, `gestures.py` mix FFT + drum onsets (events, not a state).
`loudness.py` publishes the per-stem RMS series and draws no conclusion from it.
Read that series as a state vector — who is playing, right now — and it recovers
boundaries the operator marks by hand that no shipped stage emits.

**The detector.** Per-stem, per-song thresholds (a stem sounds when within 18 dB
of its own 98th percentile in this song). Detect at 250 ms, gate on 1.5 s
persistence, report the unsmoothed edge. The mix channel never triggers a change
(it is a sum of the stems). Every change carries `margin_db`, the smallest dB
headroom among the stems that flipped — a measured distance from the decision
boundary, and the basis of the published `confidence`
(`round(1 - exp(-margin_db / 6.0), 3)`, `null` for the leading block).

### Measurement 1 — smoothing is the failure mode

`detect_smoothed()` (dropped at promotion, recorded here): same windows and
thresholds, but a ±1.0 s duty cycle gated by hysteresis instead of the
persistence gate.

| variant | n | P / R / F1 @ 0.5 s on `_test_song` | `Spacer` boundary error |
| --- | --- | --- | --- |
| **persistence gate, fine edge (shipped)** | 17 | **0.59 / 0.60 / 0.59** | **0.00 s** |
| ±1 s duty-cycle smoothing + hysteresis | 15 | 0.27 / 0.27 / 0.27 | 6.00 s |

Smoothing more than halves F1 **and** displaces the hand-marked `Spacer`
boundary by 6 s — "the physical onset wins over the nearest grid position" as a
number. It also explains the CLAP character layer's miss: its `smooth_s: 2.0` /
`min_block_s: 4.0` is why it emits only three blocks on `_test_song`, missing the
16 s vocal entry, the 36.5 s `Spacer` and the whole outro. The smoothing was the
cost, not the stems. (The CLAP entry in [`../experiments.md`](../experiments.md)
cites this measurement.)

### Measurement 2 — `_test_song`, the one song with dense texture labels

15 hand-marked hints in 58 s, scored against hint *start* times.

| method | n | P / R / F1 @ 0.5 s | @ 1.0 s |
| --- | --- | --- | --- |
| **arrangement state** | 17 | **0.59 / 0.60 / 0.59** | **0.76 / 0.73 / 0.75** |
| shipped `sections.json` (incumbent) | 1 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| even grid, same budget (baseline) | 17 | 0.18 / 0.27 / 0.21 | 0.47 / 0.73 / 0.57 |

Median absolute error over the nine hits is **0.07 s**. The six misses partition
cleanly and none belong to this detector: `Drum Hit` (186 ms one-shot →
`gestures.py`), three drop stages at 27.6–29.1 (gesture internals →
`gestures.py`), `Vocal Outro 3` (a phrase split inside continuous vocals → the
vocal-phrase entry) and `prepare for end` (a fade, not a stem flip).

### Measurement 3 — the Armin "Breath" block, without a model

Hand-marked 81.39–96.33, *"Vocal — no intense section"* — the block the CLAP
experiment was built to find.

| source | block | start error | end error |
| --- | --- | --- | --- |
| hand-marked | 81.39 – 96.33 | — | — |
| **arrangement state (stems only)** | **83.00 – 95.50** | **+1.61 s** | **−0.83 s** |
| CLAP character layer (`stems+clap`, `char-004`) | 83.50 – 95.00 | +2.11 s | −1.33 s |

A 1.75 s drum re-entry at 81.25–83.0 s (audible under the vocal) splits what the
eye reads as one block into two; the block matching "no intense section" is the
second, `83.00–95.50`. Tighter than the GPU pass on both edges. This confirms the
CLAP division of labour: the stems say *what is playing*, CLAP says *how it
feels* — its calm/intense axis still cuts a texture detector's false territory
from 73 % to 41 %.

### Measurement 4 — the corpus, and why its number measures the labels

| song | hints | state F1 @0.5 s | incumbent F1 @0.5 s | grid F1 @0.5 s |
| --- | --- | --- | --- | --- |
| `_test_song` | 15 | **0.59** | 0.00 | 0.21 |
| `Hideaway - Kiesza` | 5 | 0.13 | **0.33** | 0.00 |
| `Armin - Revolution` | 12 | 0.20 | **0.24** | 0.09 |
| `Titanium - David Guetta ft Sia` | 15 | 0.07 | **0.33** | 0.07 |
| **corpus (pooled)** | 47 | **0.20** (R 0.43) | **0.24** (R 0.19) | 0.08 (R 0.19) |

The detector loses to the incumbent on pooled F1 while more than doubling recall.
The cause is the label set: **32 of the 47 corpus hints are the five stages of a
drop** (Hideaway 5/5, Titanium 15/15, Armin 10/12), which `gestures.py` owns.
Outside `_test_song` the corpus holds exactly two texture hints, so on three of
four gold songs every genuine arrangement change is scored as a false positive by
construction.

Tuning does not rescue it — `margin-sweep` filters `detect()`'s changes to
`margin_db >= threshold` and rescores:

| min `margin_db` | 0 | 2 | 4 | 6 | 8 | 10 | 12 | 15 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pooled F1 @0.5 s | 0.20 | 0.20 | 0.19 | 0.18 | 0.17 | 0.16 | 0.10 | 0.10 |
| pooled F1 @1.0 s | 0.25 | 0.26 | 0.25 | 0.24 | 0.22 | 0.21 | 0.16 | 0.18 |

The margin is a good confidence and a poor filter.

**Promoted on `_test_song` evidence alone, knowingly.** Texture hints on
`Hideaway` / `Armin` / `Titanium` are still unmarked, so the corpus number stays
uninformative until they are — tracked in [`../issues.md`](../issues.md).

### Negative results worth not rediscovering

* **Smoothing the presence signal before thresholding is not a tuning choice, it
  is the failure.** F1 0.59 → 0.27 on `_test_song`, `Spacer` displaced 6 s.
  Gate on persistence and report the unsmoothed edge.
* **`margin_db` does not work as a precision filter** on this corpus — sweeping
  0 → 15 dB never improves corpus F1. It is a confidence, not a gate.
* **The mix channel must be excluded from state changes.** It is a sum of the
  stems, so including it duplicates every real change and invents none.
* **Do not score a texture detector against drop-stage labels.** 32 of the 47
  hand-marked hints in the gold corpus are the five stages of a drop. The
  resulting precision number is about the label set, not the detector.

**Shipped unresolved.** The corpus number is uninformative until texture blocks
are marked on the other three gold songs; the CLAP `feel` field is a planned
second fuse candidate on the same rows.
