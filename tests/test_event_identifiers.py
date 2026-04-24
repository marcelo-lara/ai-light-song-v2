from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.event_identifiers import infer_song_identifiers

class EventIdentifiersTests(unittest.TestCase):
    def test_infer_song_identifiers_emits_drop_from_energy_layer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            energy_layer = {
                "beat_energy": [
                    {
                        "beat": 1, 
                        "time": 0.0, 
                        "loudness_avg": 0.2, 
                        "onset_density": 0.1, 
                        "centroid_avg": 90.0,
                        "energy_score": 0.1,
                        "section_id": "section-001"
                    },
                    {
                        "beat": 2, 
                        "time": 1.0, 
                        "loudness_avg": 0.8, 
                        "onset_density": 0.5, 
                        "centroid_avg": 300.0,
                        "energy_score": 0.6,
                        "section_id": "section-002"
                    },
                ]
            }

            sections = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 1.0, "label": "build", "section_character": "build", "confidence": 0.8},
                    {"section_id": "section-002", "start": 1.0, "end": 3.0, "label": "peak_lift", "section_character": "peak_lift", "confidence": 0.9},
                ]
            }

            payload = infer_song_identifiers(paths, energy_layer, sections)

            self.assertEqual(payload["supported_identifiers"], ["drop"])
            self.assertEqual(len(payload["events"]), 1)
            event = payload["events"][0]
            self.assertEqual(event["identifier"], "drop")
            self.assertEqual(event["section_id"], "section-002")
            self.assertGreater(event["evidence"]["loudness_delta"], 0.0)
            self.assertIn("audit", event)
            self.assertIn("alignment_score", event["audit"])
            self.assertIn("mismatch_flag", event["audit"])
            self.assertTrue(paths.artifact("energy_summary", "hints.json").exists())

if __name__ == "__main__":
    unittest.main()
