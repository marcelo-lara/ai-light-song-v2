from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.review_queue import build_review_queue


def _paths(tmp: str) -> SongPaths:
    root = Path(tmp)
    paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
    paths.artifact("validation").mkdir(parents=True)
    return paths


class ReviewQueueTests(unittest.TestCase):
    def test_low_confidence_form_family_becomes_top_question(self) -> None:
        sections_payload = {
            "form_family": {"value": "unknown", "confidence": 0.3, "provenance": "inferred",
                            "evidence": {"dance_score": 0.5, "song_score": 0.45}},
            "sections": [{"section_id": "section-001", "start": 0.0, "form_role": "intro", "form_role_margin": 0.4}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(tmp)
            queue = build_review_queue(paths, sections_payload, {"genres": ["dance"], "confidence": 0.3}, {"events": []})
            self.assertGreaterEqual(queue["open_question_count"], 1)
            self.assertEqual(queue["questions"][0]["field"], "form_family")
            self.assertTrue(paths.artifact("validation", "review_queue.json").exists())

    def test_form_family_genre_disagreement_flagged(self) -> None:
        sections_payload = {
            "form_family": {"value": "dance_form", "confidence": 0.8, "provenance": "inferred", "evidence": {}},
            "sections": [{"section_id": "section-001", "start": 0.0, "form_role": "intro", "form_role_margin": 0.4}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(tmp)
            queue = build_review_queue(paths, sections_payload, {"genres": ["ambient", "classical"], "confidence": 0.2}, {"events": []})
        fields = {q["field"] for q in queue["questions"]}
        self.assertIn("form_family_vs_genre", fields)

    def test_missing_drop_question_when_fact_says_has_drop(self) -> None:
        sections_payload = {
            "form_family": {"value": "dance_form", "confidence": 0.9, "provenance": "inferred", "evidence": {}},
            "sections": [{"section_id": "section-001", "start": 0.0, "form_role": "intro", "form_role_margin": 0.4}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(tmp)
            paths.reference("human").mkdir(parents=True)
            (paths.reference("human", "song_facts.json")).write_text(json.dumps({"facts": {"has_drop": {"value": True}}}))
            queue = build_review_queue(paths, sections_payload, {"genres": ["dance"]}, {"events": []})
        self.assertIn("drops.timed_location", {q["field"] for q in queue["questions"]})

    def test_analyzer_never_writes_reference(self) -> None:
        sections_payload = {
            "form_family": {"value": "unknown", "confidence": 0.2, "provenance": "inferred", "evidence": {}},
            "sections": [{"section_id": "section-001", "start": 0.0, "form_role": "unknown", "form_role_margin": 0.01}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            paths = _paths(tmp)
            reference_dir = paths.reference("human")
            reference_dir.mkdir(parents=True)
            before = sorted(p.name for p in reference_dir.iterdir())
            build_review_queue(paths, sections_payload, {"genres": ["dance"]}, {"events": []})
            after = sorted(p.name for p in reference_dir.iterdir())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
