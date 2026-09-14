"""Shared math for the five rhythm/energy/tension candidate-producer
experiments (docs/product-refinement-v3.6.md item 5, section 6):
`rhythm_drum_ioi`, `rhythm_stem_autocorr`, `rhythm_vocal_onsets`,
`energy_level`, `tension_shape`.

Not an experiment itself — no queue row, no UI lane, no README. Wraps
`experiments/segment_seeds/features.py`'s seed-rule math (`SUBDIVISIONS`,
`MIN_AUTOCORR`) with a per-row **confidence**, which the seed writer did not
need (it writes one fixed value per row, never scored against itself). Every
function documents its own confidence formula; callers must not invent a
constant.
"""
from __future__ import annotations

import numpy as np

from experiments.segment_seeds.features import MIN_AUTOCORR, SUBDIVISIONS


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def subdivision_from_ratio(
    ratio: float | None, *, below_frac: float | None = None
) -> tuple[str | None, float | None]:
    """Nearest `SUBDIVISIONS` name to `ratio` (an IOI / beat-period fraction)
    by log-distance, same rule as `segment_seeds.features.nearest_subdivision`.
    Confidence = normalised margin between the best and second-best
    candidate's log-distance: `(d2 - d1) / (d2 + d1)`, clamped to [0, 1] — 0
    when the two nearest candidates are equidistant (genuinely ambiguous), 1
    when the best is an exact hit and the rest are far.

    `below_frac` (0..1): when the caller has already decided "none" (an onset
    rate below its 1-per-bar/beat floor), pass the rate as a fraction of that
    floor instead of a ratio; confidence is then the honest "how far below
    the floor" = `1 - below_frac`.
    """
    if below_frac is not None:
        return "none", round(_clamp01(1.0 - below_frac), 4)
    if ratio is None or ratio <= 0:
        return None, None
    dists = sorted(
        (abs(np.log(ratio) - np.log(target)), name)
        for name, target in SUBDIVISIONS.items()
    )
    best_dist, best_name = dists[0]
    second_dist = dists[1][0] if len(dists) > 1 else best_dist + 1.0
    denom = best_dist + second_dist
    conf = (second_dist - best_dist) / denom if denom > 0 else 0.0
    return best_name, round(_clamp01(conf), 4)


def dominant_ioi_ratio(onset_times: list[float], beat_period: float) -> float | None:
    """Median inter-onset interval of `onset_times`, divided by
    `beat_period`. `None` when fewer than 2 onsets or no positive gaps."""
    times = sorted(onset_times)
    if len(times) < 2 or not beat_period or beat_period <= 0:
        return None
    iois = np.diff(np.array(times, dtype=float))
    iois = iois[iois > 0]
    if iois.size == 0:
        return None
    return float(np.median(iois)) / beat_period


def autocorr_subdivision(
    xs: np.ndarray, interval_s: float, beat_period: float | None
) -> tuple[str | None, float | None]:
    """Strongest sub-beat autocorrelation peak of `xs` (a loudness curve at
    `interval_s` spacing) among `SUBDIVISIONS` lags of `beat_period` — same
    scan as `segment_seeds.features.stem_rhythm`. Confidence = normalised
    margin between the best and second-best candidate's correlation:
    `(c1 - c2) / (|c1| + |c2|)`, clamped [0, 1]. Below `MIN_AUTOCORR` ->
    `"none"`, confidence = honest distance below that floor:
    `1 - best_corr / MIN_AUTOCORR` (clamped)."""
    if xs.size < 8 or not beat_period or beat_period <= 0:
        return None, None
    xs = xs - xs.mean()
    denom = float(np.sum(xs * xs))
    if denom <= 1e-9:
        return "none", 0.0
    scored: list[tuple[float, str]] = []
    for name, frac in SUBDIVISIONS.items():
        lag = int(round((beat_period * frac) / interval_s))
        if lag <= 0 or lag >= xs.size:
            continue
        a, b = xs[:-lag], xs[lag:]
        corr = float(np.sum(a * b) / denom)
        scored.append((corr, name))
    if not scored:
        return None, None
    scored.sort(reverse=True)
    best_corr, best_name = scored[0]
    second_corr = scored[1][0] if len(scored) > 1 else -1.0
    if best_corr < MIN_AUTOCORR:
        return "none", round(_clamp01(1.0 - best_corr / MIN_AUTOCORR), 4)
    denom2 = abs(best_corr) + abs(second_corr)
    conf = (best_corr - second_corr) / denom2 if denom2 > 0 else 0.0
    return best_name, round(_clamp01(conf), 4)


def quintile_with_margin(raw_scores: list[float]) -> list[tuple[int, float]]:
    """Song-relative rank -> 1-5 bin, same rule as
    `segment_seeds.features.quintile_bin` (stable tie order, deterministic),
    paired with a confidence = `2 * distance from the nearest bin boundary`
    in bin-fraction space: 0 right at a boundary (could tip either way), 1 at
    a bin's centre."""
    n = len(raw_scores)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: (raw_scores[i], i))
    out: list[tuple[int, float]] = [(0, 0.0)] * n
    for rank, i in enumerate(order):
        frac = (rank + 0.5) / n
        bin_frac = frac * 5.0
        b = min(5, max(1, int(np.ceil(bin_frac))))
        dist = min(bin_frac - np.floor(bin_frac), np.ceil(bin_frac) - bin_frac)
        conf = round(_clamp01(2.0 * float(dist)), 4)
        out[i] = (b, conf)
    return out
