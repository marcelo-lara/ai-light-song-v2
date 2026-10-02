"""Phase 3 (relate) -- named gesture phases + section-pair transitions.

Replaces the whole `event_*` stack (`event_rules/`, `event_machine/`,
`event_features/`, `event_timeline.py`, `event_review.py`,
`event_identifiers.py`, `review_queue.py`), measured at chance against the
gold set (CLAUDE.md). Ported from `experiments/gestures/primitives.py` and
`assembly.py` after that experiment's own comparison there:

    | method                                       | +-0.25s | +-1.0s | events/min |
    | --------------------------------------------- | ------- | ------ | ---------- |
    | gesture impact phase (this stage, production) | 2/7     | 4/7    | 4.5-10.3   |
    | incumbent (song_event_timeline impact/drop)   | 0/7     | 2/7    | 1.5        |

    "events/min" above is per-song `impact`-type events only; combined with
    the other phases and section transitions this stage also emits, the full
    `song_event_timeline.json` stays under 20 events/min on all four gold
    songs (9.5-18.6/min measured). The detector thresholds below (all of them
    tuned on the gold set, not invented) are tighter than
    `experiments/gestures/primitives.py`'s defaults for exactly this reason:
    the experiment scored recall of the bare impact instants and reported
    "gestures/min" from the *impact* count alone, never the exploded
    per-phase event list this production stage has to keep under budget
    (the projection wants few high-value discrete events — docs/mcp-definition.md). The
    impact detector's own three constants (`_IMPACT_TRANSIENT_PERCENTILE`,
    `_IMPACT_SUB_PERCENTILE`, `_IMPACT_MIN_GAP_S`) sit at the loosest values
    that still clear the acceptance floor above — every value in the sweep
    tried past them dropped recall below 4/7 @ ±1.0s. The other detectors'
    thresholds (ramp, reverse-cymbal, pre-drop-gap, release) do not affect
    that recall number at all and were tightened much further purely to keep
    the emitted approach/build/tension/release volume down; exact duplicate
    phase spans reused by several nearby impacts (they share the same 16-bar
    lookback window) are also collapsed to one event rather than emitted once
    per gesture that reused them.

This stage reads ONLY phase-1/2 artifacts -- `fft_bands.json`,
`rms_loudness.json`, `drum_events.json`, the canonical timing grid
(`essentia/beats.json`) -- plus the PUBLISHED top-level `sections.json`
(v3.7 item 6; previously `artifacts/section_segmentation/sections.json`,
allin1's raw, coarser boundaries) -- and never opens the audio (phase 3
"relate" never touches audio). Reading the published table means this stage
now runs after `build-ui-data` in the full pipeline (moved there in v3.7 item
6 for exactly this reason — nothing downstream of `build-gestures` before
that point reads `song_event_timeline.json`, so the reorder is free).

Two kinds of named, timed thing are produced, both flattened into one event
list for `song_event_timeline.json`:

1. **Gesture phases** (`approach`, `build`, `tension`, `impact`, `release`).
   One detector per named sound-design device -- riser / downlifter (sliding-
   window linear regression on high-band energy), reverse cymbal (a rising
   mix-RMS ramp into a `transient_strength` spike), snare roll (per-bar onset-
   density doubling in `drum_events.json`), impact (simultaneous sub-band +
   transient spike, OR -- v3.9 item 4 -- a published section boundary where
   the bass and drums stems both enter within one beat, `detect_stem_entry_impacts`;
   this is the only primitive that reads `rms_loudness.json`'s raw per-stem
   frames rather than `fft_bands.json`), pre-drop gap (a `dropout_strength`
   spike immediately before an impact). Every impact's `start` is its onset,
   never a detector's peak instant -- `detect_impacts` keeps its transient
   peak as `peak_time`; a stem-entry impact has no separate peak, so the two
   are equal. `assemble_gestures` anchors each gesture on a detected
   impact and fills approach/build/tension/release from whichever primitives
   fall in the preceding window. **A phase with no supporting primitive is
   absent, never guessed** (no silent fallbacks — never guess to keep a run green). A drop is never detected or
   named directly -- this stage says "a build of this shape happens here", not
   "this is the drop" (a drop is derived from a named section pair, never detected).
2. **Section-pair transitions**, one per boundary in the published
   `sections.json` -- consecutive equal-labelled runs are already merged
   upstream, so every remaining boundary is a change in `function` (or, for
   two same-labelled non-adjacent runs, `same_label_as`); the transition is
   named `"<from> -> <to>"` and carries that row's own boundary `confidence`,
   never a re-detected instant of its own.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION, validate_field_sources
from analyzer.paths import SongPaths

#: Ordered sub-phases of a composite gesture (event_vocabulary.json).
PHASE_NAMES = ("approach", "build", "tension", "impact", "release")

_HIGH_BAND_IDX = (4, 5, 6)  # upper_mid, presence, brilliance
_SUB_BAND_IDX = 0

#: Detector selectivity. An "impact" must be a rare, structurally significant
#: moment (a handful per song), not every strong kick -- tuned on the gold set
#: so the combined event stream stays well under 20 events/min (input-guide
#: the projection wants few high-value discrete events) while keeping the measured impact-phase recall (module docstring
#: table). Raising these numbers trades recall for a shorter, higher-value
#: event list; the values below are the smallest that still clear the
#: acceptance floor on the four gold songs.
_IMPACT_TRANSIENT_PERCENTILE = 95.0
_IMPACT_SUB_PERCENTILE = 82.0
_IMPACT_MIN_GAP_S = 1.0

#: v3.9 item 4 -- an impact's reported `start` is the onset (first frame of
#: the rise leading to the transient peak), never the peak itself; `peak_time`
#: keeps the old instant. Walking back is capped at one beat so a preceding
#: riser or roll (a real, separate primitive) can never pull the onset into
#: its own span -- "how far starts moved" is reported in this item's checks.
_IMPACT_WALKBACK_MAX_BEATS = 1.0

#: v3.9 item 4 -- stem-entry impacts. A published section boundary where the
#: bass and drums stems both enter gets its own impact even when the FFT
#: transient detector above found nothing there (Rapture's 55.39s drop is the
#: loudest arrival in the song and produces no qualifying transient at all).
#: Every ratio is of each stem's OWN whole-song p95 (`rms_loudness.json`,
#: 10ms frames -- finer than the 20ms floor this item's plan text names, never
#: coarser). Values below are tuned against the gold corpus
#: (docs/analysis-definition.md); see the stage-4 hard-won-lessons note in
#: docs/issues.md history / commit message for the failure modes each guards:
#:   - a centered moving average over ON_RATIO/OFF_RATIO hysteresis finds
#:     *that* both stems turn on near the boundary -- SMOOTH_BEATS wide so a
#:     kick-only stem's between-hits dips don't reset the "on" state;
#:   - the smoothed crossing is never reported as the onset (it lags up to
#:     half a beat) -- it only anchors a raw-frame search window
#:     [-SEARCH_BACK_BEATS, +SEARCH_FWD_BARS] for the frame maximizing the
#:     jump in (bass+drums)/p95 from the previous beat to the next one
#:     (JUMP_MIN floor -- Queen of Kings' pre-drop riser/roll never clears it
#:     over a full bar-scale window the way a real entry does);
#:   - the onset itself is the first raw frame at/after that jump clearing
#:     ONSET_RATIO of drums' own p95 whose next SUSTAIN_BEATS never dips below
#:     SUSTAIN_RATIO -- a lone pre-drop stray hit (a hi-hat spike inside a
#:     riser) crashes back down within a beat and fails this, a real entry
#:     does not;
#:   - no qualifying frame anywhere in the search -> no impact, never guessed.
_STEM_ENTRY_ON_RATIO = 0.40
_STEM_ENTRY_OFF_RATIO = 0.25
_STEM_ENTRY_SMOOTH_BEATS = 1.0
_STEM_ENTRY_PAIR_MAX_BEATS = 1.0
_STEM_ENTRY_BOUNDARY_WINDOW_BARS = 1.0
_STEM_ENTRY_SEARCH_BACK_BEATS = 1.0
_STEM_ENTRY_SEARCH_FWD_BARS = 1.0
_STEM_ENTRY_JUMP_MIN = 0.6
_STEM_ENTRY_ONSET_RATIO = 0.5
_STEM_ENTRY_SUSTAIN_RATIO = 0.2
_STEM_ENTRY_SUSTAIN_BEATS = 0.5
#: An existing impact within this of the BOUNDARY means the drop already has
#: an impact accounted for -- never add a second one for the same event. A
#: transient-detector hit is routinely placed at its peak rather than the
#: physical onset (Rapture's 170.05s peak for a 169.83s onset, 220ms off, is
#: the motivating case for this whole item); that existing impact's `start` is
#: corrected in place to the more precisely stem-anchored onset (its old
#: `start` kept as `peak_time` if it did not already carry one) rather than
#: left stale -- physical onset wins over the grid (CLAUDE.md); a cue fired
#: late is a cue missed. `_STEM_ENTRY_CORRECTION_EPSILON_S` guards against a
#: no-op rewrite when the existing impact is already at the onset. Also used,
#: unscoped to any one boundary, as the floor below which a freshly computed
#: onset is never emitted as a NEW impact -- against every existing impact
#: and every stem-entry impact already emitted this call, so two
#: bar-spaced boundaries whose search windows overlap can't each
#: independently rediscover the same real hit as their own.
_STEM_ENTRY_DEDUP_S = 0.25
_STEM_ENTRY_CORRECTION_EPSILON_S = 0.02
#: "Stems entered first" is not sufficient evidence on its own to override an
#: existing impact -- a bass pickup + drum-fill hit ahead of the real downbeat
#: also clears the sustain check (Queen of Kings' 48.555s pickup before its
#: operator-reviewed 48.70s drop). Distinguish a pickup from a genuine
#: monotonic attack (Rapture's 169.845s onset -> its own peak) by shape, not
#: absolute strength: if the raw drums value, somewhere between the stem
#: onset and the existing impact, dips to a real trough and then climbs back
#: up again, that is a *separate* later hit -- the onset does not win. A
#: single hit's own attack only decays gently off its early peak (Rapture:
#: never drops below ~98% of its onset value in this span); a pickup-then-hit
#: has a real trough in between (Queen of Kings: dips to ~53% of the onset
#: value before recovering). Measured on the gold set, not the round number
#: it sits near -- a literal "half the onset value" (0.50) sits 3 points on
#: the wrong side of Queen of Kings' measured 0.529 trough, which would fail
#: to guard it; 0.6 clears that with room and is still far below Rapture's
#: 0.978 (never tuned past what the gold set needed -- CLAUDE.md, "tuned on
#: the gold set, not invented").
_STEM_ENTRY_TROUGH_RATIO = 0.6

#: v3.10 item 3 -- drums-led entries. The two-stem rule above needs bass AND
#: drums to cross their on-thresholds within one beat, and judges "on" by a
#: 1-beat rolling mean. Two real drops escape it: *Cinderella* 85.73s (a
#: drums-only entry, the bass stem a beat and a half later) and
#: *Charli-VonDutch* 29.85s (one ~50 ms kick per beat, whose rolling mean tops
#: out at 0.31x p95 against the 0.40x gate; a rolling *max* was tried and
#: regressed Titanium 151.445s and moved Rapture / Queen of Kings earlier).
#: This fallback runs only at a boundary the two-stem rule found nothing for.
#: Drums presence is HIT DENSITY on the raw frames, not a mean:
#:   - a hit is a raw-frame local maximum >= HIT_RATIO of the drums stem's
#:     own p95 (Charli's kicks peak at 0.96-1.51x p95, Cinderella's at
#:     1.05-1.11x; Charli's 29.55s stray ghost hit is 0.43x and never counts);
#:     hits closer than HIT_MIN_GAP_BEATS collapse to the first (one kick's
#:     own decay ripple);
#:   - the groove must be CONTINUOUS: no gap between consecutive hits inside
#:     the density window longer than MAX_GAP_BEATS. A lone pickup hit
#:     followed by a trough and then the real groove would otherwise borrow
#:     the groove's hits for its density (Charli-Guess 95.745s pickup, 3 beats
#:     of silence, real entry ~97.25s; genuine grooves here run 1 beat apart);
#:   - the drums are "on" from a hit when the next DENSITY_BEATS beats hold
#:     at least DENSITY_MIN hits per beat (Charli and Cinderella: 1 per beat,
#:     4 hits in 4 beats) and the PRIOR_BEATS beats before it hold no hit
#:     (both songs: complete silence before the entry, so this is a turn-on,
#:     not a continuing groove);
#:   - the bass then follows: its smoothed value clears its own on-threshold
#:     somewhere in the next FOLLOW_BARS bar and was below it the beat before
#:     the drums onset (Cinderella: ~1.5 beats after; Charli: ~4 beats);
#:   - the onset is the drums onset, walked back from the hit's peak to the
#:     first frame >= the shared `_STEM_ENTRY_ONSET_RATIO` (at most
#:     ONSET_BACK_BEATS), and it must lie within one bar of its own boundary;
#:   - the impact carries the fixed, deliberately modest FALLBACK_CONFIDENCE
#:     (below the two-stem case's 0.75 ceiling): there is no jump score here.
#: The v3.9 guards (0.25 s dedup against every impact, D4.1 trough guard on
#: an in-place correction) apply unchanged in the shared tail.
_DRUMS_LED_HIT_RATIO = 0.5
_DRUMS_LED_HIT_MIN_GAP_BEATS = 0.25
_DRUMS_LED_DENSITY_BEATS = 4.0
_DRUMS_LED_DENSITY_MIN = 0.75
_DRUMS_LED_PRIOR_BEATS = 2.0
_DRUMS_LED_MAX_GAP_BEATS = 1.5
_DRUMS_LED_FOLLOW_BARS = 1.0
_DRUMS_LED_ONSET_BACK_BEATS = 0.25
_DRUMS_LED_FALLBACK_CONFIDENCE = 0.5

#: Riser/downlifter: a near-monotonic ramp has to explain most of the
#: high-band range (not just a quarter of it) and fit tightly (r2) to count --
#: otherwise general loudness drift reads as a "riser" on every bar.
_RAMP_MIN_R2 = 0.75
_RAMP_MIN_DELTA = 0.5

_REVERSE_CYMBAL_TRANSIENT_PERCENTILE = 98.0
_REVERSE_CYMBAL_MIN_R2 = 0.85

_SNARE_ROLL_MIN_PREV_COUNT = 3
_SNARE_ROLL_START_RATIO = 2.0
_SNARE_ROLL_CONTINUE_RATIO = 1.6

_PRE_DROP_GAP_DROPOUT_PERCENTILE = 99.5

#: Release requires the mix to genuinely climb after the impact, not merely
#: fail to collapse -- otherwise almost any impact in an already-loud section
#: qualifies.
_RELEASE_MIN_RATIO = 1.15


# ---------------------------------------------------------------------------
# small numeric helpers
# ---------------------------------------------------------------------------


def _bar_length(beats: list[dict]) -> float:
    downbeat_times = [b["time"] for b in beats if b.get("type") == "downbeat"]
    if len(downbeat_times) > 1:
        return float(np.median(np.diff(downbeat_times)))
    return 2.0


def _beat_length(beats: list[dict]) -> float:
    times = sorted(b["time"] for b in beats)
    diffs = np.diff(times)
    return float(np.median(diffs)) if len(diffs) else 0.5


def _nearest_beat(beats: list[dict], t: float) -> dict | None:
    if not beats:
        return None
    times = np.array([b["time"] for b in beats])
    return beats[int(np.argmin(np.abs(times - t)))]


def _linreg(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Returns (slope, r_squared)."""
    if len(x) < 3 or np.std(y) < 1e-9:
        return 0.0, 0.0
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = np.sum((y - pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 0.0
    return float(slope), float(max(0.0, r2))


def _local_peaks(values: np.ndarray, threshold: float, *, min_gap: float, times: np.ndarray) -> list[tuple[float, float]]:
    above = values >= threshold
    peaks: list[tuple[float, float]] = []
    i, n = 0, len(values)
    last_t = -1e9
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            peak_idx = i + int(np.argmax(values[i:j]))
            t = float(times[peak_idx])
            if t - last_t >= min_gap:
                peaks.append((t, float(values[peak_idx])))
                last_t = t
            i = j
        else:
            i += 1
    return peaks


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


# ---------------------------------------------------------------------------
# primitive detectors -- one named sound-design device each
# ---------------------------------------------------------------------------


def detect_ramps(fft_levels: np.ndarray, fft_times: np.ndarray, beats: list[dict], *, kind: str) -> list[dict]:
    """Riser (`kind="riser"`, ascending) or downlifter (`kind="downlifter"`,
    descending) -- a near-monotonic ramp in high-band energy over a
    bar-multiple span. No chord change required."""
    high = fft_levels[:, _HIGH_BAND_IDX].mean(axis=1)
    bar_len = _bar_length(beats)
    span_range = max(high.max() - high.min(), 1e-6)
    sign = 1 if kind == "riser" else -1

    candidates = []
    for n_bars in (2, 4, 8, 16):
        window_s = n_bars * bar_len
        step_s = max(bar_len / 2.0, 0.25)
        t = fft_times[0]
        while t + window_s <= fft_times[-1]:
            idx = (fft_times >= t) & (fft_times < t + window_s)
            if idx.sum() >= 4:
                slope, r2 = _linreg(fft_times[idx], high[idx])
                delta = slope * window_s
                if sign * delta > 0 and r2 >= _RAMP_MIN_R2 and abs(delta) / span_range >= _RAMP_MIN_DELTA:
                    candidates.append({
                        "start": float(t), "end": float(t + window_s),
                        "r2": r2, "delta": abs(delta) / span_range, "n_bars": n_bars,
                    })
            t += step_s

    # Non-max suppression: keep the strongest (highest r2*delta) among overlaps.
    candidates.sort(key=lambda c: c["r2"] * c["delta"], reverse=True)
    kept: list[dict] = []
    for c in candidates:
        if any(not (c["end"] <= k["start"] or c["start"] >= k["end"]) for k in kept):
            continue
        kept.append(c)
    kept.sort(key=lambda c: c["start"])

    out = []
    for c in kept:
        anchor = _nearest_beat(beats, c["end"] if kind == "riser" else c["start"])
        out.append({
            "type": kind,
            "start": round(c["start"], 3),
            "end": round(c["end"], 3),
            "confidence": round(min(1.0, c["r2"] * (0.5 + 0.5 * min(1.0, c["delta"]))), 3),
            "intensity": round(min(1.0, c["delta"]), 3),
            "anchor_bar": anchor["bar"] if anchor else None,
            "evidence": f"high-band r2={c['r2']:.2f} over {c['n_bars']} bars, delta={c['delta']:.2f}x range",
        })
    return out


def detect_reverse_cymbal(fft_levels: np.ndarray, fft_times: np.ndarray, fft_transient: np.ndarray, rms_times: np.ndarray, rms_mix: np.ndarray | None, beats: list[dict]) -> list[dict]:
    """Amplitude ramp terminating in a transient -- envelope rising into a
    `transient_strength` spike."""
    if rms_mix is None or len(fft_transient) == 0:
        return []
    thresh = np.percentile(fft_transient, _REVERSE_CYMBAL_TRANSIENT_PERCENTILE)
    peaks = _local_peaks(fft_transient, thresh, min_gap=1.0, times=fft_times)
    out = []
    for peak_t, strength in peaks:
        lookback = 3.0
        rms_idx = (rms_times >= peak_t - lookback) & (rms_times <= peak_t)
        if rms_idx.sum() < 4:
            continue
        slope, r2 = _linreg(rms_times[rms_idx], rms_mix[rms_idx])
        if slope > 0 and r2 >= _REVERSE_CYMBAL_MIN_R2:
            start = float(rms_times[rms_idx][0])
            anchor = _nearest_beat(beats, peak_t)
            out.append({
                "type": "reverse_cymbal",
                "start": round(start, 3),
                "end": round(float(peak_t), 3),
                "confidence": round(min(1.0, r2 * min(1.0, strength / max(thresh, 1e-6))), 3),
                "intensity": round(min(1.0, strength / max(thresh, 1e-6)), 3),
                "anchor_bar": anchor["bar"] if anchor else None,
                "evidence": f"mix-RMS rise r2={r2:.2f} into transient={strength:.2f}",
            })
    return out


def detect_snare_roll(drum_events: list[dict], beats: list[dict]) -> list[dict]:
    """Onset density from `drum_events.json` doubling across consecutive bars."""
    bars = sorted({b["bar"] for b in beats})
    if len(bars) < 3:
        return []
    bar_times: dict[int, float] = {}
    for b in beats:
        if b["bar"] not in bar_times or b["beat_in_bar"] == 1:
            bar_times[b["bar"]] = b["time"]
    bar_end = {bars[i]: bar_times.get(bars[i + 1], bar_times[bars[i]] + 2.0) for i in range(len(bars) - 1)}
    bar_end[bars[-1]] = bar_times[bars[-1]] + 2.0

    # "crash" is a v3.4 brilliance-gated split of pitch-42 hat events; it still
    # contributes onset density to a fill, so keep it in this set.
    snare_hat_times = sorted(e["time"] for e in drum_events if e.get("event_type") in ("snare", "hat", "crash"))
    counts: dict[int, int] = {}
    for bar in bars:
        t0, t1 = bar_times[bar], bar_end[bar]
        counts[bar] = sum(1 for t in snare_hat_times if t0 <= t < t1)

    out = []
    i = 1
    while i < len(bars):
        prev_bar, cur_bar = bars[i - 1], bars[i]
        prev_c, cur_c = counts[prev_bar], counts[cur_bar]
        if prev_c >= _SNARE_ROLL_MIN_PREV_COUNT and cur_c >= _SNARE_ROLL_START_RATIO * prev_c:
            j = i
            while j + 1 < len(bars) and counts[bars[j + 1]] >= _SNARE_ROLL_CONTINUE_RATIO * counts[bars[j]] and counts[bars[j]] > 0:
                j += 1
            start_bar, end_bar = bars[i - 1], bars[min(j + 1, len(bars) - 1)]
            ratio = counts[bars[j]] / max(prev_c, 1)
            anchor = _nearest_beat(beats, bar_end[end_bar])
            out.append({
                "type": "snare_roll",
                "start": round(bar_times[start_bar], 3),
                "end": round(bar_end[end_bar], 3),
                "confidence": round(min(1.0, (ratio - 1.0)), 3),
                "intensity": round(min(1.0, ratio - 1.0), 3),
                "anchor_bar": anchor["bar"] if anchor else None,
                "evidence": f"onset density {prev_c}->{counts[bars[j]]} across bars {start_bar}-{end_bar}",
            })
            i = j + 2
        else:
            i += 1
    return out


def detect_impacts(fft_levels: np.ndarray, fft_times: np.ndarray, fft_transient: np.ndarray, beats: list[dict]) -> list[dict]:
    """Simultaneous sub and brilliance transient -- the crash-and-sub hit that
    lands a gesture's impact.

    `start` is the onset, not the transient peak (v3.9 item 4 -- a cue fired
    late is a cue missed): walk back from the peak while the transient stays
    *strictly* above its own threshold, capped at `_IMPACT_WALKBACK_MAX_BEATS`
    so a preceding riser or roll can never pull the onset into its own span.
    The peak itself is kept as `peak_time`. Confidence logic is unchanged --
    it is still keyed on the peak's magnitude and downbeat alignment."""
    if len(fft_transient) == 0:
        return []
    t_thresh = np.percentile(fft_transient, _IMPACT_TRANSIENT_PERCENTILE)
    sub = fft_levels[:, _SUB_BAND_IDX]
    sub_thresh = np.percentile(sub, _IMPACT_SUB_PERCENTILE)
    peaks = _local_peaks(fft_transient, t_thresh, min_gap=_IMPACT_MIN_GAP_S, times=fft_times)
    max_walkback_s = _IMPACT_WALKBACK_MAX_BEATS * _beat_length(beats)
    out = []
    for peak_t, strength in peaks:
        idx = int(np.argmin(np.abs(fft_times - peak_t)))
        window = slice(max(0, idx - 2), idx + 3)
        if sub[window].max() < sub_thresh:
            continue
        onset_idx = idx
        while (
            onset_idx > 0
            and fft_transient[onset_idx - 1] > t_thresh
            and (peak_t - fft_times[onset_idx - 1]) <= max_walkback_s
        ):
            onset_idx -= 1
        onset_t = float(fft_times[onset_idx])
        anchor = _nearest_beat(beats, onset_t)
        on_downbeat = anchor is not None and anchor.get("type") == "downbeat"
        magnitude = min(1.0, strength / max(t_thresh, 1e-6))
        out.append({
            "type": "impact",
            "start": round(onset_t, 3),
            "peak_time": round(float(peak_t), 3),
            "end": round(onset_t, 3),
            "confidence": round(magnitude * (1.0 if on_downbeat else 0.75), 3),
            "intensity": round(magnitude, 3),
            "anchor_bar": anchor["bar"] if anchor else None,
            "on_downbeat": on_downbeat,
            "evidence": (
                f"transient={strength:.2f} at peak {peak_t:.3f}s (onset {onset_t:.3f}s), "
                f"sub-band elevated, {'on' if on_downbeat else 'off'} downbeat"
            ),
        })
    return out


def detect_stem_entry_impacts(
    rms_loudness: dict,
    beats: list[dict],
    sections: list[dict],
    existing_impacts: list[dict],
) -> list[dict]:
    """A published section boundary where the bass and drums stems both enter
    (cross from below to above their own on-threshold, within one beat of
    each other) gets its own impact even when `detect_impacts` above found no
    qualifying transient there. See the `_STEM_ENTRY_*` constants' docstring
    for the algorithm and why each step exists. Never guessed: no qualifying
    boundary emits nothing, silently."""
    rms_sources = rms_loudness.get("sources", [])
    rms_ids = [s["id"] for s in rms_sources]
    rms_frames = rms_loudness.get("frames", [])
    if "bass" not in rms_ids or "drums" not in rms_ids or not rms_frames or not sections:
        return []
    bass_col, drums_col = rms_ids.index("bass"), rms_ids.index("drums")
    rms_times = np.array([f["time"] for f in rms_frames])
    bass_raw = np.array([f["values"][bass_col] for f in rms_frames])
    drums_raw = np.array([f["values"][drums_col] for f in rms_frames])

    beat_len = _beat_length(beats)
    bar_len = _bar_length(beats)
    if beat_len <= 0 or len(rms_times) < 2:
        return []
    frame_dt = float(np.median(np.diff(rms_times)))
    if frame_dt <= 0:
        return []

    bass_p95 = float(np.percentile(bass_raw, 95))
    drums_p95 = float(np.percentile(drums_raw, 95))
    if bass_p95 <= 0 or drums_p95 <= 0:
        return []

    smooth_window = max(1, int(round(_STEM_ENTRY_SMOOTH_BEATS * beat_len / frame_dt)))
    bass_smooth = _centered_moving_average(bass_raw, smooth_window)
    drums_smooth = _centered_moving_average(drums_raw, smooth_window)
    bass_on, bass_off = _STEM_ENTRY_ON_RATIO * bass_p95, _STEM_ENTRY_OFF_RATIO * bass_p95
    drums_on, drums_off = _STEM_ENTRY_ON_RATIO * drums_p95, _STEM_ENTRY_OFF_RATIO * drums_p95

    beat_frames = max(1, int(round(beat_len / frame_dt)))
    sustain_frames = max(1, int(round(_STEM_ENTRY_SUSTAIN_BEATS * beat_len / frame_dt)))
    onset_back_frames = max(1, beat_frames // 4)

    def _two_stem_entry(boundary_time: float, lo_idx: int, hi_idx: int) -> tuple[int, float] | None:
        """The v3.9 rule: bass and drums both cross their on-thresholds
        within one beat -> (raw onset frame, jump score), else None."""
        bass_crossings = _off_to_on_crossings(bass_smooth, rms_times, bass_on, bass_off, lo_idx, hi_idx)
        drums_crossings = _off_to_on_crossings(drums_smooth, rms_times, drums_on, drums_off, lo_idx, hi_idx)
        if not bass_crossings or not drums_crossings:
            return None
        # The earliest pair of (bass, drums) crossings within one beat of
        # each other; anchored on the LATER of the pair -- the point both
        # stems are confirmed on together, not a lone stem's own (possibly
        # much earlier, e.g. a slow separate riser) crossing.
        anchor = None
        for bt in bass_crossings:
            for dt in drums_crossings:
                if abs(bt - dt) <= _STEM_ENTRY_PAIR_MAX_BEATS * beat_len:
                    candidate = max(bt, dt)
                    if anchor is None or candidate < anchor:
                        anchor = candidate
        if anchor is None:
            return None

        search_lo = int(np.searchsorted(rms_times, anchor - _STEM_ENTRY_SEARCH_BACK_BEATS * beat_len))
        search_hi = int(np.searchsorted(rms_times, anchor + _STEM_ENTRY_SEARCH_FWD_BARS * bar_len))
        best_idx, best_score = None, -1e9
        for i in range(max(search_lo, beat_frames), min(search_hi, len(rms_times) - beat_frames)):
            prev, nxt = slice(i - beat_frames, i), slice(i, i + beat_frames)
            score = (
                (np.mean(bass_raw[nxt]) / bass_p95 + np.mean(drums_raw[nxt]) / drums_p95)
                - (np.mean(bass_raw[prev]) / bass_p95 + np.mean(drums_raw[prev]) / drums_p95)
            )
            if score > best_score:
                best_score, best_idx = score, i
        if best_idx is None or best_score < _STEM_ENTRY_JUMP_MIN:
            return None

        for i in range(max(best_idx - onset_back_frames, 0), min(best_idx + beat_frames, len(rms_times))):
            if drums_raw[i] < _STEM_ENTRY_ONSET_RATIO * drums_p95:
                continue
            follow = slice(i, min(i + sustain_frames, len(rms_times)))
            if np.min(drums_raw[follow]) >= _STEM_ENTRY_SUSTAIN_RATIO * drums_p95:
                return i, float(best_score)
        return None

    hit_level = _DRUMS_LED_HIT_RATIO * drums_p95
    hit_min_gap = max(1, int(round(_DRUMS_LED_HIT_MIN_GAP_BEATS * beat_frames)))
    hit_indices = _drum_hit_indices(drums_raw, hit_level, hit_min_gap)
    density_frames = _DRUMS_LED_DENSITY_BEATS * beat_frames
    prior_frames = _DRUMS_LED_PRIOR_BEATS * beat_frames
    max_gap_frames = _DRUMS_LED_MAX_GAP_BEATS * beat_frames
    follow_frames = int(round(_DRUMS_LED_FOLLOW_BARS * bar_len / frame_dt))
    led_back_frames = max(1, int(round(_DRUMS_LED_ONSET_BACK_BEATS * beat_frames)))

    def _drums_led_entry(boundary_time: float) -> tuple[int, float] | None:
        """v3.10 item 3 -- a drums-led entry near `boundary_time` (see the
        `_DRUMS_LED_*` constants): the first qualifying hit within one bar of
        the boundary -> (raw onset frame, hit peak / drums p95), else None."""
        window = _STEM_ENTRY_BOUNDARY_WINDOW_BARS * bar_len
        for h in hit_indices:
            if abs(float(rms_times[h]) - boundary_time) > window:
                continue
            n_ahead = int(np.sum((hit_indices >= h) & (hit_indices < h + density_frames)))
            n_prior = int(np.sum((hit_indices >= h - prior_frames) & (hit_indices < h)))
            if n_ahead / _DRUMS_LED_DENSITY_BEATS < _DRUMS_LED_DENSITY_MIN:
                continue
            if n_prior / _DRUMS_LED_PRIOR_BEATS > 0.0:
                continue
            in_window = hit_indices[(hit_indices >= h) & (hit_indices < h + density_frames)]
            if np.any(np.diff(in_window) > max_gap_frames):
                continue
            onset = h
            while (
                onset > 0
                and h - onset < led_back_frames
                and drums_raw[onset - 1] >= _STEM_ENTRY_ONSET_RATIO * drums_p95
                and drums_raw[onset - 1] <= drums_raw[onset]
            ):
                onset -= 1
            # Bass follows within a bar, and was not already on before the drums.
            after = slice(onset, min(onset + follow_frames + 1, len(rms_times)))
            if not np.any(bass_smooth[after] >= bass_on):
                continue
            before = slice(max(0, onset - beat_frames), onset + 1)
            if np.any(bass_smooth[before] >= bass_on):
                continue
            return onset, float(drums_raw[h] / drums_p95)
        return None

    out = []
    for section in sections[1:]:
        boundary_time = float(section["start"])
        lo_idx = int(np.searchsorted(rms_times, boundary_time - _STEM_ENTRY_BOUNDARY_WINDOW_BARS * bar_len))
        hi_idx = int(np.searchsorted(rms_times, boundary_time + _STEM_ENTRY_BOUNDARY_WINDOW_BARS * bar_len))
        if hi_idx <= lo_idx:
            continue

        primary = _two_stem_entry(boundary_time, lo_idx, hi_idx)
        if primary is not None:
            onset_idx, best_score = primary
            entry_kind = "two-stem"
            evidence_tail = (
                f"bass+drums both on within {_STEM_ENTRY_PAIR_MAX_BEATS:.0f} beat, jump score {best_score:.2f}"
            )
            confidence = round(min(1.0, best_score / max(_STEM_ENTRY_JUMP_MIN, 1e-6) * 0.75), 3)
            intensity = round(min(1.0, best_score), 3)
        else:
            led = _drums_led_entry(boundary_time)
            if led is None:
                continue
            onset_idx, peak_ratio = led
            entry_kind = "drums-led"
            evidence_tail = (
                f"drums-led, hit density >= {_DRUMS_LED_DENSITY_MIN:g}/beat then bass within "
                f"{_DRUMS_LED_FOLLOW_BARS:.0f} bar (hit {peak_ratio:.2f}x drums p95)"
            )
            confidence = _DRUMS_LED_FALLBACK_CONFIDENCE
            intensity = round(min(1.0, peak_ratio), 3)
        onset_time = float(rms_times[onset_idx])
        # An onset this far from the boundary it was searched from does not
        # belong to it -- it belongs to whichever (closer) boundary it is
        # actually the entry for (Queen of Kings' 48.555s onset, found while
        # searching from the 46.82s boundary 1.735s away, really belongs to
        # the 48.72s boundary 0.165s away). Bars, not the pairing's own
        # one-beat tolerance: Titanium's real onset legitimately sits 0.985s
        # (~2 beats, ~0.52 bar) past its 150.46s boundary -- a literal
        # one-beat cap would silently drop that verified case, so this reuses
        # the same one-bar radius the crossing search itself is bounded to.
        if abs(onset_time - boundary_time) > _STEM_ENTRY_BOUNDARY_WINDOW_BARS * bar_len:
            continue

        nearby = [e for e in existing_impacts if abs(float(e["start"]) - boundary_time) <= _STEM_ENTRY_DEDUP_S]
        if nearby:
            # The drop already has an impact -- never add a second one for
            # the same event. Refine it in place to the stem-anchored onset
            # unless it is already there in all but name.
            closest = min(nearby, key=lambda e: abs(float(e["start"]) - onset_time))
            existing_start = float(closest["start"])
            moved_enough = abs(existing_start - onset_time) > _STEM_ENTRY_CORRECTION_EPSILON_S
            # Guard (v3.9 item 4 follow-up): "stems entered first" is not
            # enough on its own -- a bass pickup + drum-fill hit ahead of the
            # real downbeat (Queen of Kings' 48.555s before its true 48.70s
            # drop) also clears the sustain check above. Only move the
            # existing impact when there is no recovering trough between the
            # onset and it -- a real trough (drums dips well below the
            # onset's own level, then climbs back up again) means a separate,
            # later hit exists in between, and the onset is the pickup, not
            # the drop.
            no_trough = not moved_enough or not _has_recovering_trough(
                drums_raw, rms_times, onset_idx, existing_start, _STEM_ENTRY_TROUGH_RATIO
            )
            if moved_enough and no_trough:
                if closest.get("peak_time") is None:
                    closest["peak_time"] = closest["start"]
                closest["evidence"] = (
                    f"{closest['evidence']}; corrected to stem entry onset {onset_time:.3f}s "
                    f"({evidence_tail})"
                )
                closest["start"] = round(onset_time, 3)
                closest["end"] = round(onset_time, 3)
            continue

        # Never emit within the dedup floor of ANY existing impact -- not
        # only ones near this boundary -- so two boundaries whose search
        # windows overlap (bar-spaced boundaries are less than two bar
        # lengths apart) can't each independently rediscover the same real
        # hit and emit near-duplicates for it.
        all_prior_starts = [float(e["start"]) for e in existing_impacts] + [float(e["start"]) for e in out]
        if any(abs(onset_time - t) <= _STEM_ENTRY_DEDUP_S for t in all_prior_starts):
            continue

        anchor_beat = _nearest_beat(beats, onset_time)
        out.append({
            "type": "impact",
            "start": round(onset_time, 3),
            "peak_time": round(onset_time, 3),
            "end": round(onset_time, 3),
            "confidence": confidence,
            "intensity": intensity,
            "anchor_bar": anchor_beat["bar"] if anchor_beat else None,
            "on_downbeat": bool(anchor_beat and anchor_beat.get("type") == "downbeat"),
            "evidence": f"stem entry at section boundary {boundary_time:.2f}s: {evidence_tail}",
        })
    return out


def _drum_hit_indices(drums_raw: np.ndarray, level: float, min_gap: int) -> np.ndarray:
    """Frame indices of raw-frame local maxima at/above `level`, later ones
    within `min_gap` frames of an accepted hit dropped (one kick's own decay
    ripple). Hit *density* over these is how `_DRUMS_LED_*` judges drums
    presence -- short sparse kicks count, unlike a rolling mean."""
    hits: list[int] = []
    n = len(drums_raw)
    for i in range(1, n - 1):
        if drums_raw[i] < level or drums_raw[i] < drums_raw[i - 1] or drums_raw[i] < drums_raw[i + 1]:
            continue
        if hits and i - hits[-1] < min_gap:
            continue
        hits.append(i)
    return np.array(hits, dtype=int)


def _centered_moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return values.copy()
    kernel = np.ones(window) / window
    padded = np.pad(values, (window // 2, window - 1 - window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def _off_to_on_crossings(
    smoothed: np.ndarray, times: np.ndarray, on: float, off: float, lo_idx: int, hi_idx: int
) -> list[float]:
    """Every below-`off` -> at/above-`on` transition in `[lo_idx, hi_idx]`.
    Never reported as the onset itself -- a centered moving average lags the
    true onset by up to half a smoothing window; this only locates the
    region a raw-frame search should refine."""
    out: list[float] = []
    was_off = True
    capped_hi = min(hi_idx, len(smoothed) - 1)
    for i in range(max(lo_idx, 1), capped_hi + 1):
        if smoothed[i - 1] < off:
            was_off = True
        if was_off and smoothed[i - 1] < on <= smoothed[i]:
            out.append(float(times[i]))
            was_off = False
    return out


def _has_recovering_trough(
    drums_raw: np.ndarray, rms_times: np.ndarray, onset_idx: int, other_time: float, trough_ratio: float
) -> bool:
    """True when the raw drums value, somewhere strictly between `onset_idx`
    and `other_time`, dips below `trough_ratio` of the onset's own value and
    then climbs back above that floor again -- a real trough, meaning a
    separate later hit exists in between (see `_STEM_ENTRY_TROUGH_RATIO`).
    A single hit's own attack decay does not do this; it only ever eases off
    its early peak."""
    onset_value = float(drums_raw[onset_idx])
    if onset_value <= 0:
        return False
    other_idx = int(np.searchsorted(rms_times, other_time))
    lo, hi = sorted((onset_idx, other_idx))
    trough_thresh = trough_ratio * onset_value
    dipped = False
    for i in range(lo, hi + 1):
        if i == onset_idx:
            continue
        if not dipped and drums_raw[i] < trough_thresh:
            dipped = True
        elif dipped and drums_raw[i] >= trough_thresh:
            return True
    return False


def detect_pre_drop_gaps(fft_times: np.ndarray, fft_dropout: np.ndarray, impacts: list[dict], beats: list[dict]) -> list[dict]:
    """One to two beats of near-silence immediately before an impact -- a
    `dropout_strength` spike / broadband RMS collapse."""
    if len(fft_dropout) == 0:
        return []
    d_thresh = np.percentile(fft_dropout, _PRE_DROP_GAP_DROPOUT_PERCENTILE)
    out = []
    for imp in impacts:
        window = (fft_times >= imp["start"] - 2.0) & (fft_times < imp["start"])
        if not window.any():
            continue
        seg_times = fft_times[window]
        seg_dropout = fft_dropout[window]
        if seg_dropout.max() < d_thresh:
            continue
        peak_i = int(np.argmax(seg_dropout))
        peak_t = float(seg_times[peak_i])
        half_thresh = np.percentile(seg_dropout, 50)
        lo = peak_i
        while lo > 0 and seg_dropout[lo - 1] >= half_thresh:
            lo -= 1
        hi = peak_i
        while hi < len(seg_dropout) - 1 and seg_dropout[hi + 1] >= half_thresh:
            hi += 1
        anchor = _nearest_beat(beats, peak_t)
        magnitude = min(1.0, float(seg_dropout[peak_i]) / max(d_thresh, 1e-6))
        out.append({
            "type": "pre_drop_gap",
            "start": round(float(seg_times[lo]), 3),
            "end": round(float(imp["start"]), 3),
            "confidence": round(magnitude, 3),
            "intensity": round(magnitude, 3),
            "anchor_bar": anchor["bar"] if anchor else None,
            "evidence": f"dropout_strength peak {seg_dropout[peak_i]:.2f} at {peak_t:.2f}s, {imp['start']-peak_t:.2f}s before impact",
        })
    return out


# ---------------------------------------------------------------------------
# assembly -- named phases anchored on a detected impact
# ---------------------------------------------------------------------------


def assemble_gestures(
    impacts: list[dict],
    ramps: list[dict],
    reverse_cymbals: list[dict],
    snare_rolls: list[dict],
    pre_drop_gaps: list[dict],
    beats: list[dict],
    rms_mix_times: np.ndarray,
    rms_mix_values: np.ndarray | None,
) -> list[dict]:
    """Anchor each detected impact and fill approach/build/tension/release
    from whichever primitives fall in the preceding window. A phase with no
    supporting primitive is simply absent -- never guessed (no silent fallbacks — never guess to keep a run green).
    Returns a list of gestures, each `{"impact_time", "phases": {name: {...}}}`.
    """
    bar_len = _bar_length(beats)
    gestures = []
    for gesture_index, impact in enumerate(impacts, start=1):
        t_impact = impact["start"]
        window_start = t_impact - 16 * bar_len

        def in_window(p: dict) -> bool:
            return window_start <= p["end"] <= t_impact + 0.1

        near_ramps = sorted((p for p in ramps if in_window(p)), key=lambda p: p["end"])
        near_gap = next((g for g in pre_drop_gaps if abs(g["end"] - t_impact) <= 0.15), None)
        near_cymbal = sorted((c for c in reverse_cymbals if in_window(c)), key=lambda c: c["end"])
        near_roll = sorted((r for r in snare_rolls if in_window(r)), key=lambda r: r["end"])

        phases: dict[str, dict] = {}

        if near_gap:
            phases["tension"] = {
                "start": near_gap["start"], "end": near_gap["end"],
                "confidence": near_gap["confidence"], "intensity": near_gap["intensity"],
                "from": "pre_drop_gap", "evidence": near_gap["evidence"],
            }
        elif near_cymbal and t_impact - near_cymbal[-1]["end"] <= bar_len:
            c = near_cymbal[-1]
            phases["tension"] = {
                "start": c["start"], "end": c["end"],
                "confidence": c["confidence"], "intensity": c["intensity"],
                "from": "reverse_cymbal", "evidence": c["evidence"],
            }

        tension_start = phases["tension"]["start"] if "tension" in phases else t_impact

        build_candidates = [p for p in near_ramps if p["end"] <= tension_start + 0.2 and p["type"] == "riser"]
        build_candidates += [r for r in near_roll if r["end"] <= tension_start + 0.2]
        if build_candidates:
            build_candidates.sort(key=lambda p: p["end"])
            b = build_candidates[-1]
            phases["build"] = {
                "start": b["start"], "end": b["end"],
                "confidence": b["confidence"], "intensity": b["intensity"],
                "from": b["type"], "evidence": b["evidence"],
            }

        build_start = phases["build"]["start"] if "build" in phases else tension_start

        approach_candidates = [p for p in near_ramps if p["end"] <= build_start + 0.2]
        if approach_candidates:
            approach_candidates.sort(key=lambda p: p["end"])
            a = approach_candidates[-1]
            if a["end"] <= build_start + 0.2 and a["start"] < build_start:
                phases["approach"] = {
                    "start": a["start"], "end": a["end"],
                    "confidence": a["confidence"], "intensity": a["intensity"],
                    "from": a["type"], "evidence": a["evidence"],
                }

        phases["impact"] = {
            "start": t_impact, "end": t_impact,
            "confidence": impact["confidence"], "intensity": impact["intensity"],
            "from": "impact", "evidence": impact["evidence"],
            # v3.9 item 4 -- `start`/`t_impact` is the onset; `peak_time` keeps
            # the transient's own peak instant (equal to the onset for a
            # stem-entry impact, which has no separate transient peak).
            "peak_time": impact.get("peak_time", t_impact),
        }

        # Release: does the mix RMS stay elevated (above its own pre-impact
        # level) for the 2 bars after the impact? If not, omit -- never guess.
        if rms_mix_values is not None:
            post_idx = (rms_mix_times >= t_impact) & (rms_mix_times <= t_impact + 2 * bar_len)
            pre_idx = (rms_mix_times >= t_impact - bar_len) & (rms_mix_times < t_impact)
            if post_idx.any() and pre_idx.any():
                post_level = float(np.median(rms_mix_values[post_idx]))
                pre_level = float(np.median(rms_mix_values[pre_idx]))
                if post_level >= pre_level * _RELEASE_MIN_RATIO:
                    conf = float(np.clip((post_level - pre_level) / max(pre_level, 1e-6), 0.0, 1.0))
                    phases["release"] = {
                        "start": t_impact, "end": round(t_impact + 2 * bar_len, 3),
                        "confidence": round(0.5 + 0.5 * conf, 3), "intensity": round(conf, 3),
                        "from": "post-impact RMS plateau",
                        "evidence": f"post-impact mix-RMS median {post_level:.4f} vs pre-impact {pre_level:.4f}",
                    }

        gestures.append({"gesture_id": f"gesture-{gesture_index:03d}", "impact_time": round(t_impact, 3), "phases": phases})
    return gestures


# ---------------------------------------------------------------------------
# section-pair transitions
# ---------------------------------------------------------------------------


def detect_section_transitions(sections: list[dict]) -> list[dict]:
    """One event per boundary in the published `sections.json` (`sections`
    here is that table's own `sections` list -- v3.7 item 6, previously the
    raw `artifacts/section_segmentation/sections.json`).

    Consecutive equal-labelled phrase runs are already merged upstream
    (`merge_equal_labelled_runs`), so every remaining boundary is already a
    change in `function` -- this never re-detects the boundary instant, it
    only names it. The section's own boundary `confidence` carries over
    unchanged; this stage adds no independent opinion about whether the
    boundary is real."""
    transitions = []
    for i in range(1, len(sections)):
        prev_section = sections[i - 1]
        section = sections[i]
        from_label = str(prev_section.get("function") or "unknown")
        to_label = str(section.get("function") or "unknown")
        boundary_time = float(section["start"])
        unverified = section.get("function_status") == "unknown"
        transitions.append({
            "type": f"{from_label} → {to_label}",
            "start_time": boundary_time,
            "end_time": boundary_time,
            "confidence": round(float(section.get("confidence", 0.5)), 6),
            "section_id": section.get("section_id"),
            "section_name": section.get("function"),
            "summary": (
                f"The song moves from {from_label} into {to_label} here"
                + (" (the new section's name is unverified)." if unverified else ".")
            ),
            "evidence_summary": (
                f"allin1 section boundary: function changes from '{from_label}' to '{to_label}' "
                f"(boundary confidence {section.get('confidence', 0.5):.2f})."
            ),
        })
    return transitions


# ---------------------------------------------------------------------------
# top-level stage entry point
# ---------------------------------------------------------------------------

_PHASE_SUMMARIES = {
    "approach": "An early {from_} begins shaping the run-up toward the impact at {impact:.2f}s.",
    "build": "A rising {from_} builds toward the impact at {impact:.2f}s.",
    "tension": "A {from_} holds tension immediately before the impact at {impact:.2f}s.",
    "impact": "An impact lands here (simultaneous sub-band and transient spike{downbeat_note}).",
    "release": "The mix stays elevated after the impact at {impact:.2f}s, sustaining the release.",
}


def _phase_summary(phase_name: str, phase: dict, impact_time: float) -> str:
    from_label = str(phase.get("from", "")).replace("_", " ")
    if phase_name == "impact":
        note = " on the downbeat" if phase.get("on_downbeat") else ""
        return _PHASE_SUMMARIES["impact"].format(downbeat_note=note)
    return _PHASE_SUMMARIES[phase_name].format(from_=from_label, impact=impact_time)


def build_gestures(
    paths: SongPaths,
    fft_bands: dict,
    rms_loudness: dict,
    drum_events: dict,
    timing: dict,
    sections_payload: dict,
) -> dict:
    """Detect named sound-design primitives, assemble them into gesture
    phases anchored on detected impacts, add one event per section-pair
    transition, and write the merged, flat event list to
    `song_event_timeline.json`. Reads only phase-1/2 artifacts plus the
    published `sections.json`, never audio. `sections_payload` must be the
    PUBLISHED table (v3.7 item 6) -- see module docstring."""
    frames = fft_bands.get("frames", [])
    fft_times = np.array([f["time"] for f in frames]) if frames else np.array([])
    fft_levels = np.array([f["levels"] for f in frames]) if frames else np.zeros((0, 7))
    fft_transient = np.array([f["transient_strength"] for f in frames]) if frames else np.array([])
    fft_dropout = np.array([f["dropout_strength"] for f in frames]) if frames else np.array([])

    rms_sources = rms_loudness.get("sources", [])
    rms_ids = [s["id"] for s in rms_sources]
    rms_frames = rms_loudness.get("frames", [])
    rms_times = np.array([f["time"] for f in rms_frames]) if rms_frames else np.array([])
    rms_mix = None
    if "mix" in rms_ids and rms_frames:
        mix_index = rms_ids.index("mix")
        rms_mix = np.array([f["values"][mix_index] for f in rms_frames])

    beats = timing.get("beats", [])
    sections = sections_payload.get("sections", [])
    events_list = drum_events.get("events", [])

    events: list[dict[str, Any]] = []

    if len(fft_times) > 0:
        risers = detect_ramps(fft_levels, fft_times, beats, kind="riser")
        downlifters = detect_ramps(fft_levels, fft_times, beats, kind="downlifter")
        reverse_cymbals = detect_reverse_cymbal(fft_levels, fft_times, fft_transient, rms_times, rms_mix, beats)
        snare_rolls = detect_snare_roll(events_list, beats)
        impacts = detect_impacts(fft_levels, fft_times, fft_transient, beats)
        pre_drop_gaps = detect_pre_drop_gaps(fft_times, fft_dropout, impacts, beats)

        # v3.9 item 4 -- a published section boundary where bass+drums both
        # enter gets its own impact even where the transient detector above
        # found nothing (or placed one imprecisely, corrected in place by
        # this call -- see `detect_stem_entry_impacts`'s docstring).
        stem_entry_impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, impacts)
        impacts = sorted(impacts + stem_entry_impacts, key=lambda i: i["start"])

        gestures = assemble_gestures(
            impacts, risers + downlifters, reverse_cymbals, snare_rolls, pre_drop_gaps,
            beats, rms_times, rms_mix,
        )

        for gesture in gestures:
            impact_time = gesture["impact_time"]
            section = _section_for_time(impact_time, sections)
            for phase_name in PHASE_NAMES:
                phase = gesture["phases"].get(phase_name)
                if phase is None:
                    continue
                phase_section = _section_for_time(float(phase["start"]), sections) or section
                event: dict[str, Any] = {
                    "type": phase_name,
                    "start_time": round(float(phase["start"]), 6),
                    "end_time": round(float(max(phase["end"], phase["start"])), 6),
                    "confidence": round(float(phase["confidence"]), 6),
                    "intensity": round(float(phase["intensity"]), 6),
                    "section_id": phase_section.get("section_id") if phase_section else None,
                    "section_name": phase_section.get("function") if phase_section else None,
                    "gesture_id": gesture["gesture_id"],
                    "provenance": "machine-only",
                    "summary": _phase_summary(phase_name, phase, impact_time),
                    "evidence_summary": phase["evidence"],
                }
                if phase_name == "impact":
                    # v3.9 item 4 -- `start_time` is the onset; `peak_time`
                    # keeps the transient's own peak (equal to the onset for a
                    # stem-entry impact, which has no separate transient peak).
                    event["peak_time"] = round(float(phase["peak_time"]), 6)
                events.append(event)
    else:
        gestures = []

    for transition in detect_section_transitions(sections):
        events.append({
            "type": transition["type"],
            "start_time": round(transition["start_time"], 6),
            "end_time": round(transition["end_time"], 6),
            "confidence": transition["confidence"],
            "intensity": transition["confidence"],
            "section_id": transition["section_id"],
            "section_name": transition["section_name"],
            "provenance": "machine-only",
            "summary": transition["summary"],
            "evidence_summary": transition["evidence_summary"],
        })

    # Nearby impacts share the same 16-bar lookback window, so the same
    # riser/roll/gap/cymbal primitive is routinely the best candidate for
    # several consecutive gestures -- a real riser does not become a second
    # event just because a later impact also looked back far enough to see
    # it. Collapse exact (type, start_time, end_time) duplicates to the
    # highest-confidence row rather than emitting one per gesture that reused
    # it; this is deduplication of an identical claim, not a guess.
    deduped: dict[tuple[str, float, float], dict[str, Any]] = {}
    for event in events:
        key = (event["type"], event["start_time"], event["end_time"])
        existing = deduped.get(key)
        if existing is None or event["confidence"] > existing["confidence"]:
            deduped[key] = event
    events = list(deduped.values())

    events.sort(key=lambda e: (e["start_time"], e["end_time"]))

    generated_from = {
        "source_song_path": str(paths.song_path),
        "engine": "gestures.primitives (rule-based sound-design device detectors) + gestures.assembly + section-transition detector",
        "dependencies": {
            "fft_bands_file": str(paths.artifact("essentia", "fft_bands.json")),
            "rms_loudness_file": str(paths.artifact("essentia", "rms_loudness.json")),
            "drum_events_file": str(paths.artifact("symbolic_transcription", "drum_events.json")),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "sections_file": str(paths.sections_output_path),
        },
        "gesture_count": len(gestures),
    }

    # v3.6 item 8 — the full event shape (every field, including the ones
    # dropped from the top-level view below) is written to its own artifact
    # first, so the debugger UI can still read `section_name` / `summary` /
    # `evidence_summary` / `provenance` there.
    full_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": generated_from,
        "events": events,
    }
    write_json(paths.artifact("gestures", "song_event_timeline.json"), full_payload)

    # v3.1 item 2 — attribution header. Every event field is the gestures stage's
    # own output except `section_id`, which it copies from the PUBLISHED
    # sections.json to locate each event (v3.7 item 6 — was allin1's raw
    # segmentation).
    #
    # v3.6 item 8 — `section_name` (duplicates the section_id join),
    # `summary` / `evidence_summary` / `provenance` (unread) and
    # `generated_from` (provenance now lives in artifacts/ only) are dropped
    # from the top-level view; all four stay on the artifact above.
    trimmed_events = [
        {k: v for k, v in event.items() if k not in ("section_name", "summary", "evidence_summary", "provenance")}
        for event in events
    ]
    timeline_field_sources = validate_field_sources(
        {
            "type": "gestures",
            "start_time": "gestures",
            "end_time": "gestures",
            "confidence": "gestures",
            "intensity": "gestures",
            "section_id": "sections",
            "gesture_id": "gestures",
            "peak_time": "gestures",
        },
        {key for event in trimmed_events for key in event},
        file="song_event_timeline.json",
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": timeline_field_sources,
        "events": trimmed_events,
    }
    write_json(paths.timeline_output_path, payload)
    return payload
