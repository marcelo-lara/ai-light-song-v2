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
    paths.artifact("layer_b_symbolic.json").write_text(json.dumps({"note_events": []}))
    paths.artifact("symbolic_transcription", "basic_pitch").mkdir(parents=True, exist_ok=True)
    paths.artifact("symbolic_transcription", "basic_pitch", "bass.json").write_text(json.dumps({"notes": []}))
    paths.artifact("section_segmentation").mkdir(parents=True, exist_ok=True)
    paths.artifact("section_segmentation", "sections.json").write_text(json.dumps({"sections": sections}))
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    return paths


class SectionJoinTests(unittest.TestCase):
    def test_top_level_sections_carry_section_id_and_form_role(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "form_role": "intro",
             "energy_character": "ambient_opening", "section_character": "ambient_opening",
             "repetition_group": "A", "confidence": 0.9},
            {"section_id": "section-002", "start": 10.0, "end": 20.0, "form_role": "drop",
             "energy_character": "momentum_lift", "section_character": "momentum_lift",
             "repetition_group": "B", "confidence": 0.4},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            rows = json.loads(paths.sections_output_path.read_text())
        self.assertEqual([r["section_id"] for r in rows], ["section-001", "section-002"])
        self.assertEqual(rows[1]["form_role"], "drop")
        self.assertEqual(rows[0]["energy_character"], "ambient_opening")

    def test_missing_section_id_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, [{"start": 0.0, "end": 10.0, "form_role": "intro"}])
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
