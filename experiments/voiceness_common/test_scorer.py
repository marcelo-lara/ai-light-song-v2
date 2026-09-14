"""Unit tests for `scorer.py`'s arithmetic, against synthetic ground truth and
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


def _truth(positive=(), residual=(), negative=()) -> scorer.GroundTruth:
    positive, residual, negative = list(positive), list(residual), list(negative)
    evaluable = scorer._merge_spans(positive + residual + negative)
    return scorer.GroundTruth(positive=positive, residual=residual, negative=negative, evaluable=evaluable)


def test_perfect_match_scores_one():
    marked_spans = [(1.0, 2.0), (4.0, 5.0)]
    phrases = [{"start": 1.0, "end": 2.0}, {"start": 4.0, "end": 5.0}]
    times = [round(i * 0.05, 3) for i in range(120)]  # 0.0 .. 5.95s
    frames = _grid(times, marked_spans)
    truth = _truth(positive=marked_spans, negative=[(0.0, 1.0), (2.0, 4.0), (5.0, 6.0)])

    result = scorer.score(frames, phrases, truth, duration_s=6.0)

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
    frames = _grid(times, [(10.0, 11.0)])
    # Every frame outside the marked span is a declared negative, so the
    # entire song is evaluable — matches the old implicit-negative behaviour
    # for this test.
    truth = _truth(positive=marked_spans, negative=[(0.0, 1.0), (2.0, 12.0)])

    result = scorer.score(frames, phrases, truth, duration_s=12.0)

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
    So accuracy = 7/9, false_vocal_rate = 1/9, over all 9 evaluable frames
    (the whole grid is declared negative outside the positive span, so
    nothing is excluded).
    """
    marked_spans = [(1.0, 3.0)]
    phrases = [{"start": 1.2, "end": 3.6}]
    times = [round(i * 0.5, 3) for i in range(9)]  # 0.0 .. 4.0
    frames = _grid(times, [(1.2, 3.6)])
    truth = _truth(positive=marked_spans, negative=[(0.0, 1.0), (3.0, 4.0)])

    result = scorer.score(frames, phrases, truth, duration_s=4.0)

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
    """bounds/min now normalizes against evaluable duration, not song
    duration — evaluable here is only the two 1s spans (2s total = 1/60 min),
    so 4 predicted edges over 1/30 min."""
    marked_spans = [(1.0, 2.0)]
    phrases = [{"start": 1.0, "end": 2.0}, {"start": 5.0, "end": 6.0}]
    times = [round(i * 0.05, 3) for i in range(240)]
    frames = _grid(times, [(1.0, 2.0), (5.0, 6.0)])
    truth = _truth(positive=marked_spans, negative=[(5.0, 6.0)])

    result = scorer.score(frames, phrases, truth, duration_s=120.0)

    assert result.n_phrase_edges == 4
    evaluable_minutes = 2.0 / 60.0
    assert result.bounds_per_min == pytest.approx(4 / evaluable_minutes)


def test_residual_excluded_from_numerator_and_denominator():
    """A candidate that fires (voiced) throughout a residual span must not be
    charged as a false vocal, and the residual frames must not enter
    frame_accuracy's denominator either.

    Span boundaries are offset half a grid-step off the sample times
    (-.05/.95/1.95) so no frame lands exactly on a boundary — overlap
    precedence is exercised separately in
    `test_overlap_precedence_positive_beats_unknown_beats_negative`.
    """
    positive = [(-0.05, 0.95)]
    residual = [(0.95, 1.95)]
    negative = [(1.95, 2.95)]
    times = [round(i * 0.1, 3) for i in range(30)]  # 0.0 .. 2.9
    # candidate calls everything voiced (fires through residual and negative)
    frames = [(t, 1.0) for t in times]
    truth = _truth(positive=positive, residual=residual, negative=negative)

    result = scorer.score(frames, phrases=[], truth=truth, duration_s=3.0)

    # scored frames = positive (10, all correct) + negative (10, all wrong)
    assert result.n_frames_residual == 10
    assert result.n_frames_evaluable == 30  # positive + residual + negative
    assert result.frame_accuracy == pytest.approx(10 / 20)
    assert result.false_vocal_rate == pytest.approx(10 / 20)
    assert result.residual_firing_rate == pytest.approx(1.0)


def test_unknown_time_excluded_entirely():
    """Time outside every declared span (unreviewed, or explicitly mapped
    'unknown') is not in `evaluable` and must not appear in any denominator."""
    positive = [(-0.05, 0.95)]
    negative = [(0.95, 1.95)]
    # 2.0-4.9 is unknown/unreviewed
    times = [round(i * 0.1, 3) for i in range(50)]  # 0.0 .. 4.9
    frames = [(t, 1.0) for t in times]  # fires everywhere, including unknown
    truth = _truth(positive=positive, negative=negative)

    result = scorer.score(frames, phrases=[], truth=truth, duration_s=5.0)

    assert result.n_frames_unknown == 30  # 2.0..4.9 in 0.1s steps
    assert result.n_frames_evaluable == 20  # only 0.0-1.9
    # false_vocal_rate must not count any of the unknown firing.
    assert result.false_vocal_rate == pytest.approx(10 / 20)


def test_overlap_precedence_positive_beats_unknown_beats_negative():
    """Armin-style overlap: a positive span and a differently-classed span
    covering the same time. Precedence: positive > residual > negative >
    unknown, resolved per frame."""
    truth = _truth(positive=[(1.0, 3.0)], negative=[(2.0, 4.0)])
    # t=2.5 is inside both positive [1,3] and negative [2,4] -> must resolve
    # to positive.
    assert truth.classify(2.5) == "positive"
    # t=3.5 is inside negative only -> negative.
    assert truth.classify(3.5) == "negative"
    # t=5.0 is inside nothing -> unknown.
    assert truth.classify(5.0) == "unknown"

    truth2 = _truth(residual=[(1.0, 3.0)], negative=[(2.0, 4.0)])
    # residual beats negative on overlap.
    assert truth2.classify(2.5) == "residual"


def test_fail_loud_on_unclassified_hint():
    doc = {
        "human_hints": [
            {"id": "hint-001", "start_time": 0.0, "end_time": 1.0, "type": "vocal"},
            {"id": "hint-002", "start_time": 1.0, "end_time": 2.0},  # no type, not in map
        ]
    }
    with pytest.raises(ValueError, match="hint-002"):
        scorer.ground_truth(doc, "some_song", class_map={"some_song": {}})


def test_fail_loud_on_map_naming_nonexistent_hint():
    doc = {
        "human_hints": [
            {"id": "hint-001", "start_time": 0.0, "end_time": 1.0, "type": "vocal"},
        ]
    }
    with pytest.raises(ValueError, match="hint-999"):
        scorer.ground_truth(doc, "some_song", class_map={"some_song": {"hint-999": "negative"}})


def test_ground_truth_classifies_residual_negative_unknown():
    doc = {
        "human_hints": [
            {"id": "hint-001", "start_time": 0.0, "end_time": 1.0, "type": "vocal"},
            {"id": "hint-002", "start_time": 1.0, "end_time": 2.0},  # residual
            {"id": "hint-003", "start_time": 2.0, "end_time": 3.0},  # negative
            {"id": "hint-004", "start_time": 3.0, "end_time": 4.0},  # unknown
        ]
    }
    class_map = {"some_song": {"hint-002": "residual", "hint-003": "negative", "hint-004": "unknown"}}
    truth = scorer.ground_truth(doc, "some_song", class_map)

    assert truth.positive == [(0.0, 1.0)]
    assert truth.residual == [(1.0, 2.0)]
    assert truth.negative == [(2.0, 3.0)]
    # unknown (hint-004) contributes nothing to evaluable.
    assert truth.evaluable == [(0.0, 3.0)]


def test_predicted_edge_in_unknown_time_ignored():
    """A predicted phrase edge that lands outside `evaluable` must not count
    in either the precision numerator or denominator."""
    truth = _truth(positive=[(1.0, 2.0)], negative=[(2.0, 3.0)])
    # phrase edges at 1.0 and 2.0 fall in evaluable; edges at 10.0 (well
    # outside evaluable, unknown time) must be dropped before scoring.
    phrases = [{"start": 1.0, "end": 2.0}, {"start": 10.0, "end": 10.5}]

    times = [round(i * 0.1, 3) for i in range(30)]
    frames = _grid(times, [(1.0, 2.0)])

    result = scorer.score(frames, phrases, truth, duration_s=30.0)

    # 2 raw edges are evaluable (1.0, 2.0); 2 are dropped (10.0, 10.5).
    assert result.n_phrase_edges == 4
    assert result.n_phrase_edges_evaluable == 2
    # bounds/min counts only the evaluable edges, over evaluable minutes —
    # never the raw count over an evaluable-only denominator.
    assert result.bounds_per_min == pytest.approx(2 / (2.0 / 60.0))
    for tol in (0.25, 0.5, 1.0):
        b = result.boundary[tol]
        assert b.precision == pytest.approx(1.0)
        assert b.recall == pytest.approx(1.0)


def test_empty_frames_and_spans_do_not_crash():
    truth = _truth()
    result = scorer.score([], [], truth)
    assert result.frame_accuracy == 0.0
    assert result.false_vocal_rate == 0.0
    assert result.residual_firing_rate == 0.0
    assert result.n_frames == 0
    for tol in (0.25, 0.5, 1.0):
        assert result.boundary[tol].f1 == 0.0
