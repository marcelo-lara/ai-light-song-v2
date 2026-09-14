from __future__ import annotations

from experiments.truth_common import structure


def _truth():
    return [
        structure.TruthBoundary(time=10.0, label="Verse"),
        structure.TruthBoundary(time=20.0, label="Chorus"),
        structure.TruthBoundary(time=35.0, label="Bridge"),
    ]


def test_perfect_prediction_scores_one():
    predicted = [
        {"time": 10.1, "label": "verse"},
        {"time": 19.8, "label": "Chorus"},
        {"time": 35.0, "label": "Bridge"},
    ]
    score = structure.score_structure("fixture_song", predicted, truth=_truth(), tolerance=1.0)
    assert score.matched == 3
    assert score.precision == 1.0
    assert score.recall == 1.0
    assert score.f1 == 1.0
    assert score.label_matches == 3
    assert score.label_accuracy == 1.0


def test_missed_and_extra_boundaries_and_wrong_label():
    predicted = [
        {"time": 10.2, "label": "Chorus"},  # matches 10.0 but wrong label
        {"time": 50.0, "label": "Outro"},  # extra, no truth nearby
        # 20.0 and 35.0 truth boundaries are missed entirely
    ]
    score = structure.score_structure("fixture_song", predicted, truth=_truth(), tolerance=1.0)
    assert score.matched == 1
    assert score.n_predicted == 2
    assert score.n_truth == 3
    assert score.precision == 0.5
    assert score.recall == 1 / 3
    assert score.label_matches == 0
    assert score.label_accuracy == 0.0


def test_out_of_vocabulary_label_flagged():
    predicted = [{"time": 10.0, "label": "Glorpsection"}]
    score = structure.score_structure(
        "fixture_song", predicted, truth=_truth(), tolerance=1.0, vocabulary={"verse", "chorus", "bridge"}
    )
    assert score.out_of_vocab_predicted == 1


def test_corpus_row_is_micro_averaged_not_mean_of_f1():
    song_a = structure.score_structure(
        "a", [{"time": 10.0, "label": "verse"}], truth=[structure.TruthBoundary(10.0, "Verse")]
    )
    song_b = structure.score_structure(
        "b",
        [{"time": 100.0, "label": "x"}],
        truth=[structure.TruthBoundary(1.0, "Verse"), structure.TruthBoundary(2.0, "Chorus")],
    )
    row = structure.corpus_row([song_a, song_b])
    # pooled: matched=1, predicted=2, truth=3
    assert row["matched"] == 1
    assert row["precision"] == 0.5
    assert row["recall"] == 1 / 3
