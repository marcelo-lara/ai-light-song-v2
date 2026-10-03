import numpy as np

from experiments.light_changes import detect


def bar(i, *, mix=0.05, low=0.8, high=0.5, bright=0.5, hits=(4, 2, 8), dur=2.0, entered=(), left=()):
    bands = [low, low, 0.6, 0.6, high, high, high]
    return {
        "bar": i + 1, "start_s": i * 2.0, "end_s": i * 2.0 + dur, "beats_in_bar": 4, "irregular": False,
        "loud_rms": {"mix": mix, "bass": mix / 2, "drums": mix / 3, "harmonic": mix, "vocals": mix / 4},
        "bands": {s: list(bands) for s in ("mix", "bass", "drums", "harmonic", "vocals")},
        "brightness": bright, "transient_mean": 0.01, "transient_std": 0.02,
        "kick": hits[0], "snare": hits[1], "hat": hits[2], "vocals_cover": 1.0,
        "entered": list(entered), "left": list(left),
    }


def _jitter(n, seed=0):
    r = np.random.default_rng(seed)
    return [bar(i, mix=0.05 + r.normal(0, 0.001), bright=0.5 + r.normal(0, 0.01),
                high=0.5 + r.normal(0, 0.01), low=0.8 + r.normal(0, 0.01),
                hits=(4 + int(r.integers(0, 2)), 2, 8 + int(r.integers(0, 2)))) for i in range(n)]


def test_steady_song_yields_no_points():
    assert detect.detect(_jitter(40), None) == []


def test_step_change_fires_once_then_new_state_is_not_reflagged():
    bars = _jitter(40)
    for i in range(20, 40):  # sub drops out, brightness collapses, kick stops: a break
        bars[i] = bar(i, mix=0.03, low=0.2, high=0.2, bright=0.2, hits=(0, 0, 2))
    pts = detect.detect(bars, None)
    assert [p["bar"] for p in pts] == [21]
    assert pts[0]["role"] in ("break", "gap")


def test_drop_after_break_is_labelled_drop():
    bars = _jitter(40)
    for i in range(10, 20):
        bars[i] = bar(i, mix=0.03, low=0.1, high=0.3, bright=0.3, hits=(0, 0, 1))
    for i in range(20, 40):
        bars[i] = bar(i, mix=0.08, low=0.95, high=0.7, bright=0.6, hits=(6, 3, 10))
    pts = {p["bar"]: p for p in detect.detect(bars, None)}
    assert 21 in pts and pts[21]["role"] == "drop"


def test_one_bar_gap_is_labelled_gap():
    bars = _jitter(30)
    bars[15] = bar(15, mix=0.01, low=0.1, high=0.1, bright=0.3, hits=(0, 0, 0))
    pts = {p["bar"]: p for p in detect.detect(bars, None)}
    assert pts[16]["role"] == "gap"


def test_short_window_is_merged_so_the_point_lands_where_the_slip_starts():
    bars = _jitter(30)
    for i in range(16, 30):
        bars[i] = bar(i, mix=0.03, low=0.2, high=0.2, bright=0.2, hits=(0, 0, 2))
    bars[16]["end_s"] = bars[16]["start_s"] + 0.5   # a 1-beat window
    bars[16]["irregular"] = True
    pts = detect.detect(bars, None)
    assert pts and pts[0]["bar"] == 17 and pts[0]["time_s"] == bars[16]["start_s"]
    assert pts[0]["irregular_bar"] is True


def test_loudness_only_baseline_ignores_non_loudness_changes():
    bars = [bar(i, mix=0.05) for i in range(30)]
    for i in range(15, 30):
        bars[i] = bar(i, mix=0.05, low=0.2, high=0.9, bright=0.9, hits=(0, 0, 0))   # everything but level
    assert detect.detect_loudness_only(bars) == []
    assert detect.detect(bars, None) != []


def test_texture_novelty_is_one_sided():
    bars = _jitter(30)
    tex = [0.9] * 15 + [0.0] * 15          # novelty falling is not a change
    assert detect.detect(bars, tex) == []
