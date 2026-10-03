import numpy as np
from scipy.signal import butter, sosfilt

from experiments.filter_sweep_v2 import aftermath, detect, features

SR = features.SR
BEAT = 0.5
BAR = 4 * BEAT


def _audio(cutoffs, level=None):
    """One bar of low-passed noise + a 150 Hz tone per cutoff; level scales a bar."""
    rng = np.random.default_rng(0)
    t = np.arange(int(BAR * SR)) / SR
    parts = []
    for i, fc in enumerate(cutoffs):
        noise = sosfilt(butter(4, fc, btype="low", fs=SR, output="sos"), rng.standard_normal(len(t)))
        bar = 0.3 * np.sin(2 * np.pi * 150 * t) + 0.1 * noise / max(np.abs(noise).max(), 1e-9) * 3
        parts.append(bar * (1.0 if level is None else level[i]))
    return np.concatenate(parts)


def _states(y, n_bars):
    beat_t = np.arange(n_bars * 4) * BEAT
    times, power, centres, _ = features.log_spectrogram(y, SR)
    rows = features.half_beat_rows(times, power, centres, beat_t)
    detect.add_log_columns(rows)
    row_bar = [r["beat_index"] // 4 for r in rows]
    sl = detect.bar_slopes(rows, row_bar, n_bars, BAR)
    return sl, detect.bar_states(sl)


def test_rising_cutoff_is_opening_and_flat_is_not():
    cut = list(np.geomspace(400, 9000, 12)) + [9000] * 4
    _, st = _states(_audio(cut), 16)
    assert st[3:11].count("opening") >= 6 and "closing" not in st
    _, flat = _states(_audio([3000] * 16), 16)
    assert all(s is None for s in flat)


def test_falling_cutoff_is_closing():
    cut = list(np.geomspace(9000, 400, 12)) + [400] * 4
    _, st = _states(_audio(cut), 16)
    assert st[3:11].count("closing") >= 6 and "opening" not in st


def test_dropout_bar_ends_the_run():
    cut = list(np.geomspace(400, 9000, 8)) + [9000] * 8
    level = [1.0] * 8 + [0.02] + [1.0] * 7
    sl, st = _states(_audio(cut, level), 16)
    assert sl[8]["dropout"] and st[8] is None
    assert all(s is None for s in st[8:])
    runs = detect.runs_of(st)
    assert runs and runs[0][2] == "opening" and runs[0][1] <= 7


def test_resonant_peak_found_and_sharper_than_noise():
    t = np.arange(SR) / SR
    rng = np.random.default_rng(1)
    peaky = rng.standard_normal(SR) * 0.05 + np.sin(2 * np.pi * 1500 * t)
    flat = rng.standard_normal(SR)
    times, power, centres, _ = features.log_spectrogram(peaky, SR)
    a = features.window_features(power[:, 5:30].mean(axis=1), centres)
    times, power, centres, _ = features.log_spectrogram(flat, SR)
    b = features.window_features(power[:, 5:30].mean(axis=1), centres)
    assert 1200 < a["peak_hz"] < 1900 and a["sharpness"] > b["sharpness"] + 5


def _bars(rms, kick=None):
    kick = kick or [False] * len(rms)
    return [{"loud_rms": {"mix": r}, "kick_present": k} for r, k in zip(rms, kick)]


def test_aftermath_gap_break_drop_none():
    base = [0.05, 0.05]
    assert aftermath.classify(_bars(base + [0.03, 0.05, 0.05]), 1) == "gap"
    assert aftermath.classify(_bars(base + [0.03, 0.03, 0.05]), 1) == "break"
    assert aftermath.classify(_bars(base + [0.05, 0.07, 0.05]), 1) == "drop"
    assert aftermath.classify(_bars(base + [0.05, 0.05, 0.05], [False, False, False, True, True]), 1) == "drop"
    assert aftermath.classify(_bars(base + [0.05, 0.05, 0.05]), 1) == "none"
    assert aftermath.classify(_bars(base), 1) == "none"  # run touches the end of the song


def test_end_kind_cut_vs_top():
    assert detect.end_kind("opening", 5.0, -3.0) == "cut"
    assert detect.end_kind("opening", 5.0, 4.0) == "top"
    assert detect.end_kind("closing", -5.0, 3.0) == "cut"
    assert detect.end_kind("opening", None, 4.0) == "top"
