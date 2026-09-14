from __future__ import annotations

from experiments.truth_common import texture


def _truth():
    return [
        texture.TextureSpan(start=0.0, end=10.0, title="No vocals"),
        texture.TextureSpan(start=10.0, end=25.0, title="Bass rhythm"),
    ]


def test_perfect_edges_score_one():
    predicted = [{"start": 0.1, "end": 9.9}, {"start": 10.1, "end": 24.8}]
    score = texture.score_texture("fixture_song", predicted, truth=_truth(), tolerance=1.0)
    assert score.matched == 4
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0


def test_partial_miss():
    predicted = [{"start": 0.1, "end": 40.0}]  # only start edge matches
    score = texture.score_texture("fixture_song", predicted, truth=_truth(), tolerance=1.0)
    assert score.matched == 1
    assert score.n_predicted_edges == 2
    assert score.n_truth_edges == 4
    assert score.precision == 0.5
    assert score.recall == 0.25


def test_vocal_and_drop_titled_hints_excluded_from_truth():
    import json
    import tempfile
    from pathlib import Path

    doc = {
        "human_hints": [
            {"id": "hint-001", "title": "Vocal phrase", "type": "vocal", "start_time": 0.0, "end_time": 1.0},
            {"id": "hint-002", "title": "drop approach", "start_time": 1.0, "end_time": 2.0},
            {"id": "hint-003", "title": "Bass rhythm", "start_time": 2.0, "end_time": 3.0},
        ]
    }
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "human_hints.json"
        p.write_text(json.dumps(doc))
        import experiments.truth_common.paths as truth_paths

        original = truth_paths.human_hints_path
        truth_paths.human_hints_path = lambda song: p
        try:
            rows = texture.load_truth("fixture_song")
        finally:
            truth_paths.human_hints_path = original

    assert [r.title for r in rows] == ["Bass rhythm"]
