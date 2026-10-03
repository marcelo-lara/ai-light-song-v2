"""Running slope indicator, per-bar sweep state, sweep end events.

All series are half-beat rows (features.half_beat_rows). A bar's slope over the last N
bars is the least-squares slope of the series against time over the half-beats of bars
i-N+1..i, in units per bar (bar = 4 x median beat, never the downbeat labels). `cons` is
|Pearson r| of that fit, 0..1: how monotone the move is. These are a running indicator,
not a verdict; the *state* below is the thin, thresholded reading of them.

State (opening | closing | None). Bar i is `opening` when, over a trailing window of 4 or
8 bars, the high/low ratio rises by >= HL_SLOPE dB/bar or the 99 % rolloff rises by
>= ROLL_SLOPE octaves/bar, with cons >= MIN_CONS on that series; `closing` is the mirror.
Single-bar gaps between equal states are bridged, runs shorter than MIN_RUN_BARS dropped.
A bar whose stem level falls DROPOUT_DB under the previous four bars' median is a dropout: it carries no
state and every window restarts after it, so a gap ends a sweep instead of extending it. Thresholds were chosen on Armin - Revolution and Medicine-MilkInc (the validation songs),
not held out.

Sweep end event: first bar after a run, on its first beat. `end_kind` is `cut` if the high/low
ratio moves back by >= CUT_DB dB in that bar, else `top`. The aftermath (aftermath.py) comes
from bar_features.
"""
from __future__ import annotations

import numpy as np

WINDOWS = (1, 2, 4, 8)
STATE_WINDOWS = (4, 8)
HL_SLOPE = 1.5        # dB per bar
ROLL_SLOPE = 0.15     # octaves per bar
MIN_CONS = 0.6
DROPOUT_DB = 6.0      # a bar this far under the previous 4 bars' median level is a dropout, not part of a sweep
MIN_RUN_BARS = 3
BRIDGE_BARS = 1
CUT_DB = 6.0
MIN_POINTS = 4
SERIES = {"hl": "hl_db", "roll": "roll_log2", "peak": "peak_log2"}


def add_log_columns(rows: list[dict]) -> None:
    for r in rows:
        r["roll_log2"] = float(np.log2(r["roll_hz"])) if r["roll_hz"] == r["roll_hz"] else float("nan")
        r["peak_log2"] = float(np.log2(r["peak_hz"])) if r["peak_hz"] == r["peak_hz"] else float("nan")


def _fit(x: np.ndarray, y: np.ndarray) -> tuple[float | None, float | None]:
    ok = ~np.isnan(y)
    if ok.sum() < MIN_POINTS or np.ptp(x[ok]) == 0:
        return None, None
    x, y = x[ok], y[ok]
    slope = float(np.polyfit(x, y, 1)[0])
    if np.std(y) < 1e-9:
        return slope, 0.0
    return slope, float(abs(np.corrcoef(x, y)[0, 1]))


def bar_slopes(rows: list[dict], row_bar: list[int], n_bars: int, bar_len: float) -> list[dict]:
    """Per bar: {series: {N: (slope, cons)}} over the last N bars, plus bar medians."""
    t = np.array([(r["start_s"] + r["end_s"]) / 2.0 for r in rows]) / bar_len
    bar_of = np.array(row_bar)
    vals = {k: np.array([r[c] for r in rows], dtype=float) for k, c in SERIES.items()}
    level = np.array([r["level_db"] for r in rows], dtype=float)
    med_level = [float(np.nanmedian(level[bar_of == i])) if (bar_of == i).any() and not np.all(np.isnan(level[bar_of == i]))
                 else float("nan") for i in range(n_bars)]
    dropout = [False] * n_bars
    for i in range(n_bars):  # a dropout bar's values are the cut itself, not part of a move
        ref = np.nanmedian(med_level[max(0, i - 4):i]) if i and not np.all(np.isnan(med_level[max(0, i - 4):i])) else np.nan
        dropout[i] = bool(med_level[i] < ref - DROPOUT_DB)
    out = []
    for i in range(n_bars):
        entry: dict = {"median": {}, "dropout": dropout[i]}
        here = bar_of == i
        for k, v in vals.items():
            entry["median"][k] = float(np.nanmedian(v[here])) if here.any() and not np.all(np.isnan(v[here])) else None
            entry[k] = {}
            for n in WINDOWS:
                first = i - n + 1
                for d in range(first, i + 1):  # the window restarts after a dropout
                    if d >= 0 and dropout[d]:
                        first = d + 1
                m = (bar_of >= first) & (bar_of <= i)
                s, c = _fit(t[m], v[m])
                entry[k][n] = (s, c)
        out.append(entry)
    return out


def _vote(entry: dict) -> str | None:
    if entry["dropout"]:
        return None
    best: tuple[float, str] | None = None
    for n in STATE_WINDOWS:
        for k, thr in (("hl", HL_SLOPE), ("roll", ROLL_SLOPE)):
            s, c = entry[k][n]
            if s is None or c < MIN_CONS or abs(s) < thr:
                continue
            d = "opening" if s > 0 else "closing"
            if best is None or c > best[0]:
                best = (c, d)
    return best[1] if best else None


def bar_states(slopes: list[dict]) -> list[str | None]:
    st = [_vote(e) for e in slopes]
    for i in range(1, len(st) - BRIDGE_BARS):  # bridge one-bar gaps
        if st[i] is None and st[i - 1] is not None and st[i - 1] == st[i + 1]:
            st[i] = st[i - 1]
    out = list(st)
    i = 0
    while i < len(st):
        if st[i] is None:
            i += 1
            continue
        j = i
        while j + 1 < len(st) and st[j + 1] == st[i]:
            j += 1
        if j - i + 1 < MIN_RUN_BARS:
            for k in range(i, j + 1):
                out[k] = None
        i = j + 1
    return out


def runs_of(states: list[str | None]) -> list[tuple[int, int, str]]:
    runs, i = [], 0
    while i < len(states):
        if states[i] is None:
            i += 1
            continue
        j = i
        while j + 1 < len(states) and states[j + 1] == states[i]:
            j += 1
        runs.append((i, j, states[i]))
        i = j + 1
    return runs


def end_kind(direction: str, last_bar_hl: float | None, next_bar_hl: float | None) -> str:
    """`cut` when the high/low ratio snaps back in the first bar after the run."""
    if last_bar_hl is None or next_bar_hl is None:
        return "top"
    delta = next_bar_hl - last_bar_hl
    return "cut" if (delta <= -CUT_DB if direction == "opening" else delta >= CUT_DB) else "top"
