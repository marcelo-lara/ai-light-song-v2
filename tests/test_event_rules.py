from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.event_rules import generate_rule_candidates


class EventRuleCandidatesTests(unittest.TestCase):
    def test_generate_rule_candidates_emits_expected_baseline_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            features = {
                "features": [
                    {
                        "beat": 1,
                        "start_time": 0.0,
                        "end_time": 1.0,
                        "section_id": "section-001",
                        "section_name": "tense_transition",
                        "normalized": {"energy_score": 0.5, "onset_density": 0.45},
                        "derived": {
                            "energy_delta": 0.1,
                            "density_delta": 0.02,
                            "silence_gap_seconds": 0.0,
                            "vocal_presence_score": 0.1,
                            "bass_activation_score": 0.2,
                            "harmonic_tension_proxy": 0.5,
                            "accent_intensity": 0.1,
                        },
                        "rolling": {"short": {"energy_mean": 0.5, "harmonic_tension_mean": 0.52}},
                    },
                    {
                        "beat": 2,
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "section_id": "section-001",
                        "section_name": "tense_transition",
                        "normalized": {"energy_score": 0.92, "onset_density": 0.82},
                        "derived": {
                            "energy_delta": 0.35,
                            "density_delta": 0.1,
                            "silence_gap_seconds": 0.0,
                            "vocal_presence_score": 0.0,
                            "bass_activation_score": 0.7,
                            "harmonic_tension_proxy": 0.45,
                            "accent_intensity": 0.9,
                        },
                        "rolling": {"short": {"energy_mean": 0.7, "harmonic_tension_mean": 0.5}},
                    },
                    {
                        "beat": 3,
                        "start_time": 2.0,
                        "end_time": 3.0,
                        "section_id": "section-002",
                        "section_name": "steady_flow",
                        "normalized": {"energy_score": 0.2, "onset_density": 0.1},
                        "derived": {
                            "energy_delta": -0.4,
                            "density_delta": -0.3,
                            "silence_gap_seconds": 1.0,
                            "vocal_presence_score": 0.0,
                            "bass_activation_score": 0.0,
                            "harmonic_tension_proxy": 0.6,
                            "accent_intensity": 0.0,
                        },
                        "rolling": {"short": {"energy_mean": 0.3, "harmonic_tension_mean": 0.6}},
                    },
                    {
                        "beat": 4,
                        "start_time": 3.0,
                        "end_time": 4.0,
                        "section_id": "section-003",
                        "section_name": "driving_pulse",
                        "normalized": {"energy_score": 0.58, "onset_density": 0.4},
                        "derived": {
                            "energy_delta": 0.02,
                            "density_delta": 0.0,
                            "silence_gap_seconds": 0.0,
                            "vocal_presence_score": 0.0,
                            "bass_activation_score": 0.58,
                            "harmonic_tension_proxy": 0.3,
                            "accent_intensity": 0.1,
                        },
                        "rolling": {"short": {"energy_mean": 0.58, "harmonic_tension_mean": 0.32}},
                    },
                    {
                        "beat": 5,
                        "start_time": 4.0,
                        "end_time": 5.0,
                        "section_id": "section-003",
                        "section_name": "driving_pulse",
                        "normalized": {"energy_score": 0.6, "onset_density": 0.42},
                        "derived": {
                            "energy_delta": 0.01,
                            "density_delta": 0.0,
                            "silence_gap_seconds": 0.0,
                            "vocal_presence_score": 0.0,
                            "bass_activation_score": 0.62,
                            "harmonic_tension_proxy": 0.28,
                            "accent_intensity": 0.1,
                        },
                        "rolling": {"short": {"energy_mean": 0.59, "harmonic_tension_mean": 0.3}},
                    },
                ]
            }
            sections = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 2.0, "label": "tense_transition", "section_character": "tense_transition", "confidence": 0.8},
                    {"section_id": "section-002", "start": 2.0, "end": 3.0, "label": "steady_flow", "section_character": "steady_flow", "confidence": 0.85},
                    {"section_id": "section-003", "start": 3.0, "end": 5.0, "label": "driving_pulse", "section_character": "driving_pulse", "confidence": 0.9},
                ]
            }

            payload = generate_rule_candidates(paths, features, sections, {"genres": ["dance"]})

            event_types = [event["type"] for event in payload["events"]]
            self.assertIn("build", event_types)
            self.assertIn("drop", event_types)
            self.assertIn("pause_break", event_types)
            self.assertIn("groove_loop", event_types)
            self.assertTrue(all(event["created_by"] == "analyzer_rule_engine" for event in payload["events"]))
            self.assertTrue(paths.artifact("event_inference", "rule_candidates.json").exists())


if __name__ == "__main__":
    unittest.main()