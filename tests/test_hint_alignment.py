from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.hint_alignment import build_human_hints_alignment


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class HumanHintsAlignmentTests(unittest.TestCase):
    def test_build_human_hints_alignment_writes_overlap_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            _write_json(
                paths.reference("human", "human_hints.json"),
                {
                    "song_name": "Example Song",
                    "human_hints": [
                        {
                            "id": "ui_001",
                            "start_time": 10.0,
                            "end_time": 14.0,
                            "title": "Vocal rise",
                            "summary": "Lead vocal rises over a repeating figure.",
                            "lighting_hint": "",
                        }
                    ],
                },
            )
            _write_json(
                paths.sections_output_path,
                [
                    {"start": 8.0, "end": 12.0, "label": "Ambient Opening"},
                    {"start": 12.0, "end": 16.0, "label": "Peak Lift"},
                ],
            )
            _write_json(
                paths.timeline_output_path,
                {
                    "events": [
                        {
                            "id": "event-001",
                            "type": "build",
                            "start_time": 10.0,
                            "end_time": 11.0,
                            "section_name": "Ambient Opening",
                        },
                        {
                            "id": "event-002",
                            "type": "impact_hit",
                            "start_time": 13.0,
                            "end_time": 13.5,
                            "section_name": "Peak Lift",
                        },
                    ]
                },
            )
            _write_json(
                paths.artifact("layer_d_patterns.json"),
                {
                    "patterns": [
                        {
                            "id": "pattern_A",
                            "label": "A",
                            "sequence": "C#|D#",
                            "occurrences": [
                                {"start_s": 9.5, "end_s": 13.5, "sequence": "C#|D#", "mismatch_count": 0}
                            ],
                        }
                    ]
                },
            )
            _write_json(
                paths.artifact("layer_a_harmonic.json"),
                {
                    "chords": [
                        {"time": 10.0, "end_s": 12.0, "chord": "C#", "confidence": 0.8},
                        {"time": 12.0, "end_s": 14.0, "chord": "D#", "confidence": 0.7},
                    ]
                },
            )

            result = build_human_hints_alignment(paths)

        self.assertIsNotNone(result)
        assert result is not None
        payload = result["payload"]
        self.assertEqual(payload["summary"]["hint_count"], 1)
        self.assertEqual(payload["summary"]["hints_with_section_overlap"], 1)
        self.assertEqual(payload["summary"]["hints_with_event_overlap"], 1)
        self.assertEqual(payload["summary"]["hints_with_pattern_overlap"], 1)
        self.assertEqual(payload["summary"]["hints_with_chord_overlap"], 1)
        alignment = payload["alignments"][0]
        self.assertEqual(alignment["primary_section_label"], "Ambient Opening")
        self.assertEqual(alignment["event_type_counts"], {"build": 1, "impact_hit": 1})


if __name__ == "__main__":
    unittest.main()