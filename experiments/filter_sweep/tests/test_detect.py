import numpy as np

from experiments.filter_sweep import detect


def _series(n=400, ramp=(100, 200), depth=2.0, loud=None):
    cen = np.full(n, 6.0)
    cen[ramp[0]:ramp[1]] = np.linspace(6.0, 6.0 + depth, ramp[1] - ramp[0])
    cen[ramp[1]:] = 6.0 + depth
    lev = np.full(n, 0.5) if loud is None else loud
    return cen, lev


STEP, BAR = 0.25, 2.0  # 8 samples per bar


def test_opening_ramp_detected_on_flat_level():
    cen, lev = _series()
    rows = detect.detect_stem("harmonic", cen, lev, 0.5, STEP, BAR)
    assert len(rows) == 1 and rows[0]["direction"] == "opening"
    assert 1.5 <= rows[0]["depth"] <= 2.1


def test_closing_ramp_direction():
    cen, lev = _series()
    rows = detect.detect_stem("harmonic", 12.0 - cen, lev, 0.5, STEP, BAR)
    assert [r["direction"] for r in rows] == ["closing"]


def test_steady_centroid_yields_nothing():
    rng = np.random.default_rng(0)
    cen = 6.0 + rng.normal(0, 0.2, 400)
    assert detect.detect_stem("harmonic", cen, np.full(400, 0.5), 0.5, STEP, BAR) == []


def test_loudness_ramp_is_not_a_sweep():
    cen, _ = _series()
    lev = np.full(400, 0.1)
    lev[100:200] = np.linspace(0.1, 1.0, 100)  # the stem fades in as it brightens: entry, not a filter move
    lev[200:] = 1.0
    assert detect.detect_stem("harmonic", cen, lev, 1.0, STEP, BAR) == []


def test_too_short_move_rejected():
    cen, lev = _series(ramp=(100, 101))  # instant jump = a cut, not a sweep
    assert detect.detect_stem("harmonic", cen, lev, 0.5, STEP, BAR) == []
