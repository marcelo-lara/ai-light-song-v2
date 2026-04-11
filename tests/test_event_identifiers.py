from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.event_identifiers import infer_song_identifiers


class EventIdentifiersTests(unittest.TestCase):
    def test_infer_song_identifiers_emits_drop_from_rule_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            event_features = {
                "features": [
                    {
                        "beat": 1,
                        "start_time": 0.0,
                        "end_time": 1.0,
                        "derived": {"bass_activation_score": 0.1, "energy_delta": 0.0, "accent_intensity": 0.0},
                    },
                    {
                        "beat": 2,
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "derived": {"bass_activation_score": 0.72, "energy_delta": 0.34, "accent_intensity": 0.8},
                    },
                ]
            }
            energy_features = {
                "beat_features": [
                    {"beat": 1, "loudness_avg": 0.2, "onset_density": 0.1, "centroid_avg": 90.0},
                    {"beat": 2, "loudness_avg": 0.8, "onset_density": 0.5, "centroid_avg": 180.0},
                ]
            }
            energy_layer = {
                "beat_energy": [
                    {"beat": 1, "energy_score": 0.25},
                    {"beat": 2, "energy_score": 0.88},
                ]
            }
            rule_candidates = {
                "events": [
                    {
                        "id": "rule_drop_001",
                        "type": "drop",
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "section_id": "section-002",
                        "confidence": 0.86,
                        "evidence": {
                            "source_windows": [
                                {"layer": "event_features", "start_time": 1.0, "end_time": 2.0, "ref": "beats:2-2"}
                            ]
                        },
                    }
                ]
            }
            sections = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 1.0, "label": "build", "section_character": "build", "confidence": 0.8},
                    {"section_id": "section-002", "start": 1.0, "end": 3.0, "label": "peak_lift", "section_character": "peak_lift", "confidence": 0.9},
                ]
            }

            payload = infer_song_identifiers(paths, event_features, energy_features, energy_layer, rule_candidates, sections)

            self.assertEqual(payload["supported_identifiers"], ["drop"])
            self.assertEqual(len(payload["events"]), 1)
            event = payload["events"][0]
            self.assertEqual(event["identifier"], "drop")
            self.assertEqual(event["section_id"], "section-002")
            self.assertGreater(event["evidence"]["loudness_delta"], 0.0)
            self.assertTrue(paths.artifact("energy_summary", "hints.json").exists())


if __name__ == "__main__":
    unittest.main()