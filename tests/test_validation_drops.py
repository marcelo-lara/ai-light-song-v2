from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.validation.drops import (
    detected_drops,
    labelled_drop_times,
    score_drops,
    validate_drops,
)


def _timeline(events: list[dict]) -> dict:
    return {"schema_version": "1.0", "events": events}


class DropScoringTests(unittest.TestCase):
    def test_labelled_drop_times_ignores_fake(self) -> None:
        hints = [
            {"title": "Drop in", "summary": "", "start_time": 28.8},
            {"title": "Fake drop", "summary": "withheld release", "start_time": 40.0},
            {"title": "build up", "summary": "", "start_time": 22.0},
        ]
        self.assertEqual(labelled_drop_times(hints), [28.8])

    def test_detected_drops_reads_type_and_composite_phase(self) -> None:
        timeline = _timeline([
            {"type": "drop", "start_time": 30.0, "confidence": 0.9},
            {"type": "fake_drop", "start_time": 50.0},
            {"type": "composite_drop", "start_time": 60.0, "phases": [
                {"phase": "build", "start_time": 58.0},
                {"phase": "impact", "start_time": 61.5},
            ]},
        ])
        times = [d["time"] for d in detected_drops(timeline)]
        self.assertEqual(times, [30.0, 61.5])

    def test_timed_mode_precision_recall(self) -> None:
        timeline = _timeline([
            {"type": "drop", "start_time": 28.9, "confidence": 0.8},
            {"type": "drop", "start_time": 90.0, "confidence": 0.4},
        ])
        score = score_drops(timeline, [{"title": "Drop in", "start_time": 28.8}])
        self.assertEqual(score["mode"], "timed")
        self.assertEqual(score["metrics"]["true_positives"], 1)
        self.assertEqual(score["metrics"]["recall"], 1.0)
        self.assertEqual(score["metrics"]["precision"], 0.5)

    def test_no_timed_hints_reports_unlabelled_never_presence(self) -> None:
        # Plan v3.0 item 10: the old `presence` fallback against the
        # song-level `has_drop` fact passed by construction (any detector
        # that fires once on a `has_drop: true` song "matched") and is gone.
        # A song with no timed drop hints scores `unlabelled`, full stop.
        timeline = _timeline([{"type": "drop", "start_time": 12.0}])
        score = score_drops(timeline, [])
        self.assertEqual(score["mode"], "unlabelled")
        self.assertNotIn("presence_ok", score)

    def test_fake_outnumbers_drop_flag(self) -> None:
        timeline = _timeline([
            {"type": "drop", "start_time": 10.0},
            {"type": "fake_drop", "start_time": 20.0},
            {"type": "fake_drop", "start_time": 30.0},
        ])
        score = score_drops(timeline, [])
        self.assertTrue(score["fake_outnumbers_drop"])


class ValidateAdapterTests(unittest.TestCase):
    def test_validate_drops_skips_without_timed_labels_and_scores_with_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            out = paths.song_output_dir
            out.mkdir(parents=True)
            paths.timeline_output_path.write_text(json.dumps(_timeline([
                {"type": "drop", "start_time": 28.5, "confidence": 0.9},
            ])))

            # No reference/human at all -> skipped.
            self.assertEqual(validate_drops(paths).status, "skipped")

            human = paths.reference("human")
            human.mkdir(parents=True)
            (human / "human_hints.json").write_text(json.dumps({
                "song_name": "_test_song",
                "human_hints": [{"title": "build up", "summary": "energy rising", "start_time": 5.0}],
            }))

            # Human hints exist, but none of them are timed drop labels ->
            # still skipped, not a presence check against has_drop.
            result = validate_drops(paths)
            self.assertEqual(result.status, "skipped")
            self.assertEqual(result.diagnostics["reason"], "no timed human drop hints")

            (human / "human_hints.json").write_text(json.dumps({
                "song_name": "_test_song",
                "human_hints": [{"title": "Drop in", "start_time": 28.4}],
            }))
            drops_result = validate_drops(paths)
            self.assertEqual(drops_result.status, "passed")
            self.assertTrue(paths.artifact("validation", "drops_score.json").exists())


if __name__ == "__main__":
    unittest.main()
