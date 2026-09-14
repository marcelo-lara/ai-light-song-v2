"""Autocorrelation of the bar sequence — period, not phase.

Two readings come out of the same per-bar 16-slot matrix:

  * **phrase length** — the lag L in 2..16 bars at which the bar-to-bar
    similarity peaks. `prominence` = peak minus its neighbouring lags, which
    doubles as an honest confidence. Near-zero prominence -> "no phrase
    structure detected", never a forced number.
  * **block regime** — `rep@bar` (lag-1 bar similarity) and `rep@beat`
    (within-bar 4-slot circular similarity) classify a passage as
    through-composed / bar-loop / half-bar-loop.

The method config is fixed here, not swept.
"""
from __future__ import annotations

import numpy as np

MAX_LAG = 16
EPS = 1e-12

# regime thresholds — principled, not tuned to a target number. rep@bar low
# means consecutive bars do not resemble each other (through-composed); high
# means a bar loop. rep@beat high on top of that means the repeat unit is
# half a bar.
REP_BAR_LOOP = 0.30
REP_BEAT_HALF = 0.45

# a phrase peak below this prominence is reported as "no phrase structure".
PROMINENCE_FLOOR = 0.05


def _row_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity per row-pair of two (n, d) matrices — NOT re-centred.

    This is why the per-bar z-normalisation is load-bearing: on a z-normed bar
    (mean 0, unit std) cosine similarity is pure shape agreement; on the raw
    envelope the shared positive DC level dominates and washes the shape out.
    The raw-envelope run is the named cheap-baseline ablation.
    """
    num = (a * b).sum(axis=1)
    den = np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
    return np.where(den > EPS, num / np.maximum(den, EPS), 0.0)


def bar_autocorr(bars: np.ndarray, max_lag: int = MAX_LAG) -> np.ndarray:
    """ac[k] = mean bar-to-bar cosine similarity at lag (k+1) bars, for k in 0..max_lag-1."""
    n = len(bars)
    out = np.zeros(max_lag)
    for k in range(1, max_lag + 1):
        if n - k < 2:
            break
        out[k - 1] = float(np.mean(_row_sim(bars[:-k], bars[k:])))
    return out


def phrase_length(bars: np.ndarray) -> tuple[int | None, float]:
    """(period_bars, prominence). period is None when prominence < the floor."""
    ac = bar_autocorr(bars)
    if len(bars) < 4 or not np.any(ac[1:]):
        return None, 0.0
    cand = ac.copy()
    cand[0] = -np.inf  # lag 1 is rep@bar, not a phrase
    peak = int(np.argmax(cand))  # 0-based -> period = peak + 1
    lo = ac[peak - 1] if peak - 1 >= 1 else ac[peak]
    hi = ac[peak + 1] if peak + 1 < len(ac) and ac[peak + 1] != 0 else ac[peak]
    prominence = float(ac[peak] - 0.5 * (lo + hi))
    if prominence < PROMINENCE_FLOOR:
        return None, prominence
    return peak + 1, prominence


def rep_at_bar(bars: np.ndarray) -> float:
    if len(bars) < 3:
        return 0.0
    return float(np.mean(_row_sim(bars[:-1], bars[1:])))


def rep_at_beat(bars: np.ndarray) -> float:
    """Within-bar circular autocorrelation at a 4-slot (one-beat) lag, averaged
    over bars. High => the bar is built from a repeating beat cell."""
    if len(bars) == 0:
        return 0.0
    rolled = np.roll(bars, -4, axis=1)
    return float(np.mean(_row_sim(bars, rolled)))


def regime(bars: np.ndarray) -> tuple[str, float | None]:
    """(regime label, period in bars or None)."""
    if len(bars) < 2:
        return "through-composed", None
    rb = rep_at_bar(bars)
    rbeat = rep_at_beat(bars)
    if rb < REP_BAR_LOOP:
        return "through-composed", None
    if rbeat >= REP_BEAT_HALF:
        return "half-bar-loop", 0.5
    return "bar-loop", 1.0


def bars_in_span(cache: dict, start_s: float, end_s: float, key: str) -> np.ndarray:
    """The per-bar rows whose bar-centre falls inside [start_s, end_s)."""
    db = cache["downbeats"]
    rows = cache[key]
    if len(db) < 2 or len(rows) == 0:
        return rows[:0]
    centres = (db[:-1] + db[1:]) / 2.0
    centres = centres[: len(rows)]
    mask = (centres >= start_s) & (centres < end_s)
    return rows[mask]
