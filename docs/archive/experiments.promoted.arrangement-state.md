# Arrangement state — *who is playing*, from a file the pipeline already publishes

[← archive index](experiments_archive.md)

No model, no repo. The detector is arithmetic over
`data/analysis/{song}/loudness.json`.

**Promoted** in v3.2 plan items 1-2 → `src/analyzer/stages/arrangement_state.py`
(detection) and `publish_arrangement_state` in `ui_data.py` (the top-level
`arrangement_state.json`). Replaced nothing — the pipeline had no
arrangement-state stage. Unlike the other entries in this archive there is **no
surviving `experiments/` README**: it was deleted in the same change, so
everything worth keeping is reproduced here.

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
