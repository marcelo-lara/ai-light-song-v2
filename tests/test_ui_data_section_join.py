from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.ui_data import build_ui_data


def _setup(tmp: str, sections: list[dict]) -> SongPaths:
    root = Path(tmp)
    paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
    paths.artifact("essentia").mkdir(parents=True)
    paths.artifact("essentia", "beats.json").write_text(json.dumps({"beats": [{"time": 0.0, "index": 1, "bar": 1, "beat_in_bar": 1, "type": "downbeat"}]}))
    paths.artifact("layer_a_harmonic.json").write_text(json.dumps({"chords": []}))
    paths.artifact("section_segmentation").mkdir(parents=True, exist_ok=True)
    paths.artifact("section_segmentation", "sections.json").write_text(json.dumps({"sections": sections}))
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    return paths


class SectionJoinTests(unittest.TestCase):
    def test_top_level_sections_carry_section_id_label_and_description(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro",
             "function_confidence": 0.9, "function_status": "known", "same_label_as": None,
             "confidence": 0.9},
            {"section_id": "section-002", "start": 10.0, "end": 20.0, "function": "chorus",
             "function_confidence": 0.4, "function_status": "known", "same_label_as": None,
             "confidence": 0.4},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            rows = json.loads(paths.sections_output_path.read_text())
        self.assertEqual([r["section_id"] for r in rows], ["section-001", "section-002"])
        self.assertEqual(rows[0]["label"], "001 Intro (0.90)")
        self.assertEqual(rows[1]["label"], "002 Chorus (0.40)")
        self.assertIn("intro", rows[0]["description"])
        self.assertNotIn("section_character", rows[0])
        self.assertNotIn("form_role", rows[0])

    def test_unknown_function_status_marks_label_unverified(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "verse",
             "function_confidence": 0.2, "function_status": "unknown", "same_label_as": None,
             "confidence": 0.5},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            rows = json.loads(paths.sections_output_path.read_text())
        self.assertIn("[unverified]", rows[0]["label"])
        self.assertIn("not trustworthy", rows[0]["description"])

    def test_missing_section_id_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, [{"start": 0.0, "end": 10.0, "function": "intro"}])
            with self.assertRaises(ValueError):
                build_ui_data(paths)

    def test_duplicate_section_id_fails_loudly(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0},
            {"section_id": "section-001", "start": 10.0, "end": 20.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            with self.assertRaises(ValueError):
                build_ui_data(paths)


if __name__ == "__main__":
    unittest.main()
