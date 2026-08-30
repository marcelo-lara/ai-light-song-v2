from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyzer.paths import SongPaths
from analyzer.stages.event_benchmark import _load_threshold_profiles, _select_profile, benchmark_event_outputs


class SelectProfileTests(unittest.TestCase):
    def _paths(self, tmp):
        root = Path(tmp)
        return SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")

    def test_form_family_selects_profile_not_genre(self) -> None:
        profiles = _load_threshold_profiles()
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            paths.artifact("section_segmentation").mkdir(parents=True)
            paths.artifact("section_segmentation", "sections.json").write_text(
                json.dumps({"form_family": {"value": "dance_form"}, "sections": []})
            )
            name, basis = _select_profile(paths, profiles)
        self.assertEqual(name, "festival_edm")
        self.assertEqual(basis, "form_family:dance_form")

    def test_human_confirmed_genre_wins(self) -> None:
        profiles = _load_threshold_profiles()
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(tmp)
            paths.artifact("section_segmentation").mkdir(parents=True)
            paths.artifact("section_segmentation", "sections.json").write_text(
                json.dumps({"form_family": {"value": "dance_form"}, "sections": []})
            )
            paths.reference("human").mkdir(parents=True)
            paths.reference("human", "song_facts.json").write_text(
                json.dumps({"facts": {"genre": {"value": "alt_rock"}}})
            )
            name, basis = _select_profile(paths, profiles)
        self.assertEqual(name, "alt_rock")
        self.assertEqual(basis, "human_confirmed_genre")

    def test_default_when_nothing_available(self) -> None:
        profiles = _load_threshold_profiles()
        with tempfile.TemporaryDirectory() as tmp:
            name, basis = _select_profile(self._paths(tmp), profiles)
        self.assertEqual(name, profiles["default_profile"])
        self.assertEqual(basis, "default")


class EventBenchmarkTests(unittest.TestCase):
    def test_benchmark_event_outputs_matches_reviewed_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            annotation_dir = root / "benchmark_annotations"
            annotation_dir.mkdir(parents=True, exist_ok=True)
            annotation_file = annotation_dir / "_test_song.json"
            annotation_file.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "song_name": "_test_song",
                        "annotation_status": "reviewed",
                        "events": [
                            {"type": "drop_punch", "start_time": 1.0, "end_time": 2.0}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            merged_payload = {
                "events": [
                    {"id": "evt_001", "type": "drop_punch", "start_time": 1.1, "end_time": 2.0}
                ]
            }
            with patch("analyzer.stages.event_benchmark._annotation_path", return_value=annotation_file):
                report = benchmark_event_outputs(paths, merged_payload, {"genres": ["festival_edm"]})
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["matched"], 1)


if __name__ == "__main__":
    unittest.main()