from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.event_machine import generate_machine_events


class EventMachineTests(unittest.TestCase):
    def test_generate_machine_events_refines_drop_and_adds_hook_phrase(self) -> None:
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
                        "section_id": "section-001",
                        "derived": {"energy_delta": 0.3, "accent_intensity": 0.9, "bass_activation_score": 0.7, "vocal_presence_score": 0.2},
                        "normalized": {"onset_density": 0.8},
                        "rolling": {"medium": {"energy_mean": 0.75}, "short": {"harmonic_tension_mean": 0.5}},
                    },
                    {
                        "beat": 2,
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": 0.0, "accent_intensity": 0.2, "bass_activation_score": 0.4, "vocal_presence_score": 0.6},
                        "normalized": {"onset_density": 0.5},
                        "rolling": {"medium": {"energy_mean": 0.6}, "short": {"harmonic_tension_mean": 0.3}},
                    },
                    {
                        "beat": 3,
                        "start_time": 2.0,
                        "end_time": 3.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": 0.0, "accent_intensity": 0.15, "bass_activation_score": 0.35, "vocal_presence_score": 0.58},
                        "normalized": {"onset_density": 0.45},
                        "rolling": {"medium": {"energy_mean": 0.55}, "short": {"harmonic_tension_mean": 0.28}},
                    },
                ]
            }
            rule_candidates = {
                "events": [
                    {
                        "id": "rule_drop_001",
                        "type": "drop",
                        "created_by": "analyzer_rule_engine",
                        "start_time": 0.0,
                        "end_time": 1.0,
                        "confidence": 0.8,
                        "section_id": "section-001",
                        "notes": "Baseline drop.",
                        "source_layers": ["event_features"],
                        "evidence": {
                            "summary": "Drop baseline.",
                            "source_windows": [{"layer": "event_features", "start_time": 0.0, "end_time": 1.0, "ref": "beats:1-1", "metric_names": ["energy_score"]}],
                            "metrics": [],
                            "reasons": ["rule"],
                            "rule_names": ["drop"],
                        },
                    }
                ]
            }
            identifier_payload = {
                "events": [
                    {
                        "source_event_id": "rule_drop_001",
                        "evidence": {"spectral_centroid_delta": 220.0},
                    }
                ]
            }
            symbolic = {
                "phrase_windows": [
                    {"id": "phrase-001", "phrase_group_id": "group-001", "section_id": "section-001", "start_s": 1.0, "end_s": 3.0},
                    {"id": "phrase-002", "phrase_group_id": "group-002", "section_id": "section-001", "start_s": 3.0, "end_s": 4.0},
                ],
                "motif_summary": {"repeated_phrase_groups": [{"id": "group-001", "phrase_window_ids": ["phrase-001", "phrase-003"]}]},
            }
            sections = {"sections": [{"section_id": "section-001", "start": 0.0, "end": 4.0, "label": "peak_lift", "section_character": "peak_lift", "confidence": 0.9}]}

            payload = generate_machine_events(paths, event_features, rule_candidates, identifier_payload, symbolic, sections)

            event_types = [event["type"] for event in payload["events"]]
            self.assertIn("drop_explode", event_types)
            self.assertIn("hook_phrase", event_types)
            created_by_by_type = {event["type"]: event["created_by"] for event in payload["events"]}
            self.assertEqual(created_by_by_type["drop_explode"], "analyzer_event_classifier")
            self.assertEqual(created_by_by_type["hook_phrase"], "analyzer_phrase_classifier")
            self.assertTrue(paths.artifact("event_inference", "events.machine.json").exists())


if __name__ == "__main__":
    unittest.main()