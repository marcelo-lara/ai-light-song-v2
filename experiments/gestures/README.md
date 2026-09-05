# Experiment — Transition-FX and gesture phases

**Status: promoted in v3.0.** Plan item 9 shipped
this into `src/analyzer/stages/gestures.py`, replacing the whole `event_*`
stack (`event_rules/`, `event_machine/`, `event_features/`, `event_timeline.py`,
`event_review.py`, `event_identifiers.py`, `review_queue.py`,
`event_contracts.py`) and rebuilding `song_event_timeline.json` around gesture
phases and section-pair transitions. The **Gestures** debugger lane was
promoted alongside it (item 14) — it now reads the production
`song_event_timeline.json` directly and lost its experiment badge. The
measurements below are kept exactly as run, including the open per-primitive
precision-audit gap; they do not go stale (measured evidence does not go stale). Archive entry:
[`../../docs/archive/experiments.md`](../../docs/archive/experiments.md).

## The question

docs/product-definition.md: a drop "has an approach, a build, a tension span, an
impact and a release, and each phase becomes a different look." The current
`event_*` stack claims this and is measured at chance (CLAUDE.md). But
producers build these gestures out of a small, named, conspicuous set of
sound-design devices — risers, downlifters, reverse cymbals, snare rolls,
pre-drop gaps — each with a detectable signature in artifacts the pipeline
already trusts (`fft_bands.json`, `rms_loudness.json`, `drum_events.json`).

> Do rule-based detectors for these named primitives, assembled into
> composite gestures on the bar grid, land an impact phase where the operator
> marks a drop better than the current event stack — and better than a plain
> RMS-derivative peak-picker?

This experiment explicitly does not name the section (naming stays with the section-pair transition) — it says "a
build of this shape happens here", never "this is the drop".

## How to run it

```bash
docker compose run --rm --no-deps app python -m experiments.gestures.run export
docker compose run --rm --no-deps app python -m experiments.gestures.run score
```

`primitives.py` has one detector per device (riser/downlifter via sliding-
window linear regression on high-band energy, reverse-cymbal via a rising
mix-RMS ramp into a `transient_strength` spike, snare-roll via per-bar
onset-density doubling in `drum_events.json`, impact via a simultaneous
sub-band + transient spike, pre-drop-gap via a `dropout_strength` spike
immediately before an impact). `assembly.py` anchors each gesture on a
detected impact and fills in approach/build/tension/release from whichever
primitives fall in the preceding window; a phase with no supporting primitive
is simply absent (never guessed). `score` reproduces
[`out/score.txt`](out/score.txt).

## Results

Full tables in [`out/score.txt`](out/score.txt). Gold set, 7 drop impacts.

| method | ±0.25s | ±0.5s | ±1.0s | events/min |
| --- | --- | --- | --- | --- |
| gesture impact phase | 2/7 | 4/7 | 4/7 | 14.1 |
| incumbent (`song_event_timeline` impact/drop) | 0/7 | 1/7 | 2/7 | 1.5 |
| **RMS-derivative peak-picker (baseline)** | **3/7** | **6/7** | **7/7** | 40.8 |

**Clearly beats the incumbent** — confirms CLAUDE.md's "measured at chance"
finding directly, on a metric the incumbent's own event stack is supposed to
own. **Does not beat a one-line RMS-derivative peak-picker** on raw recall,
though the peak-picker fires nearly 3× as often and finds nothing named — no
phases, no evidence, nothing auditable beyond "loudness went up here". This
is an honest, humbling result for an eight-detector rule engine: on pure
impact-instant recall, a peak-picker is competitive or better. What the
gesture pipeline delivers that the peak-picker structurally cannot is the
**named internal phase structure** docs/product-definition.md actually asks for —
`12 gestures / 35 primitives` on `_test_song` alone, each with per-primitive
evidence strings auditable against the audio, not just a recall number.

**Non-drop hint coverage** (full table in `out/score.txt`) is where the
detector's real limits show. It covers `hint-001` "Drum Hit", `hint-004`
"Spacer", `hint-005` "Outro start" and `hint-017` "High Energy" on
`_test_song` via `build`/`tension`/`release` phases. It **misses every one**
of the three `Vocal outro` phrases, `Synth Pad`, `prepare for end` and
`Finale` — all vocal- or texture-driven blocks with no riser, roll, or
transient signature to detect. That is exactly the gap the sibling
`vocal_phrases` experiment (run order 1) targets, not a bug here — gesture
primitives and vocal-phrase blocks are complementary, not overlapping,
signal.

## Conclusion

Positive against the thing it was built to replace (the `event_*` stack),
negative against the cheapest possible baseline on raw recall, and the one
thing it uniquely offers — named, evidenced, phase-structured gestures — is
not captured by a recall-only metric at all. Per-primitive precision (does
each detected riser/gap/roll actually exist in the audio) was **not**
independently hand-audited in this run beyond spot-checking the exported
spans against the score tables above; the plan calls for this and it remains
open. Before any promotion discussion: a precision audit by ear (the plan's
own suggested check, ~20-30 spans across four songs), and a version of the
RMS-peak baseline that also reports *something* structured, so the
comparison isn't recall-only against a method that can't lose on "does it say
anything wrong" because it says nothing at all.

## Reach test

`song_event_timeline.json` — phases would become the tightly-timed,
high-value discrete events with real `intensity` the input guide asks for.
If promoted this is a phase-3 stage and the first honest candidate to
**replace** part of the `event_*` stack rather than add to it. Given the
open precision-audit question above, **not ready to promote**.
