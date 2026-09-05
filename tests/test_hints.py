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
    def test_generate_section_hints_adds_transition_role_and_preserves_user_hints(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )

            sections_payload = {
                "sections": [
                    {
                        "section_id": "section-001",
                        "start": 0.0,
                        "end": 10.0,
                        "function": "intro",
                    },
                    {
                        "section_id": "section-002",
                        "start": 10.0,
                        "end": 20.0,
                        "function": "chorus",
                    },
                ]
            }
            _write_json(
                paths.hints_output_path,
                {
                    "schema_version": "1.0",
                    "song_name": "_test_song",
                    "sections": [
                        {
                            "section_id": "section-002",
                            "label": "chorus",
                            "start": 10.0,
                            "end": 20.0,
                            "hints": [
                                {
                                    "id": "section-002-user-01",
                                    "source": "user",
                                    "category": "note",
                                    "text": "Keep the reset sharp on the boundary.",
                                    "anchor_refs": {
                                        "phrase_window_ids": [],
                                        "phrase_group_ids": [],
                                        "motif_group_ids": [],
                                    },
                                }
                            ],
                        }
                    ],
                },
            )

            generate_section_hints(paths, sections_payload)

            merged_payload = json.loads(paths.hints_output_path.read_text(encoding="utf-8"))
            section_two = next(section for section in merged_payload["sections"] if section["section_id"] == "section-002")
            categories = [hint["category"] for hint in section_two["hints"] if hint["source"] == "inference"]
            self.assertIn("transition_role", categories)
            self.assertEqual(section_two["hints"][0]["source"], "user")
            transition_hint = next(
                hint for hint in section_two["hints"] if hint["source"] == "inference" and hint["category"] == "transition_role"
            )
            self.assertIn("10.00s", transition_hint["text"])
            self.assertIn("chorus", transition_hint["text"])


if __name__ == "__main__":
    unittest.main()
