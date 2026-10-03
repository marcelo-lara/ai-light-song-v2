import numpy as np

from experiments.bar_features import features


def _beats(bars_beats):
    """bars_beats: list of (bar, n_beats); 0.5 s beats."""
    out, t = [], 0.0
    for bar, n in bars_beats:
        for k in range(n):
            out.append({"time": t, "bar": bar, "beat": k + 1, "type": "beat", "downbeat_confidence": None})
            t += 0.5
    return out


def test_bar_windows_flag_slipped_bar_and_never_repair():
    bars, halves = features.build_windows(_beats([(1, 4), (2, 4), (3, 1), (4, 4), (5, 4)]))
    assert [b["beats_in_bar"] for b in bars] == [4, 4, 1, 4, 4]
    assert [b["irregular"] for b in bars] == [False, False, True, False, False]
    assert bars[2]["end_s"] - bars[2]["start_s"] == 0.5          # the 1-beat bar keeps its real length
    assert len(halves) == 2 * 17
    assert halves[0]["end_s"] == halves[1]["start_s"] == 0.25


def test_last_window_ends_one_median_beat_after_last_beat():
    bars, _ = features.build_windows(_beats([(1, 4), (2, 4)]))
    assert bars[-1]["end_s"] == 4.0


def test_frame_means_window_semantics():
    times = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
    vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    wins = np.array([[0.0, 0.2], [0.2, 0.5], [9.0, 10.0]])
    out = features._frame_means(times, vals, wins)
    assert out[0] == 1.5 and out[1] == 4.0 and np.isnan(out[2])  # [s, e), empty window is NaN not 0


def test_frame_means_multicolumn():
    times = np.array([0.0, 1.0])
    vals = np.array([[1.0, 10.0], [3.0, 30.0]])
    out = features._frame_means(times, vals, np.array([[0.0, 2.0]]))
    assert out.tolist() == [[2.0, 20.0]]


def test_cover_unions_overlapping_spans():
    assert features._cover([(0, 2), (1, 3)], 0, 4) == 0.75
    assert features._cover([], 0, 4) == 0.0
    assert features._cover([(5, 6)], 0, 4) == 0.0
