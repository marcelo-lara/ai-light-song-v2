"""Combine the three cues into a per-frame voiceness score, and derive
`vocal_phrase` blocks with the sustained-note pitch-continuity bridge.

**Combination rule — noisy-OR, not a weighted average.** The refinement doc's
own framing is that sibilance is "the single cue no pitched instrument can
fake" — i.e. a single strong cue should be enough to call a frame voiced, not
diluted by two other cues sitting near zero at that same instant (vibrato and
portamento are properties of a held note or a glide; a plosive consonant frame
has neither, but its sibilance alone should still carry the frame). A weighted
sum would punish exactly the frames where the cues are individually strongest.
So each cue is treated as a "probability of voice" reliability-weighted, and
combined as:

    voiceness = 1 - (1 - w_vibrato * vibrato) * (1 - w_portamento * portamento) * (1 - w_sibilance * sibilance)

with `w_sibilance` highest (hardest cue to fake per the refinement doc),
`w_vibrato` next (a strong, well-formed vibrato is a strong pitched-voice
tell), `w_portamento` lowest (glide bands are the least selective of the
three — bent-note pitched instruments can produce a similar slope). Weights
are a documented judgement call, not fit to any ground truth (none exists yet
— see `features.py`'s module docstring).

**Confidence.** `evidence_margin = |voiceness - 0.5| * 2`, clipped to [0, 1] —
an honest heuristic for "how far this frame's call sits from the decision
boundary," not a calibrated probability. A frame with no vibrato/portamento
window evidence AND near-zero sibilance is not specially flagged: `voiceness`
degrades gracefully to whatever cue did fire (sibilance always has evidence,
since it is read from every fft_bands frame), so the "unknown" case here is
"nothing fired," rendered as a low, not a null, voiceness — consistent with
`VoicenessFrame.confidence` staying an honest per-cue-evidence signal.

**The `sustained_notes` bridge (v3.5 item 4, explicit fix, not inherited).**
`vocal_phrases.detector.derive_phrases` gates on RMS-ratio hysteresis alone: a
held note's own natural amplitude decay can dip the ratio below the OFF
threshold mid-note, splitting one sustained tone into two word-level runs
before either reaches the 1.5s sustain minimum — confirmed on `_test_song`'s
drop-build hold (`experiments/vocal_phrases/README.md`, "A real, documented
limitation"). This module recomputes the word-level hysteresis run split via
`vocal_phrases.detector` (imported directly, not monkeypatched), then BEFORE
the breath-merge step, bridges any inter-run gap that is short
(`BRIDGE_MAX_GAP_S`) and pitch-continuous (the f0 just before the gap and the
f0 just after it sit within `BRIDGE_PITCH_TOLERANCE_CENTS`, using pYIN samples
that fall inside the gap itself when pYIN reports any pitch there, else the
before/after boundary values only — a direct-evidence bridge is marked with
higher confidence than a boundary-only one, and that distinction is kept in
the emitted phrase's `raw` info). This produces `vocal_phrase` spans that do
not fragment on the exact gap `vocal_phrases` documents as a known limitation.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import medfilt

from experiments.vocal_phrases import detector as vp_detector

from . import features

WEIGHT_VIBRATO = 0.55
WEIGHT_PORTAMENTO = 0.35
WEIGHT_SIBILANCE = 0.80

BRIDGE_MAX_GAP_S = 0.6            # a mid-note amplitude dip, not real silence
BRIDGE_PITCH_TOLERANCE_CENTS = vp_detector.PITCH_TOLERANCE_CENTS  # 60 cents, matches vocal_phrases
MIN_PHRASE_S = vp_detector.MIN_PHRASE_S
DEFAULT_BREATH_S = vp_detector.DEFAULT_BREATH_S
DEFAULT_SUSTAIN_S = vp_detector.DEFAULT_SUSTAIN_S


def combine_voiceness(feat: features.VoicenessFeatures) -> tuple[list[float], list[float]]:
    vib = np.array(feat.vibrato)
    port = np.array(feat.portamento)
    sib = np.array(feat.sibilance)

    p_not_voiced = (
        (1.0 - WEIGHT_VIBRATO * vib)
        * (1.0 - WEIGHT_PORTAMENTO * port)
        * (1.0 - WEIGHT_SIBILANCE * sib)
    )
    voiceness = np.clip(1.0 - p_not_voiced, 0.0, 1.0)
    confidence = np.clip(np.abs(voiceness - 0.5) * 2.0, 0.0, 1.0)
    return voiceness.round(4).tolist(), confidence.round(3).tolist()


def _median_f0_near(times: np.ndarray, f0: np.ndarray, t: float, window_s: float = 0.1) -> float:
    idx = (times >= t - window_s) & (times <= t + window_s) & (f0 > 0)
    vals = f0[idx]
    return float(np.median(vals)) if len(vals) else 0.0


def _bridge_word_spans(
    word_spans: list[tuple[float, float]],
    times: np.ndarray,
    f0: np.ndarray,
) -> tuple[list[tuple[float, float]], list[dict]]:
    """Merge consecutive word-level runs across a short, pitch-continuous gap.

    Returns (bridged_spans, bridge_events) — `bridge_events` records every gap
    that was actually bridged, for `raw` provenance in the exported phrase.
    """
    if not word_spans:
        return word_spans, []

    bridged: list[tuple[float, float]] = [word_spans[0]]
    events: list[dict] = []
    for start, end in word_spans[1:]:
        prev_start, prev_end = bridged[-1]
        gap = start - prev_end
        if gap <= 0:
            bridged[-1] = (prev_start, end)
            continue
        if gap > BRIDGE_MAX_GAP_S:
            bridged.append((start, end))
            continue

        pitch_before = _median_f0_near(times, f0, prev_end, window_s=0.1)
        pitch_after = _median_f0_near(times, f0, start, window_s=0.1)
        if pitch_before <= 0 or pitch_after <= 0:
            bridged.append((start, end))
            continue
        cents_diff = abs(1200.0 * np.log2(pitch_after / pitch_before))
        if cents_diff > BRIDGE_PITCH_TOLERANCE_CENTS:
            bridged.append((start, end))
            continue

        inside = (times > prev_end) & (times < start) & (f0 > 0)
        direct_evidence = bool(inside.any())
        if direct_evidence:
            inside_vals = f0[inside]
            inside_cents = 1200.0 * np.log2(inside_vals / pitch_before)
            if np.any(np.abs(inside_cents) > BRIDGE_PITCH_TOLERANCE_CENTS * 2):
                # pitch wandered too far during the dip to call this the same
                # note — do not bridge.
                bridged.append((start, end))
                continue

        bridged[-1] = (prev_start, end)
        events.append({
            "gap_start": round(float(prev_end), 3),
            "gap_end": round(float(start), 3),
            "gap_s": round(float(gap), 3),
            "cents_diff": round(float(cents_diff), 1),
            "direct_evidence": direct_evidence,
        })
    return bridged, events


def derive_vocal_phrases(song: str) -> dict:
    """Recomputes `vocal_phrases`'s word-level hysteresis run split, applies
    the pitch-continuity bridge, then reuses its own breath-merge / min-phrase
    filter and sustained-note pass on the bridged spans."""
    env = vp_detector.compute_envelope(song)
    times = np.array(env.times)
    ratio = np.array(env.ratio)
    f0 = np.array(env.f0_hz)

    active = vp_detector._hysteresis_active(ratio, vp_detector.ON_RATIO, vp_detector.OFF_RATIO)
    word_spans = vp_detector._runs(active, env.times)
    bridged_spans, bridge_events = _bridge_word_spans(word_spans, times, f0)

    # breath-merge (identical to vp_detector.derive_phrases) over the bridged runs
    phrase_spans: list[tuple[float, float]] = []
    for (s, e) in bridged_spans:
        if phrase_spans and s - phrase_spans[-1][1] < DEFAULT_BREATH_S:
            phrase_spans[-1] = (phrase_spans[-1][0], e)
        else:
            phrase_spans.append((s, e))
    phrase_spans = [sp for sp in phrase_spans if sp[1] - sp[0] >= MIN_PHRASE_S]

    phrases = []
    for (s, e) in phrase_spans:
        idx = (times >= s) & (times <= e)
        seg_ratio = ratio[idx]
        conf = float(np.clip(
            (seg_ratio.mean() - vp_detector.OFF_RATIO)
            / max(vp_detector.ON_RATIO - vp_detector.OFF_RATIO, vp_detector.EPS),
            0.0, 1.0,
        )) if len(seg_ratio) else 0.0
        bridged_here = [
            ev for ev in bridge_events if s - 1e-6 <= ev["gap_start"] and ev["gap_end"] <= e + 1e-6
        ]
        phrases.append({
            "start": round(float(s), 3),
            "end": round(float(e), 3),
            "confidence": round(conf, 3),
            "bridged_gaps": bridged_here,
        })

    # sustained notes over the bridged phrase spans (vp_detector's own pass,
    # now finding longer runs because a mid-note amplitude dip no longer
    # fragments the phrase before the sustain minimum is reached).
    hop_s = env.hop_length / env.sr
    kernel = max(1, int(round(0.05 / hop_s)))
    if kernel % 2 == 0:
        kernel += 1
    f0_smooth = medfilt(f0, kernel_size=kernel) if len(f0) > kernel else f0

    sustained = []
    for (s, e) in phrase_spans:
        idx = np.where((times >= s) & (times <= e))[0]
        if len(idx) < 2:
            continue
        run_start_i = idx[0]
        anchor = None
        for i in idx:
            v = f0_smooth[i]
            if v <= 0:
                if anchor is not None:
                    dur = times[i - 1] - times[run_start_i]
                    if dur >= DEFAULT_SUSTAIN_S:
                        sustained.append(vp_detector._sustained_entry(times, f0_smooth, run_start_i, i - 1))
                anchor = None
                run_start_i = i + 1 if i + 1 < len(times) else i
                continue
            if anchor is None:
                anchor = v
                run_start_i = i
                continue
            cents = abs(1200.0 * np.log2(v / anchor))
            if cents > vp_detector.PITCH_TOLERANCE_CENTS:
                dur = times[i - 1] - times[run_start_i]
                if dur >= DEFAULT_SUSTAIN_S:
                    sustained.append(vp_detector._sustained_entry(times, f0_smooth, run_start_i, i - 1))
                anchor = v
                run_start_i = i
        if anchor is not None and idx[-1] > run_start_i:
            dur = times[idx[-1]] - times[run_start_i]
            if dur >= DEFAULT_SUSTAIN_S:
                sustained.append(vp_detector._sustained_entry(times, f0_smooth, run_start_i, idx[-1]))

    return {
        "vocal_phrases": phrases,
        "sustained_notes": sustained,
        "bridge_events": bridge_events,
        "params": {
            "bridge_max_gap_s": BRIDGE_MAX_GAP_S,
            "bridge_pitch_tolerance_cents": BRIDGE_PITCH_TOLERANCE_CENTS,
            "breath_s": DEFAULT_BREATH_S,
            "sustain_s": DEFAULT_SUSTAIN_S,
            "min_phrase_s": MIN_PHRASE_S,
        },
    }
