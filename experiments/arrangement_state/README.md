# Experiment — arrangement state: *who is playing*, and where that changes

No model, no repo. The whole detector is arithmetic over
`data/analysis/{song}/loudness.json`, which the pipeline already publishes.

**Status: measured. Decisive on the one densely texture-labelled song, and
unmeasurable on the other three because their ground truth marks only drops.**
Nothing in `src/` reads anything in here. Queue entry:
[`../../docs/experiments.md`](../../docs/experiments.md).

## The question

It started as a question about the debugger. Looking at `_test_song` in the UI,
the operator read the per-stem RMS lane and said, without hesitation:

> bars 7–15 there is a voice approach to a high energy region from bar 15–22 …
> we do not want the exact name, but something to tell "something is happening
> here, that is different to other region". Why is it so hard for models to
> infer something there?

Here is everything the authoring model is told about those fifteen seconds:

```
section-002   14.82 → 58.05   "chorus [unverified]"   confidence 0.446
```

One 43-second row covering the vocal approach, the drop, the high-energy
region, the spacer and the entire outro. The model is not failing to infer the
contrast. It is being handed a surface on which the contrast does not exist.

So the question this experiment asks is narrower than "can a model hear it":

> The per-stem RMS series is already published. **Does reading it as a state
> vector — who is playing, right now — recover the boundaries the operator
> marks by hand, and does it beat the sections we ship?**

## Why the existing stages cannot see it

Every producer of published structure reads something other than the stems.

| producer | reads | so it cannot see |
| --- | --- | --- |
| `segmentation.py` (allin1) | mix spectrogram, argmax over 10 labels, quantised to 8 bars | a change shorter than 8 bars — at `_test_song`'s ~1.85 s/bar that is 14.8 s, longer than the whole high-energy region |
| `harmonic.py` | HPCP | anything that is not pitch — the chord is `D#m` on both sides of every boundary above |
| `gestures.py` | mix FFT + drum onsets | a *state*; it emits build/impact/release events, not "who is playing now" |
| `loudness.py` | per-stem RMS ✅ | — it publishes the series and draws no conclusion from it |

The signal is in the delivery surface as raw numbers, and no stage turns it into
a fact. That is the gap, and it is a plumbing gap, not a perception one.

## The detector

[`detector.py`](detector.py). Three decisions carry the result.

1. **Per-stem, per-song thresholds.** A stem sounds when it is within 18 dB of
   its own 98th percentile *in this song*. Nothing absolute, nothing shared
   between stems or tracks.
2. **Detect at 250 ms, gate on persistence, report the fine edge.** A flip is
   believed only when the new value holds for 1.5 s — but the time reported is
   always the unsmoothed 250 ms edge.
3. **The mix channel never triggers a change.** It is a sum; it moves whenever
   any stem moves and adds no independent evidence.

Every change carries `margin_db`, the smallest dB headroom among the stems that
flipped. That is the natural confidence: it is a measured distance from the
decision boundary, not a tuned score.

## How to run it

Stdlib only, so the ordinary `app` service is enough — no research image.

```bash
docker compose run --rm --no-deps -T --entrypoint python app \
  -m experiments.arrangement_state.run score            # gold set, vs incumbent + baseline
docker compose run --rm --no-deps -T --entrypoint python app \
  -m experiments.arrangement_state.run export           # reference/proposals/arrangement_state.json
```

[`out/score.txt`](out/score.txt) is the committed evidence.

## Measurement 1 — smoothing is what destroys this, and it is not a small effect

The obvious way to clean up a noisy presence signal is to smooth it before
thresholding. It costs the boundary. Same detector, same song, ±1 s smoothing
of the presence fractions instead of persistence gating:

| variant | P / R / F1 @ 0.5 s on `_test_song` | `Spacer` boundary error |
| --- | --- | --- |
| **persistence gate, fine edge reported** | **0.59 / 0.60 / 0.59** | **0.00 s** |
| ±1 s smoothing before threshold | 0.27 / 0.27 / 0.27 | 6.0 s |

Smoothing more than halves F1 *and* displaces a hand-marked boundary by six
seconds. This is the repository's "the physical onset wins over the nearest grid
position" rule showing up as a number — a cue fired late is a cue missed.

It also explains a known result. The CLAP character layer
([`../clap/README.md`](../clap/README.md)) uses `smooth_s: 2.0` and
`min_block_s: 4.0`, and on `_test_song` emits three blocks, missing the 16 s
vocal entry, the 36.5 s `Spacer` and the whole outro structure. The
smoothing was the cost, not the stems.

## Measurement 2 — `_test_song`, the one song with dense texture labels

15 hand-marked hints in 58 s. Scored against hint *start times* — the
operator's own answer to "something different starts here".

| method | n | P / R / F1 @ 0.5 s | @ 1.0 s |
| --- | --- | --- | --- |
| **arrangement state** | 17 | **0.59 / 0.60 / 0.59** | **0.76 / 0.73 / 0.75** |
| shipped `sections.json` (incumbent) | 1 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |
| even grid, same budget (baseline) | 17 | 0.18 / 0.27 / 0.21 | 0.47 / 0.73 / 0.57 |

The hits are not merely near. Median absolute error over the nine hits is
**0.07 s**:

```
 22.25  +drums          drop approach          22.18   d=+0.07
 25.00  +vocals -bass   drop build             25.02   d=-0.02
 29.75  +bass -vocals   High Energy            29.59   d=+0.16   <- the operator's bar 15
 36.50  +drums          Spacer                 36.50   d= 0.00
 42.50  -bass           Outro start            42.48   d=+0.02   <- the operator's bar 22
 43.25  +vocals         Vocal outro phrase 1.1 43.34   d=-0.09
 44.50  +bass -vocals   Synth Pad              44.45   d=+0.05
 47.00  +vocals         Vocal outro 2          47.09   d=-0.09
 55.25  -vocals         Finale                 55.04   d=+0.21
```

And the six misses partition cleanly — **none of them belong to this detector**:

| miss | what it actually is | who should own it |
| --- | --- | --- |
| `Drum Hit` 7.44 | a 186 ms one-shot | `gestures.py` impact primitive |
| `drop tension` / `impact` / `release` 27.6–29.1 | sub-bar internals of one gesture | `gestures.py` |
| `Vocal Outro 3` 50.08 | a phrase split *inside* continuous vocals | [`../vocal_phrases/`](../vocal_phrases/README.md) |
| `prepare for end` 54.61 | a fade, not a stem flip | an envelope-slope term, not built |

Arrangement state + impact + phrase + fade accounts for 15/15, and three of the
four already exist. This detector is one member of a family, not a replacement
for the others.

## Measurement 3 — the Armin "Breath" block, without a model

The block the CLAP experiment was built to find. Hand-marked 81.39–96.33,
*"Vocal - no intense section"*.

| source | block | start error | end error |
| --- | --- | --- | --- |
| hand-marked | 81.39 – 96.33 | — | — |
| **arrangement state (stems only)** | **81.50 – 95.50** | **+0.11 s** | **−0.83 s** |
| CLAP character layer (`stems+clap`) | 83.50 – 95.00 | +2.11 s | −1.33 s |

```
 81.50  +vocals   -> [drums,harmonic,vocals]   margin +10.5 dB
 83.00  -drums    -> [harmonic,vocals]         margin  +5.2 dB
 95.50  +drums    -> [drums,harmonic,vocals]   margin +11.5 dB
```

Tighter on both edges than the GPU pass, from a JSON file. This does not make
CLAP worthless — the CLAP ablation's finding stands, that the calm/intense axis
is what cuts a texture detector's *false territory* from 73 % of the corpus to
41 %. It relocates the division of labour exactly where that experiment already
concluded it belonged: **the stems say what is playing; CLAP says how it feels.**

## Measurement 4 — the corpus, and why its number measures the labels

| song | hints | state F1 @0.5 s | incumbent F1 @0.5 s | grid F1 @0.5 s |
| --- | --- | --- | --- | --- |
| `_test_song` | 15 | **0.59** | 0.00 | 0.21 |
| `Hideaway - Kiesza` | 5 | 0.13 | **0.33** | 0.00 |
| `Armin - Revolution` | 12 | 0.20 | **0.24** | 0.09 |
| `Titanium - David Guetta ft Sia` | 15 | 0.07 | **0.33** | 0.07 |
| **corpus (pooled)** | 47 | **0.20** (R 0.43) | **0.24** (R 0.19) | 0.08 (R 0.19) |

Read straight, the detector loses to the incumbent corpus-wide on F1 while more
than doubling its recall. Both halves of that are real, and the reason is the
labels:

**32 of the 47 corpus hints are `drop approach` / `build` / `tension` /
`impact` / `release`** — Hideaway 5 of 5, Titanium 15 of 15, Armin 10 of 12.
Those are gesture stages, which `gestures.py` already owns and this detector is
not trying to find. Outside `_test_song` the corpus contains exactly **two**
texture hints: Armin's `Breath` and one `Vocal Phrase`. So on three of four gold
songs, every genuine arrangement change the detector finds is scored as a false
positive by construction, and the precision figure is measuring an absence of
labels.

This is the "ground truth is precious and scarce" rule firing: the measurement
sits at the noise floor of the labels, so **the next move is to mark texture
blocks on the other three gold songs, not to tune the detector against drops.**

Confirming that tuning is not the answer: gating changes by `margin_db` trades
recall for precision without ever improving corpus F1 — 0.20 at 0 dB, 0.20 at
2 dB, 0.19 at 4 dB, 0.18 at 6 dB, 0.10 at 12 dB. The margin is a good
confidence and a poor filter, which is the expected shape for a detector whose
false positives are mostly unlabelled true positives.

## Review it

`run export` writes
`data/analysis/{song}/reference/proposals/arrangement_state.json` — one block
per span, each naming the stems playing, the stems that entered and left at its
start, and the `margin_db` behind that decision. **The UI lane that renders it
is not built yet**, and this experiment cannot be judged by ear until it is; the
lane belongs directly beneath **Human Hints**, next to **Drop Proposals**.

## Conclusion

**The contrast the operator sees in the UI is recoverable to ±0.1 s by
arithmetic over a file the pipeline already publishes, and no shipped stage
looks for it.** On the only song labelled densely enough to measure, it scores
F1 0.59 @0.5 s where `sections.json` scores 0.00, and it finds the reference
`Breath` block more tightly than a CLAP forward pass.

Two things are needed before promotion is worth discussing: the UI lane, and
texture hints on the other three gold songs so the corpus number means
something. Not promoted; nothing in `src/` reads this.

## Negative results worth not rediscovering

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
