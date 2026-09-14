from __future__ import annotations

from experiments.truth_common import drop_stages


def _truth_one_drop():
    return [
        drop_stages.StageEvent("approach", 10.0),
        drop_stages.StageEvent("build", 15.0),
        drop_stages.StageEvent("tension", 20.0),
        drop_stages.StageEvent("impact", 22.0),
        drop_stages.StageEvent("release", 23.0),
    ]


def test_perfect_prediction_scores_one_per_stage():
    predicted = [
        {"stage": "approach", "time": 10.2},
        {"stage": "build", "time": 14.8},
        {"stage": "tension", "time": 20.3},
        {"stage": "impact", "time": 22.1},
        {"stage": "release", "time": 22.9},
    ]
    scores = drop_stages.score_drop_stages("fixture_song", predicted, truth=_truth_one_drop())
    assert len(scores) == 5
    for s in scores:
        assert s.matched == 1
        assert s.precision == 1.0
        assert s.recall == 1.0
        assert s.f1 == 1.0


def test_missing_stage_reports_zero_not_omitted():
    predicted = [{"stage": "approach", "time": 10.0}]
    scores = drop_stages.score_drop_stages("fixture_song", predicted, truth=_truth_one_drop())
    by_stage = {s.stage: s for s in scores}
    assert set(by_stage) == set(drop_stages.STAGES)
    assert by_stage["impact"].n_predicted == 0
    assert by_stage["impact"].n_truth == 1
    assert by_stage["impact"].precision is None
    assert by_stage["impact"].recall == 0.0


def test_stage_title_parsing_matches_validation_drops_convention():
    """Only hints titled exactly 'drop <stage>' (case-insensitive) count."""
    doc = {
        "human_hints": [
            {"id": "hint-001", "title": "Drop Approach", "start_time": 1.0, "end_time": 2.0},
            {"id": "hint-002", "title": "not a drop stage", "start_time": 3.0, "end_time": 4.0},
        ]
    }
    events = [
        drop_stages.StageEvent(stage=drop_stages.STAGE_TITLES[h["title"].strip().lower()], time=h["start_time"])
        for h in doc["human_hints"]
        if h["title"].strip().lower() in drop_stages.STAGE_TITLES
    ]
    assert events == [drop_stages.StageEvent("approach", 1.0)]
