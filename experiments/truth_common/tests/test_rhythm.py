from __future__ import annotations

import pytest

from experiments.truth_common import rhythm


def _truth():
    return [
        rhythm.RhythmSegment(
            "fixture", 0.0, 10.0, subdivisions={"drums": "quarter", "bass": "half"},
            source="human", provisional=False,
        ),
        rhythm.RhythmSegment(
            "fixture", 10.0, 20.0, subdivisions={"drums": "sixteenth"},
            source="seed", provisional=True,
        ),
    ]


def test_exact_match_per_source():
    predicted = [
        {"start": 0.0, "end": 10.0, "subdivisions": {"drums": "quarter", "bass": "quarter"}},
        {"start": 10.0, "end": 20.0, "subdivisions": {"drums": "sixteenth"}},
    ]
    scores = rhythm.score_rhythm("fixture", predicted, truth=_truth())
    by = {(s.source, s.truth_origin): s for s in scores}

    assert by[("drums", "human")].exact_match == 1
    assert by[("bass", "human")].exact_match == 0  # quarter != half
    assert by[("drums", "seed")].provisional is True
    assert by[("drums", "seed")].exact_match == 1


def test_invalid_subdivision_fails_loud():
    with pytest.raises(ValueError):
        rhythm._validate_subdivisions({"drums": "not_a_subdivision"}, "test fixture")


def test_missing_seed_file_produces_no_seed_rows():
    truth = [
        rhythm.RhythmSegment(
            "fixture", 0.0, 10.0, subdivisions={"drums": "quarter"}, source="human", provisional=False
        )
    ]
    scores = rhythm.score_rhythm("fixture", [{"start": 0.0, "end": 10.0, "subdivisions": {"drums": "quarter"}}], truth=truth)
    assert all(s.truth_origin != "seed" for s in scores)
