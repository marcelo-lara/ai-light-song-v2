"""Arrangement-state change detection from the published per-stem RMS series.

The question this answers is not "what part is this" but "*who is playing*, and
when does that change". Nothing here reads audio, a spectrogram or a model —
only `loudness.json`, which the pipeline already publishes.

Three decisions carry the whole result; each is a measured one, see README.

1.  **Per-stem, per-song thresholds.** A stem is judged against its own 98th
    percentile in this song, never an absolute level. Nothing transfers between
    tracks or between stems.
2.  **Detect at 250 ms, gate on persistence, report the fine edge.** Smoothing
    the presence signal before thresholding buys precision and *moves the
    boundary* — measured at F1 0.59 -> 0.27 on `_test_song`, with the `Spacer`
    hint displaced by 6 s. So a flip counts only if the new value holds, and the
    time reported is always the unsmoothed edge (a cue fired late is a cue
    missed).
3.  **The mix channel never triggers a change.** It is a sum, so it moves
    whenever any stem does and adds no independent evidence.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from . import paths

#: Detection grid. Fine enough for the shortest hand-marked block in the corpus
#: (`_test_song` "Spacer", 0.46 s) to survive as its own edge.
WINDOW_S = 0.25

#: A stem counts as sounding when it is within this many dB of its own loud
#: level in this song. 18 dB is roughly "audible in the mix" rather than
#: "audible in isolation" — below it, stem bleed from the separator dominates.
PRESENT_DB_BELOW_P98 = 18.0

#: Fraction of a window's frames above threshold for the window to read present.
PRESENT_FRACTION = 0.4

#: How long a flipped value must hold before the flip is believed, and how much
#: of that span must agree. Expressed in seconds rather than bars because the
#: downbeat grid measures 0.226 F1 — the bar numbers are not trustworthy enough
#: to gate a boundary on.
HOLD_S = 1.5
HOLD_AGREEMENT = 0.7


@dataclass
class Change:
    time: float
    entered: list[str] = field(default_factory=list)
    left: list[str] = field(default_factory=list)
    state: dict[str, bool] = field(default_factory=dict)
    #: Smallest dB margin among the stems that flipped — the evidence behind
    #: this change, and what a confidence would be derived from.
    margin_db: float = 0.0


@dataclass
class Result:
    song: str
    stems: list[str]
    times: list[float]
    presence: list[list[float]]
    thresholds_db: dict[str, float]
    changes: list[Change]
    duration: float


def _percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


def _windows(song: str) -> tuple[list[str], float, list[float], list[list[float]], list[list[float]], dict[str, float]]:
    """Shared windowing/threshold computation for `detect` and `detect_smoothed`.

    Returns (order, duration, win_times, presence, margin, thresholds_db) —
    everything downstream of the raw per-stem dB series and before either
    gate (persistence, or duty-cycle + hysteresis) is applied.
    """
    doc = json.loads(paths.loudness_path(song).read_text())
    order: list[str] = doc["metadata"]["source_order"]
    duration: float = doc["metadata"]["duration"]
    frames = doc["frames"]

    times = [f["time"] for f in frames]
    # dB per source. A silent frame floors at -180 dB rather than being dropped:
    # silence is a fact about the stem, not missing data (no silent fallbacks).
    db = [[20.0 * math.log10(max(f["values"][i], 1e-9)) for f in frames] for i in range(len(order))]
    thresholds = {order[i]: _percentile(db[i], 0.98) - PRESENT_DB_BELOW_P98 for i in range(len(order))}

    n_windows = int(duration / WINDOW_S)
    win_times: list[float] = []
    presence: list[list[float]] = []
    margin: list[list[float]] = []
    cursor = 0
    for w in range(n_windows):
        lo, hi = w * WINDOW_S, (w + 1) * WINDOW_S
        while cursor < len(times) and times[cursor] < lo:
            cursor += 1
        idx = []
        j = cursor
        while j < len(times) and times[j] < hi:
            idx.append(j)
            j += 1
        if not idx:
            continue
        win_times.append(lo)
        presence.append(
            [sum(1 for k in idx if db[i][k] > thresholds[order[i]]) / len(idx) for i in range(len(order))]
        )
        margin.append(
            [max(db[i][k] for k in idx) - thresholds[order[i]] for i in range(len(order))]
        )

    return order, duration, win_times, presence, margin, thresholds


def detect(song: str) -> Result:
    order, duration, win_times, presence, margin, thresholds = _windows(song)

    hold = max(1, int(round(HOLD_S / WINDOW_S)))
    n = len(win_times)
    state = [[False] * len(order) for _ in range(n)]
    for i in range(len(order)):
        cur = presence[0][i] > PRESENT_FRACTION
        state[0][i] = cur
        for w in range(1, n):
            v = presence[w][i] > PRESENT_FRACTION
            if v != cur:
                future = [presence[k][i] > PRESENT_FRACTION for k in range(w, min(n, w + hold))]
                if sum(1 for x in future if x == v) >= HOLD_AGREEMENT * len(future):
                    cur = v
            state[w][i] = cur

    changes: list[Change] = []
    for w in range(1, n):
        entered, left, margins = [], [], []
        for i, stem in enumerate(order):
            if stem == "mix" or state[w][i] == state[w - 1][i]:
                continue
            (entered if state[w][i] else left).append(stem)
            margins.append(abs(margin[w][i]))
        if entered or left:
            changes.append(
                Change(
                    time=round(win_times[w], 3),
                    entered=entered,
                    left=left,
                    state={s: state[w][i] for i, s in enumerate(order) if s != "mix"},
                    margin_db=round(min(margins), 2),
                )
            )

    return Result(
        song=song,
        stems=[s for s in order if s != "mix"],
        times=win_times,
        presence=presence,
        thresholds_db={k: round(v, 2) for k, v in thresholds.items()},
        changes=changes,
        duration=duration,
    )


def detect_smoothed(song: str) -> Result:
    """Documented ablation only — the shipped detector is `detect()`.

    Same windows and thresholds as `detect()`, but gates on a ±1.0 s duty-cycle
    (a 9-window moving average of raw presence) with hysteresis, instead of the
    persistence gate. Kept here so the smoothing cost measured in the README
    ("Measurement 1") can be reproduced from this module rather than asserted.
    """
    order, duration, win_times, presence, margin, thresholds = _windows(song)
    n = len(win_times)
    n_stems = len(order)

    duty = [[0.0] * n_stems for _ in range(n)]
    for w in range(n):
        lo, hi = max(0, w - 4), min(n - 1, w + 4)
        span = presence[lo : hi + 1]
        for i in range(n_stems):
            duty[w][i] = sum(row[i] for row in span) / len(span)

    state = [[False] * n_stems for _ in range(n)]
    for i in range(n_stems):
        cur = duty[0][i] > 0.3
        state[0][i] = cur
        for w in range(1, n):
            if cur:
                if duty[w][i] < 0.15:
                    cur = False
            else:
                if duty[w][i] > 0.35:
                    cur = True
            state[w][i] = cur

    raw_changes: list[Change] = []
    for w in range(1, n):
        entered, left, margins = [], [], []
        for i, stem in enumerate(order):
            if stem == "mix" or state[w][i] == state[w - 1][i]:
                continue
            (entered if state[w][i] else left).append(stem)
            margins.append(abs(margin[w][i]))
        if entered or left:
            raw_changes.append(
                Change(
                    time=round(win_times[w], 3),
                    entered=entered,
                    left=left,
                    state={s: state[w][i] for i, s in enumerate(order) if s != "mix"},
                    margin_db=round(min(margins), 2),
                )
            )

    merged: list[Change] = []
    for c in raw_changes:
        if merged and c.time - merged[-1].time < 0.5:
            prev = merged[-1]
            merged[-1] = Change(
                time=prev.time,
                entered=sorted(set(prev.entered) | set(c.entered)),
                left=sorted(set(prev.left) | set(c.left)),
                state=c.state,
                margin_db=round(min(prev.margin_db, c.margin_db), 2),
            )
        else:
            merged.append(c)

    return Result(
        song=song,
        stems=[s for s in order if s != "mix"],
        times=win_times,
        presence=presence,
        thresholds_db={k: round(v, 2) for k, v in thresholds.items()},
        changes=merged,
        duration=duration,
    )


def blocks(result: Result) -> list[dict]:
    """The changes read as spans — what a published character block would be."""
    edges = [0.0] + [c.time for c in result.changes] + [result.duration]
    out = []
    for i, c in enumerate([None] + result.changes):
        start, end = edges[i], edges[i + 1]
        if end - start <= 0:
            continue
        state = c.state if c else {s: True for s in result.stems}
        playing = [s for s in result.stems if state.get(s)]
        out.append(
            {
                "start_s": round(start, 3),
                "end_s": round(end, 3),
                "playing": playing,
                "entered": c.entered if c else [],
                "left": c.left if c else [],
                "margin_db": c.margin_db if c else None,
            }
        )
    return out
