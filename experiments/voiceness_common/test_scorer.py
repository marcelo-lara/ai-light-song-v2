"""Unit tests for `scorer.py`'s arithmetic, against synthetic marked spans and
synthetic predictions with hand-computed expected values — no real candidate
depends on this scorer until these pass.

Naming matches `experiments/vocal_phrases`'s convention of colocating tests
with the module they cover (no separate `tests/` package under
`experiments/`).
"""
from __future__ import annotations

import pytest

from . import scorer


def _grid(times: list[float], voiced_spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Build (time, voiceness) frames: 1.0 inside any of `voiced_spans`, else 0.0."""
    frames = []
    for t in times:
        v = 1.0 if any(s <= t <= e for s, e in voiced_spans) else 0.0
        frames.append((t, v))
    return frames


def test_perfect_match_scores_one():
    marked_spans = [(1.0, 2.0), (4.0, 5.0)]
    phrases = [{"start": 1.0, "end": 2.0}, {"start": 4.0, "end": 5.0}]
    times = [round(i * 0.05, 3) for i in range(120)]  # 0.0 .. 5.95s
    frames = _grid(times, marked_spans)

    result = scorer.score(frames, phrases, marked_spans, duration_s=6.0)

    assert result.frame_accuracy == pytest.approx(1.0)
    assert result.false_vocal_rate == pytest.approx(0.0)
    for tol in (0.25, 0.5, 1.0):
        b = result.boundary[tol]
        assert b.precision == pytest.approx(1.0)
        assert b.recall == pytest.approx(1.0)
        assert b.f1 == pytest.approx(1.0)


def test_no_overlap_scores_zero_boundary_f1():
    marked_spans = [(1.0, 2.0)]
    phrases = [{"start": 10.0, "end": 11.0}]
    times = [round(i * 0.05, 3) for i in range(240)]  # 0.0 .. 11.95s
    frames = _grid(times, phrases_as_spans := [(10.0, 11.0)])

    result = scorer.score(frames, phrases, marked_spans, duration_s=12.0)

    # every voiced frame (inside the predicted phrase) sits outside the
    # marked span, and every marked frame is called unvoiced.
    assert result.frame_accuracy < 1.0
    assert result.false_vocal_rate > 0.0
    for tol in (0.25, 0.5, 1.0):
        b = result.boundary[tol]
        assert b.f1 == pytest.approx(0.0)


def test_partial_overlap_hand_worked_boundary_f1():
    """span [1.0, 3.0] vs phrase [1.2, 3.6].

    Edge distances: |1.2-1.0| = 0.2, |3.6-3.0| = 0.6.
    - tol 0.25 / 0.5: only the start edge matches -> matched=1/2 each side
      -> precision=recall=0.5 -> F1=0.5.
    - tol 1.0: both edges match -> precision=recall=1.0 -> F1=1.0.

    Frames: 0.5s steps 0..4.0s (9 frames). Voiced (phrase [1.2, 3.6]):
    1.5, 2.0, 2.5, 3.0, 3.5 -> 5 frames. Truth (span [1.0, 3.0]):
    1.0, 1.5, 2.0, 2.5, 3.0 -> 5 frames.
    Mismatches: t=1.0 (truth, not voiced -> false negative),
                t=3.5 (voiced, not truth -> false vocal).
    So accuracy = 7/9, false_vocal_rate = 1/9.
    """
    marked_spans = [(1.0, 3.0)]
    phrases = [{"start": 1.2, "end": 3.6}]
    times = [round(i * 0.5, 3) for i in range(9)]  # 0.0 .. 4.0
    frames = _grid(times, [(1.2, 3.6)])

    result = scorer.score(frames, phrases, marked_spans, duration_s=4.0)

    assert result.frame_accuracy == pytest.approx(7 / 9)
    assert result.false_vocal_rate == pytest.approx(1 / 9)

    assert result.boundary[0.25].precision == pytest.approx(0.5)
    assert result.boundary[0.25].recall == pytest.approx(0.5)
    assert result.boundary[0.25].f1 == pytest.approx(0.5)

    assert result.boundary[0.5].precision == pytest.approx(0.5)
    assert result.boundary[0.5].recall == pytest.approx(0.5)
    assert result.boundary[0.5].f1 == pytest.approx(0.5)

    assert result.boundary[1.0].precision == pytest.approx(1.0)
    assert result.boundary[1.0].recall == pytest.approx(1.0)
    assert result.boundary[1.0].f1 == pytest.approx(1.0)


def test_bounds_per_min_reported_beside_f1():
    marked_spans = [(1.0, 2.0)]
    phrases = [{"start": 1.0, "end": 2.0}, {"start": 5.0, "end": 6.0}]
    times = [round(i * 0.05, 3) for i in range(240)]
    frames = _grid(times, [(1.0, 2.0), (5.0, 6.0)])

    result = scorer.score(frames, phrases, marked_spans, duration_s=120.0)  # 2 minutes

    # 4 predicted edges over 2 minutes.
    assert result.n_phrase_edges == 4
    assert result.bounds_per_min == pytest.approx(2.0)


def test_marked_vocal_spans_filters_type():
    doc = {
        "human_hints": [
            {"start_time": 1.0, "end_time": 2.0, "type": "vocal"},
            {"start_time": 3.0, "end_time": 4.0, "type": "hint"},
            {"start_time": 5.0, "end_time": 6.0, "type": "review"},
            {"start_time": 7.0, "end_time": 8.0},  # absent type -> not "vocal"
        ]
    }
    assert scorer.marked_vocal_spans(doc) == [(1.0, 2.0)]


def test_empty_frames_and_spans_do_not_crash():
    result = scorer.score([], [], [])
    assert result.frame_accuracy == 0.0
    assert result.false_vocal_rate == 0.0
    assert result.n_frames == 0
    for tol in (0.25, 0.5, 1.0):
        assert result.boundary[tol].f1 == 0.0
