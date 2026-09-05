from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.validation.form_drops import (
    confidence_calibration,
    detected_drops,
    labelled_boundaries,
    labelled_drop_times,
    score_drops,
    score_form,
    validate_drops,
    validate_form,
)


def _timeline(events: list[dict]) -> dict:
    return {"schema_version": "1.0", "events": events}


def _hints(rows: list[dict]) -> dict:
    return {"song_name": "x", "human_hints": rows}


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
        score = score_drops(timeline, [{"title": "Drop in", "start_time": 28.8}], {})
        self.assertEqual(score["mode"], "timed")
        self.assertEqual(score["metrics"]["true_positives"], 1)
        self.assertEqual(score["metrics"]["recall"], 1.0)
        self.assertEqual(score["metrics"]["precision"], 0.5)

    def test_presence_mode_uses_has_drop_fact(self) -> None:
        timeline = _timeline([{"type": "drop", "start_time": 12.0}])
        facts = {"has_drop": {"value": True}}
        score = score_drops(timeline, [], facts)
        self.assertEqual(score["mode"], "presence")
        self.assertTrue(score["presence_ok"])

        empty = score_drops(_timeline([]), [], facts)
        self.assertFalse(empty["presence_ok"])

    def test_fake_outnumbers_drop_flag(self) -> None:
        timeline = _timeline([
            {"type": "drop", "start_time": 10.0},
            {"type": "fake_drop", "start_time": 20.0},
            {"type": "fake_drop", "start_time": 30.0},
        ])
        score = score_drops(timeline, [], {})
        self.assertTrue(score["fake_outnumbers_drop"])


class FormScoringTests(unittest.TestCase):
    def test_labelled_boundaries_from_form_role_hints(self) -> None:
        rows = [
            {"start_time": 15.0, "form_role": "verse"},
            {"start_time": 30.0, "form_role": "chorus"},
            {"start_time": 5.0, "title": "not a boundary"},
        ]
        self.assertEqual(
            labelled_boundaries(rows),
            [{"time": 15.0, "form_role": "verse"}, {"time": 30.0, "form_role": "chorus"}],
        )

    def test_score_form_boundary_and_role_accuracy(self) -> None:
        sections = {
            "form_family": "dance_form",
            "sections": [
                {"start": 0.0, "form_role": "intro", "confidence": 0.9},
                {"start": 14.5, "form_role": "verse", "confidence": 0.7},
                {"start": 29.0, "form_role": "drop", "confidence": 0.8},
            ],
        }
        hints = _hints([
            {"start_time": 15.0, "form_role": "verse"},
            {"start_time": 30.0, "form_role": "chorus"},
        ])["human_hints"]
        facts = {"form_family": {"value": "dance_form"}}
        score = score_form(sections, hints, facts)
        self.assertTrue(score["form_family_match"])
        self.assertEqual(score["boundary_metrics"]["true_positives"], 2)
        self.assertEqual(score["form_role"]["correct"], 1)  # verse right, chorus vs drop wrong

    def test_confidence_calibration_spread(self) -> None:
        rows = [
            {"start": 0.0, "confidence": 0.1},
            {"start": 10.0, "confidence": 0.2},
            {"start": 20.0, "confidence": 0.9},
        ]
        cal = confidence_calibration(rows, [])
        self.assertAlmostEqual(cal["predicted_spread"], 0.7)
        self.assertEqual(sum(b["section_count"] for b in cal["buckets"]), 2)


class ValidateAdapterTests(unittest.TestCase):
    def test_validate_skips_without_labels_and_scores_with_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            out = paths.song_output_dir
            (out).mkdir(parents=True)
            (paths.artifact("section_segmentation")).mkdir(parents=True)
            paths.artifact("section_segmentation", "sections.json").write_text(json.dumps({
                "form_family": "dance_form",
                "sections": [
                    {"start": 0.0, "form_role": "intro", "confidence": 0.8},
                    {"start": 28.0, "form_role": "drop", "confidence": 0.7},
                ],
            }))
            paths.timeline_output_path.write_text(json.dumps(_timeline([
                {"type": "drop", "start_time": 28.5, "confidence": 0.9},
            ])))

            # No reference/human -> skipped
            self.assertEqual(validate_form(paths).status, "skipped")
            self.assertEqual(validate_drops(paths).status, "skipped")

            human = paths.reference("human")
            human.mkdir(parents=True)
            (human / "song_facts.json").write_text(json.dumps({
                "facts": {"has_drop": {"value": True}, "form_family": {"value": "dance_form"}}
            }))
            drops_result = validate_drops(paths)
            self.assertEqual(drops_result.status, "passed")
            self.assertTrue(paths.artifact("validation", "drops_score.json").exists())

            form_result = validate_form(paths)
            self.assertEqual(form_result.status, "passed")


if __name__ == "__main__":
    unittest.main()
