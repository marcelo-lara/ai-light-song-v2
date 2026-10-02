"""Edges + cached series -> phrases with per-phrase features.

Every feature is a plain measurement over the phrase's beat windows (or its
seconds), published as a number; none is a label. `None` means "not
applicable / not measurable here", never a guessed value.
"""
from __future__ import annotations

import numpy as np

from . import detect

#: presence thresholds are fractions of the song's own p95 over beat windows
#: (same fractions as stem_presence_sections; never absolute levels).
KICK_ON_FRAC, KICK_ON_FLOOR = 0.5, 0.2
BASS_ON_FRAC = 0.35
VOCALS_ON_FRAC = 0.40

KICK_END_BEATS = 4          # "near the end" = the last four beats
KICK_BODY_MIN = 0.5         # the rest of the phrase must have a kick to lose
KICK_END_MAX = 0.25         # kick presence in the tail below this = dropped out
NOISE_MAX_BEATS = 16
NOISE_MIN_BEATS = 4
NOISE_BANDS = (2, 3, 4, 5, 6)   # low-mid .. brilliance: a broadband rise, not one tonal band
NOISE_MIN_R2 = 0.4
NOISE_MIN_RISE = 0.2

#: an edge's evidence score maps to confidence as score / CONF_FULL_SCORE (cap 1.0):
#: 4.0 is roughly a presence boundary + two stem changes + an impact, so a lone
#: just-accepted edge (1.5) reads 0.375, not 1.0.
CONF_FULL_SCORE = 4.0

REPEAT_MAX_DIST = 0.12
REPEAT_MIN_BEATS = 8
REPEAT_LEN_RATIO = (0.8, 1.25)
GAP_END_BEATS = 1.0
SWEEP_MIN_INSIDE = 0.5


def _arr(xs):
    return np.array([np.nan if x is None else x for x in xs], dtype=float)


def _p95(a: np.ndarray) -> float:
    a = a[~np.isnan(a)]
    return float(np.percentile(a, 95)) if len(a) else 0.0


def _frac_on(vals: np.ndarray, thr: float) -> float | None:
    v = vals[~np.isnan(vals)]
    return round(float((v >= thr).mean()), 4) if len(v) else None


def _coverage(spans: list[dict], lo: float, hi: float) -> float:
    ivs = sorted((max(s["start"], lo), min(s["end"], hi)) for s in spans if s["end"] > lo and s["start"] < hi)
    total, cur_end = 0.0, None
    for a, b in ivs:
        if cur_end is None or a > cur_end:
            total += b - a
            cur_end = b
        elif b > cur_end:
            total += b - cur_end
            cur_end = b
    return round(total / (hi - lo), 4) if hi > lo else 0.0


def noise_sweep(bands: np.ndarray) -> tuple[bool | None, float | None]:
    """Broadband rise over the phrase's tail: every band in NOISE_BANDS rising
    with r2 >= NOISE_MIN_R2 and a mean rise >= NOISE_MIN_RISE (levels are 0..1
    normalised log power). A tonal riser lifts one or two bands; noise lifts all."""
    n = min(NOISE_MAX_BEATS, len(bands) // 2)
    if n < NOISE_MIN_BEATS:
        return None, None
    tail = bands[-n:]
    x = np.arange(n, dtype=float)
    rises, ok = [], True
    for b in NOISE_BANDS:
        y = tail[:, b]
        if np.isnan(y).any():
            return None, None
        slope, icpt = np.polyfit(x, y, 1)
        resid = y - (slope * x + icpt)
        ss_tot = float(((y - y.mean()) ** 2).sum())
        r2 = 1.0 - float((resid ** 2).sum()) / ss_tot if ss_tot > 1e-12 else 0.0
        rises.append(slope * (n - 1))
        ok &= slope > 0 and r2 >= NOISE_MIN_R2
    rise = float(np.mean(rises))
    return bool(ok and rise >= NOISE_MIN_RISE), round(rise, 4)


def build_phrases(cache: dict, sweeps: list[dict] | None) -> list[dict]:
    beats = cache["beats"]
    trusted = cache["trusted"]
    beat_len = cache["beat_len"]
    duration = cache["duration"]
    ser = {k: _arr(v) for k, v in cache["series"].items()}
    bands = np.array([[np.nan if x is None else x for x in r] for r in cache["bands"]], dtype=float)
    prim = cache["primitives"]
    centers = np.array(beats) + beat_len / 2.0

    kick_thr = max(KICK_ON_FLOOR, KICK_ON_FRAC * _p95(ser["kick_low"]))
    bass_thr = BASS_ON_FRAC * _p95(ser["bass"])
    voc_thr = VOCALS_ON_FRAC * _p95(ser["vocals"])

    edges = detect.detect_edges(cache["candidates"], beats, trusted, beat_len, duration)
    bounds = [0.0] + [e["t"] for e in edges] + [duration]
    risers = prim["riser"] + prim["reverse_cymbal"]

    phrases: list[dict] = []
    for i in range(len(bounds) - 1):
        lo, hi = bounds[i], bounds[i + 1]
        sel = np.where((centers >= lo) & (centers < hi))[0]
        n = len(sel)
        kick = ser["kick_low"][sel]
        kp = _frac_on(kick, kick_thr)
        k_end = k_body = None
        if n > KICK_END_BEATS:
            k_end = _frac_on(kick[-KICK_END_BEATS:], kick_thr)
            k_body = _frac_on(kick[:-KICK_END_BEATS], kick_thr)
        kick_drop = None
        if k_end is not None and k_body is not None and k_body >= KICK_BODY_MIN:
            kick_drop = bool(k_end <= KICK_END_MAX)
        ns, ns_strength = noise_sweep(bands[sel]) if n else (None, None)
        e_in = edges[i - 1] if i > 0 else None
        e_out = edges[i] if i < len(edges) else None
        conflicts = sorted({c for e in (e_in, e_out) if e for c in e["conflicts"]})
        edge_scores = [e["score"] for e in (e_in, e_out) if e]
        conf = round(float(np.mean([min(1.0, s / CONF_FULL_SCORE) for s in edge_scores])), 4) if edge_scores else None
        ends_gap = bool(e_out) and any(abs(g["end"] - hi) <= GAP_END_BEATS * beat_len
                                       for g in prim["pre_drop_gap"])
        if sweeps is None:
            fs = None
        else:
            fs = []
            for s in sweeps:
                inside = min(s["end_s"], hi) - max(s["start_s"], lo)
                if inside >= SWEEP_MIN_INSIDE * (s["end_s"] - s["start_s"]):
                    fs.append({"stem": s["stem"], "direction": s["direction"],
                               "start_s": s["start_s"], "end_s": s["end_s"]})
        phrases.append({
            "id": f"phrase-{i + 1:02d}",
            "start_s": round(lo, 3), "end_s": round(hi, 3),
            "n_beats": int(n),
            "kick_presence": kp,
            "bass_presence": _frac_on(ser["bass"][sel], bass_thr),
            "vocals_presence": _frac_on(ser["vocals"][sel], voc_thr),
            "riser_density": _coverage(risers, lo, hi),
            "snare_roll_density": _coverage(prim["snare_roll"], lo, hi),
            "filter_sweeps": fs,
            "noise_sweep": ns, "noise_sweep_strength": ns_strength,
            "kick_dropout_near_end": kick_drop,
            "ends_on_gap": ends_gap,
            "repeat_of": None, "repeat_distance": None,
            "start_edge": e_in, "end_edge": e_out,
            "resolved": not conflicts, "conflicts": conflicts,
            "confidence": conf,
            "_vec": _descriptor(ser, bands, sel, kick_thr, bass_thr, voc_thr),
        })
    _assign_repeats(phrases)
    for p in phrases:
        p.pop("_vec")
    return phrases


def _descriptor(ser, bands, sel, kick_thr, bass_thr, voc_thr):
    if len(sel) < REPEAT_MIN_BEATS:
        return None
    parts = [_frac_on(ser["kick_low"][sel], kick_thr), _frac_on(ser["bass"][sel], bass_thr),
             _frac_on(ser["vocals"][sel], voc_thr)]
    prof = np.nanmean(bands[sel], axis=0)
    if any(p is None for p in parts) or np.isnan(prof).any():
        return None
    return np.array(parts + list(prof), dtype=float)


def _assign_repeats(phrases: list[dict]) -> None:
    """Earliest-best earlier phrase with a near-identical presence + spectral
    profile and a similar length. Texture-level similarity, not section identity."""
    for j, p in enumerate(phrases):
        v = p["_vec"]
        if v is None:
            continue
        best = None
        for i in range(j):
            u = phrases[i]["_vec"]
            if u is None:
                continue
            ratio = p["n_beats"] / phrases[i]["n_beats"]
            if not REPEAT_LEN_RATIO[0] <= ratio <= REPEAT_LEN_RATIO[1]:
                continue
            d = float(np.sqrt(np.mean((u - v) ** 2)))
            if d <= REPEAT_MAX_DIST and (best is None or d < best[1]):
                best = (i, d)
        if best:
            p["repeat_of"] = phrases[best[0]]["id"]
            p["repeat_distance"] = round(best[1], 4)
