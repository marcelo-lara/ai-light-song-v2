from __future__ import annotations

from experiments.truth_common import vocal_rhythm as vr


def _truth():
    return [
        vr.WordOnset(line_id=1, start=1.0, end=1.2),
        vr.WordOnset(line_id=1, start=1.3, end=1.5),
        vr.WordOnset(line_id=2, start=5.0, end=5.2),
    ]


def test_onset_f1_at_two_tolerances():
    predicted_onsets = [1.02, 1.38, 5.5]  # second is 0.08s off truth's 1.3, third is 0.5s off any truth
    scores = vr.score_vocal_rhythm("fixture", predicted_onsets, predicted_phrases=[], truth=_truth())
    by_tol = {s.tolerance_s: s for s in scores}

    assert by_tol[0.05].matched == 1  # only 1.02 (0.02s off 1.0) matches within 0.05
    assert by_tol[0.10].matched == 2  # 1.02 and 1.38 (0.08s off 1.3) both match within 0.10


def test_confidence_filter_excludes_non_curated_rows(tmp_path):
    import json

    doc = [
        {"id": 1, "line_id": 1, "start": 0.0, "end": 0.0, "text": "<SOL>", "confidence": None},
        {"id": 2, "line_id": 1, "start": 1.0, "end": 1.2, "text": "hi", "confidence": "0.99"},
        {"id": 3, "line_id": 1, "start": 1.3, "end": 1.5, "text": "low", "confidence": "0.5"},
        {"id": 4, "line_id": 1, "start": 1.6, "end": 1.6, "text": "<EOL>", "confidence": None},
    ]
    p = tmp_path / "lyrics.json"
    p.write_text(json.dumps(doc))

    import experiments.truth_common.paths as truth_paths

    original = truth_paths.human_lyrics_path
    truth_paths.human_lyrics_path = lambda song: p
    try:
        rows = vr.load_truth("Queen of Kings - Alessandra")
    finally:
        truth_paths.human_lyrics_path = original

    assert len(rows) == 1
    assert rows[0].start == 1.0


def test_missing_song_not_in_corpus_raises_key_error():
    import pytest

    with pytest.raises(KeyError):
        vr.load_truth("some song never in SCORING_CORPUS")
