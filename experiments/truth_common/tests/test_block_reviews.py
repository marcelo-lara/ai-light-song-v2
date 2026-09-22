from __future__ import annotations

from experiments.truth_common import block_reviews as br


def _reviews():
    return [
        br.BlockReview(lane_id="gestures", start=7.86, verdict="correct", reason=None),
        br.BlockReview(lane_id="gestures", start=9.288, verdict="wrong", reason="boundary"),
        br.BlockReview(lane_id="gestures", start=15.232, verdict="misplaced", reason="label"),
        # no current block within +-0.25s of this start -> stale
        br.BlockReview(lane_id="gestures", start=999.999, verdict="correct", reason=None),
    ]


def _starts():
    return {"gestures": [7.86, 9.288, 15.232, 17.05]}


def test_precision_matches_hand_count_on_the_item_1_fixture():
    """Mirrors the RegFull UI fixture (tests/ui-visual/fixtures/build-
    fixtures.py `inject_block_reviews`): 1 correct, 1 wrong, 1 misplaced,
    1 stale. Reviewed = 3 (stale excluded); precision = correct/reviewed = 1/3."""
    scores = br.score_song("fixture-song", reviews=_reviews(), block_starts=_starts())
    by_lane = {s.lane_id: s for s in scores}
    gestures = by_lane["gestures"]

    assert gestures.block_count == 4
    assert gestures.reviewed == 3
    assert gestures.stale == 1
    assert gestures.correct == 1
    assert gestures.wrong == 1
    assert gestures.misplaced == 1
    assert gestures.precision == 1 / 3


def test_stale_review_excluded_from_scored_count_never_dropped_or_reattached():
    reviews = [br.BlockReview(lane_id="gestures", start=500.0, verdict="correct", reason=None)]
    scores = br.score_song("fixture-song", reviews=reviews, block_starts=_starts())
    gestures = next(s for s in scores if s.lane_id == "gestures")
    assert gestures.stale == 1
    assert gestures.reviewed == 0
    assert gestures.correct == 0
    assert gestures.precision is None


def test_unreviewed_producer_emits_zero_reviewed_perfect_precision_is_never_claimed():
    """A lane that emitted blocks but got no reviews yet: block_count > 0,
    reviewed == 0, precision is None (never 0/0 -> misleadingly reported as a
    number)."""
    scores = br.score_song("fixture-song", reviews=[], block_starts=_starts())
    gestures = next(s for s in scores if s.lane_id == "gestures")
    assert gestures.block_count == 4
    assert gestures.reviewed == 0
    assert gestures.precision is None


def test_wrong_reported_separately_from_misplaced():
    reviews = [
        br.BlockReview(lane_id="gestures", start=7.86, verdict="wrong", reason="boundary"),
        br.BlockReview(lane_id="gestures", start=9.288, verdict="misplaced", reason="value"),
    ]
    scores = br.score_song("fixture-song", reviews=reviews, block_starts=_starts())
    gestures = next(s for s in scores if s.lane_id == "gestures")
    assert gestures.wrong == 1
    assert gestures.misplaced == 1


def test_malformed_review_rows_are_dropped_not_crashed_on(tmp_path, monkeypatch):
    import json

    song_dir = tmp_path / "data" / "analysis" / "fixture-song" / "reference" / "human"
    song_dir.mkdir(parents=True)
    (song_dir / "block_reviews.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "song_name": "fixture-song",
                "reviews": [
                    {"lane_id": "gestures", "start": 7.86, "verdict": "correct", "reason": None},
                    {"start": 1.0, "verdict": "correct"},  # missing lane_id -> dropped
                    {"lane_id": "gestures", "start": 2.0, "verdict": "not-a-verdict"},  # dropped
                ],
            }
        )
    )
    monkeypatch.setattr(br.paths, "ANALYSIS_ROOT", tmp_path / "data" / "analysis")
    reviews = br.load_reviews("fixture-song")
    assert len(reviews) == 1
    assert reviews[0].start == 7.86
