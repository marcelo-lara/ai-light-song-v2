"""Sweep detector: a near-monotonic centroid move over 2-16 bars on one stem
while that stem's loudness stays roughly level.

For every stem and every window length in `BAR_LENGTHS` (stride half a bar):
  * the window must have the stem present (level >= PRESENT_FRAC of the song's
    p95 level) and >= 90 % valid centroid samples;
  * both series are first smoothed with a 1-bar boxcar (note-level jitter
    would otherwise swamp any monotonicity measure);
  * depth = |end-of-window mean - start-of-window mean| centroid (octaves)
    >= MIN_DEPTH_OCT[stem];
  * monotonicity = |Spearman rho| of centroid against time >= MIN_MONO
    (1.0 = strictly monotonic);
  * level flatness: (p90 - p10) / mean of the stem's level <= MAX_LEVEL_SPREAD,
    and the fitted level trend over the window <= MAX_LEVEL_TREND of its mean
    (a stem getting louder or quieter is a fade / entry, not a filter move).
Survivors are ranked by depth * monotonicity, kept greedily without overlap
within a stem, then trimmed to the centroid's extremes so the span ends where
the move ends. Times are physical (grid samples), never snapped to bars.
"""
from __future__ import annotations

import numpy as np

BAR_LENGTHS = (2, 3, 4, 6, 8, 12, 16)
MIN_DEPTH_OCT = {"harmonic": 1.0, "bass": 0.5}  # bass spans only the lowest bands
MIN_MONO = 0.85  # |Spearman rho| of centroid vs time
MAX_LEVEL_SPREAD = 0.50
MAX_LEVEL_TREND = 0.50
PRESENT_FRAC = 0.10
MIN_VALID = 0.90
EDGE_FRAC = 0.15  # fraction of window averaged at each end for the net move


def _interp(x: np.ndarray) -> np.ndarray:
    idx = np.arange(len(x))
    ok = ~np.isnan(x)
    return np.interp(idx, idx[ok], x[ok])


def _window_stats(cen: np.ndarray, lev: np.ndarray, level_p95: float) -> dict | None:
    if np.isnan(cen).mean() > 1 - MIN_VALID or np.isnan(lev).any():
        return None
    if lev.min() < PRESENT_FRAC * level_p95:
        return None
    c = _interp(cen)
    n = len(c)
    k = max(2, int(round(n * EDGE_FRAC)))
    net = float(c[-k:].mean() - c[:k].mean())
    if np.ptp(c) <= 0:
        return None
    ranks = np.argsort(np.argsort(c)).astype(float)
    rho = float(np.corrcoef(np.arange(n), ranks)[0, 1])
    mean_lev = float(lev.mean())
    if mean_lev <= 0:
        return None
    spread = float((np.percentile(lev, 90) - np.percentile(lev, 10)) / mean_lev)
    slope = float(np.polyfit(np.arange(n), lev, 1)[0])
    trend = abs(slope) * n / mean_lev
    return {"net": net, "mono": abs(rho), "spread": spread, "trend": trend}


def _boxcar(x: np.ndarray, w: int) -> np.ndarray:
    """NaN-aware centred moving mean over `w` samples."""
    out = np.full(len(x), np.nan)
    h = w // 2
    for i in range(len(x)):
        seg = x[max(0, i - h):i + h + 1]
        seg = seg[~np.isnan(seg)]
        if len(seg) >= max(1, w // 2):
            out[i] = seg.mean()
    return out


def detect_stem(stem: str, cen: np.ndarray, lev: np.ndarray, level_p95: float, step: float,
                bar_len: float, *, gate_mono: bool = True, gate_level: bool = True) -> list[dict]:
    """`gate_mono` / `gate_level` exist only so `score.py` can run the ablation
    baselines (depth-only, depth+monotonic); the exported lane uses both."""
    samples_per_bar = bar_len / step
    w = max(3, int(round(samples_per_bar)))
    cen, lev = _boxcar(cen, w), _boxcar(lev, w)
    min_depth = MIN_DEPTH_OCT[stem]
    stride = max(1, int(round(samples_per_bar / 2)))
    cands = []
    for nb in BAR_LENGTHS:
        n = int(round(nb * samples_per_bar))
        for i in range(0, len(cen) - n + 1, stride):
            st = _window_stats(cen[i:i + n], lev[i:i + n], level_p95)
            if st is None:
                continue
            if (abs(st["net"]) >= min_depth
                    and (not gate_mono or st["mono"] >= MIN_MONO)
                    and (not gate_level or (st["spread"] <= MAX_LEVEL_SPREAD
                                            and st["trend"] <= MAX_LEVEL_TREND))):
                cands.append({"i": i, "n": n, "score": abs(st["net"]) * st["mono"], **st})
    cands.sort(key=lambda c: (-c["score"], c["i"], c["n"]))
    kept, taken = [], np.zeros(len(cen), dtype=bool)
    for c in cands:
        if taken[c["i"]:c["i"] + c["n"]].any():
            continue
        taken[c["i"]:c["i"] + c["n"]] = True
        kept.append(c)

    rows = []
    for c in sorted(kept, key=lambda c: c["i"]):
        seg = _interp(cen[c["i"]:c["i"] + c["n"]])
        up = c["net"] > 0
        # trim to the move itself: from the last sample still within 10 % of the
        # start extreme to the first sample within 10 % of the end extreme
        rng = float(np.ptp(seg))
        s_ext, e_ext = (seg.min(), seg.max()) if up else (seg.max(), seg.min())
        e_idx = int(np.argmax(seg)) if up else int(np.argmin(seg))
        near_start = np.abs(seg[:e_idx + 1] - s_ext) <= 0.10 * rng
        lo = int(np.nonzero(near_start)[0].max()) if near_start.any() else 0
        near_end = np.abs(seg[lo:] - e_ext) <= 0.10 * rng
        hi = lo + int(np.nonzero(near_end)[0].min()) if near_end.any() else e_idx
        if hi <= lo:
            continue
        i0, i1 = c["i"] + lo, c["i"] + hi
        dur_bars = (i1 - i0) * step / bar_len
        if dur_bars < BAR_LENGTHS[0] * 0.9 or dur_bars > BAR_LENGTHS[-1] * 1.05:
            continue
        depth = float(abs(seg[hi] - seg[lo]))
        if depth < min_depth:
            continue
        rows.append({
            "stem": stem, "direction": "opening" if up else "closing",
            "start": float(i0 * step), "end": float(i1 * step),
            "depth": depth, "mono": c["mono"], "spread": c["spread"], "trend": c["trend"],
        })
    return rows


def confidence(row: dict) -> float:
    """Heuristic 0..1, not calibrated: monotonicity, depth beyond the floor
    (saturating at 3 octaves) and level flatness, multiplied."""
    mono = min(1.0, max(0.0, (row["mono"] - MIN_MONO) / (1.0 - MIN_MONO)))
    depth = min(1.0, (row["depth"] - MIN_DEPTH_OCT[row["stem"]]) / 2.0)
    flat = 1.0 - min(1.0, row["spread"] / MAX_LEVEL_SPREAD) * 0.5 - min(1.0, row["trend"] / MAX_LEVEL_TREND) * 0.5
    return round(float(0.25 + 0.75 * (0.4 * mono + 0.3 * depth + 0.3 * flat)), 3)


def detect_song(cache: dict, **gates: bool) -> list[dict]:
    rows = []
    for stem, d in cache["series"].items():
        for r in detect_stem(stem, d["centroid"], d["level"], d["level_p95"], cache["step_s"],
                             cache["bar_length_s"], **gates):
            r["confidence"] = confidence(r)
            rows.append(r)
    rows.sort(key=lambda r: (r["start"], r["stem"]))
    return rows
