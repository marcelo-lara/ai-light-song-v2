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
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            symbolic = {
                "section_summaries": [
                    {
                        "section_id": "section-001",
                        "texture": "layered",
                        "melodic_contour": "falling",
                        "density_mean": 6.0,
                        "sustain_ratio": 0.03,
                        "repetition_score": 0.05,
                    },
                    {
                        "section_id": "section-002",
                        "texture": "layered",
                        "melodic_contour": "rising",
                        "density_mean": 11.0,
                        "sustain_ratio": 0.05,
                        "repetition_score": 0.3,
                    },
                ],
                "phrase_windows": [
                    {
                        "id": "phrase_group_A_1",
                        "phrase_group_id": "phrase_group_A",
                        "section_id": "section-002",
                    }
                ],
                "motif_summary": {
                    "repeated_phrase_groups": [],
                    "motif_groups": [],
                },
            }
            sections_payload = {
                "sections": [
                    {
                        "section_id": "section-001",
                        "start": 0.0,
                        "end": 10.0,
                        "label": "contrast_bridge",
                        "section_character": "contrast_bridge",
                    },
                    {
                        "section_id": "section-002",
                        "start": 10.0,
                        "end": 20.0,
                        "label": "groove_plateau",
                        "section_character": "groove_plateau",
                    },
                ]
            }
            _write_json(
                paths.hints_output_path,
                {
                    "schema_version": "1.0",
                    "song_name": "Example Song",
                    "sections": [
                        {
                            "section_id": "section-002",
                            "label": "groove_plateau",
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

            generate_section_hints(paths, symbolic, sections_payload)

            merged_payload = json.loads(paths.hints_output_path.read_text(encoding="utf-8"))
            section_two = next(section for section in merged_payload["sections"] if section["section_id"] == "section-002")
            categories = [hint["category"] for hint in section_two["hints"] if hint["source"] == "inference"]
            self.assertIn("transition_role", categories)
            self.assertIn("section_shape", categories)
            self.assertEqual(section_two["hints"][0]["source"], "user")
            transition_hint = next(
                hint for hint in section_two["hints"] if hint["source"] == "inference" and hint["category"] == "transition_role"
            )
            self.assertIn("10.00s", transition_hint["text"])
            self.assertIn("groove plateau", transition_hint["text"])


if __name__ == "__main__":
    unittest.main()
