from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.hints import generate_section_hints


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class SectionHintsTests(unittest.TestCase):
    def test_no_human_hints_file_produces_an_empty_flat_list(self) -> None:
        # v3.6 item 8 — no more inference-hint generation: with no
        # reference/human/human_hints.json, hints.json carries zero rows,
        # not a section-by-section inference scaffold.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            sections_payload = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro"},
                ]
            }
            generate_section_hints(paths, sections_payload)
            payload = json.loads(paths.hints_output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["hints"], [])
        self.assertNotIn("sections", payload)
        self.assertNotIn("generated_from", payload)
        self.assertEqual(payload["field_sources"]["text"], "human")

    def test_generate_section_hints_merges_human_hints_and_counts_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )

            sections_payload = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro"},
                    {"section_id": "section-002", "start": 10.0, "end": 100.0, "function": "verse"},
                ]
            }

            _write_json(
                paths.reference("human", "human_hints.json"),
                {
                    "song_name": "_test_song",
                    "human_hints": [
                        {
                            "id": "hint-006",
                            "title": "Breath",
                            "start_time": 81.395,
                            "end_time": 96.326,
                            "summary": "Vocal - no intense section",
                            "lighting_hint": "soft motion of moving heads.\nparcans slow violet waves",
                        }
                    ],
                },
            )

            merged_payload_paths = generate_section_hints(paths, sections_payload)
            self.assertIn("hints", merged_payload_paths)

            payload = json.loads(paths.hints_output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["hints"]), 1)

            hint = payload["hints"][0]
            self.assertEqual(hint["section_id"], "section-002")
            self.assertEqual(hint["text"], "Vocal - no intense section")
            self.assertEqual(hint["title"], "Breath")
            self.assertEqual(
                hint["lighting_hint"],
                "soft motion of moving heads.\nparcans slow violet waves",
            )
            self.assertNotIn("id", hint)
            self.assertNotIn("category", hint)
            self.assertNotIn("source", hint)
            self.assertNotIn("anchor_refs", hint)

    def test_lighting_hint_from_human_hints_reaches_hints_json(self) -> None:
        # Regression for the v3.6 bug: hints.json going stale against
        # reference/human/human_hints.json. A non-empty lighting_hint in the
        # human ground truth must appear in hints.json after this stage runs.
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )

            sections_payload = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 30.0, "function": "verse"},
                ]
            }

            expected_lighting_hint = "hard strobe hits on the snare, red wash"
            _write_json(
                paths.reference("human", "human_hints.json"),
                {
                    "song_name": "_test_song",
                    "human_hints": [
                        {
                            "id": "hint-001",
                            "title": "Drop",
                            "start_time": 5.0,
                            "end_time": 15.0,
                            "summary": "Drop hits hard",
                            "lighting_hint": expected_lighting_hint,
                        }
                    ],
                },
            )

            generate_section_hints(paths, sections_payload)

            payload = json.loads(paths.hints_output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["hints"][0]["lighting_hint"], expected_lighting_hint)

    def test_unmatched_hint_falls_back_to_unsectioned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            sections_payload = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro"},
                ]
            }
            _write_json(
                paths.reference("human", "human_hints.json"),
                {
                    "song_name": "_test_song",
                    "human_hints": [
                        {
                            "id": "hint-009",
                            "title": "Late note",
                            "start_time": 500.0,
                            "end_time": 510.0,
                            "summary": "Outside every section",
                        }
                    ],
                },
            )
            generate_section_hints(paths, sections_payload)
            payload = json.loads(paths.hints_output_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["hints"][0]["section_id"], "unsectioned")


if __name__ == "__main__":
    unittest.main()
