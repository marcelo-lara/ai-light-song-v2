from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import json

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

    def test_generate_machine_events_refines_no_drop_plateau_to_groove_loop(self) -> None:
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
                        "end_time": 4.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": 0.02, "accent_intensity": 0.33, "bass_activation_score": 0.74, "vocal_presence_score": 0.12},
                        "normalized": {"onset_density": 0.36, "energy_score": 0.62},
                        "rolling": {"medium": {"energy_mean": 0.61}, "short": {"harmonic_tension_mean": 0.2}},
                    },
                    {
                        "beat": 2,
                        "start_time": 4.0,
                        "end_time": 8.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": 0.01, "accent_intensity": 0.31, "bass_activation_score": 0.72, "vocal_presence_score": 0.15},
                        "normalized": {"onset_density": 0.34, "energy_score": 0.64},
                        "rolling": {"medium": {"energy_mean": 0.63}, "short": {"harmonic_tension_mean": 0.18}},
                    },
                ]
            }
            rule_candidates = {
                "events": [
                    {
                        "id": "rule_plateau_001",
                        "type": "no_drop_plateau",
                        "created_by": "analyzer_rule_engine",
                        "start_time": 0.0,
                        "end_time": 8.0,
                        "confidence": 0.55,
                        "section_id": "section-001",
                        "notes": "Plateau after withheld drop.",
                        "source_layers": ["event_features"],
                        "evidence": {
                            "summary": "Plateau baseline.",
                            "source_windows": [{"layer": "event_features", "start_time": 0.0, "end_time": 8.0, "ref": "beats:1-2", "metric_names": ["energy_score"]}],
                            "metrics": [],
                            "reasons": ["rule"],
                            "rule_names": ["plateau"],
                        },
                    }
                ]
            }
            identifier_payload = {"events": []}
            symbolic = {"phrase_windows": [], "motif_summary": {"repeated_phrase_groups": []}}
            sections = {"sections": [{"section_id": "section-001", "start": 0.0, "end": 8.0, "label": "groove_plateau", "section_character": "groove_plateau", "confidence": 0.9}]}

            payload = generate_machine_events(paths, event_features, rule_candidates, identifier_payload, symbolic, sections)

            self.assertEqual(payload["events"][0]["type"], "groove_loop")

    def test_generate_machine_events_adds_vocal_tail_and_percussion_break(self) -> None:
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
                        "derived": {"energy_delta": 0.0, "accent_intensity": 0.1, "bass_activation_score": 0.1, "vocal_presence_score": 0.7, "vocals_stem_score": 0.82, "drums_stem_score": 0.05, "harmonic_stem_score": 0.22, "bass_stem_score": 0.1, "vocal_focus_score": 0.78, "percussion_focus_score": 0.0, "instrumental_focus_score": 0.02, "vocal_stem_delta": 0.0},
                        "normalized": {"onset_density": 0.1, "energy_score": 0.32},
                        "rolling": {"medium": {"energy_mean": 0.32}, "short": {"harmonic_tension_mean": 0.2}},
                    },
                    {
                        "beat": 2,
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": -0.05, "accent_intensity": 0.08, "bass_activation_score": 0.12, "vocal_presence_score": 0.64, "vocals_stem_score": 0.74, "drums_stem_score": 0.06, "harmonic_stem_score": 0.28, "bass_stem_score": 0.12, "vocal_focus_score": 0.7, "percussion_focus_score": 0.0, "instrumental_focus_score": 0.05, "vocal_stem_delta": -0.08},
                        "normalized": {"onset_density": 0.12, "energy_score": 0.3},
                        "rolling": {"medium": {"energy_mean": 0.31}, "short": {"harmonic_tension_mean": 0.18}},
                    },
                    {
                        "beat": 3,
                        "start_time": 2.0,
                        "end_time": 3.0,
                        "section_id": "section-002",
                        "derived": {"energy_delta": 0.02, "accent_intensity": 0.18, "bass_activation_score": 0.2, "vocal_presence_score": 0.12, "vocals_stem_score": 0.18, "drums_stem_score": 0.82, "harmonic_stem_score": 0.16, "bass_stem_score": 0.22, "vocal_focus_score": 0.15, "percussion_focus_score": 0.64, "instrumental_focus_score": 0.02, "vocal_stem_delta": -0.56},
                        "normalized": {"onset_density": 0.54, "energy_score": 0.45},
                        "rolling": {"medium": {"energy_mean": 0.45}, "short": {"harmonic_tension_mean": 0.12}},
                    },
                    {
                        "beat": 4,
                        "start_time": 3.0,
                        "end_time": 4.0,
                        "section_id": "section-002",
                        "derived": {"energy_delta": 0.01, "accent_intensity": 0.16, "bass_activation_score": 0.18, "vocal_presence_score": 0.08, "vocals_stem_score": 0.12, "drums_stem_score": 0.78, "harmonic_stem_score": 0.18, "bass_stem_score": 0.24, "vocal_focus_score": 0.1, "percussion_focus_score": 0.6, "instrumental_focus_score": 0.06, "vocal_stem_delta": -0.06},
                        "normalized": {"onset_density": 0.5, "energy_score": 0.42},
                        "rolling": {"medium": {"energy_mean": 0.435}, "short": {"harmonic_tension_mean": 0.12}},
                    },
                ]
            }
            rule_candidates = {"events": []}
            identifier_payload = {"events": []}
            symbolic = {
                "phrase_windows": [
                    {"id": "phrase-001", "phrase_group_id": "group-001", "section_id": "section-001", "start_s": 0.0, "end_s": 2.0},
                ],
                "motif_summary": {"repeated_phrase_groups": []},
            }
            sections = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 2.0, "label": "vocal_spotlight", "section_character": "vocal_spotlight", "confidence": 0.9},
                    {"section_id": "section-002", "start": 2.0, "end": 4.0, "label": "percussion_break", "section_character": "percussion_break", "confidence": 0.9},
                ]
            }

            payload = generate_machine_events(paths, event_features, rule_candidates, identifier_payload, symbolic, sections)

            event_types = {event["type"] for event in payload["events"]}
            self.assertIn("vocal_spotlight", event_types)
            self.assertIn("vocal_tail", event_types)
            self.assertIn("percussion_break", event_types)

    def test_generate_machine_events_uses_lyrics_as_vocal_clue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            lyrics_path = root / "reference" / "Example Song" / "moises" / "lyrics.json"
            lyrics_path.parent.mkdir(parents=True, exist_ok=True)
            lyrics_path.write_text(
                json.dumps(
                    [
                        {"id": 1, "line_id": 1, "start": 10.0, "end": 10.0, "text": "<SOL>", "confidence": None},
                        {"id": 2, "line_id": 1, "start": 10.0, "end": 10.9, "text": "what", "confidence": "0.95"},
                        {"id": 3, "line_id": 1, "start": 10.9, "end": 12.0, "text": "feeling", "confidence": "0.93"},
                        {"id": 4, "line_id": 1, "start": 12.0, "end": 12.0, "text": "<EOL>", "confidence": None},
                    ]
                ),
                encoding="utf-8",
            )

            event_features = {
                "features": [
                    {
                        "beat": 10,
                        "start_time": 10.0,
                        "end_time": 11.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": 0.0, "accent_intensity": 0.1, "bass_activation_score": 0.15, "vocal_presence_score": 0.62, "vocals_stem_score": 0.72, "drums_stem_score": 0.12, "harmonic_stem_score": 0.25, "bass_stem_score": 0.18, "vocal_focus_score": 0.64, "percussion_focus_score": 0.01, "instrumental_focus_score": 0.09, "vocal_stem_delta": 0.0},
                        "normalized": {"onset_density": 0.14, "energy_score": 0.34},
                        "rolling": {"medium": {"energy_mean": 0.34}, "short": {"harmonic_tension_mean": 0.2}},
                    },
                    {
                        "beat": 11,
                        "start_time": 11.0,
                        "end_time": 12.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": -0.02, "accent_intensity": 0.09, "bass_activation_score": 0.13, "vocal_presence_score": 0.56, "vocals_stem_score": 0.66, "drums_stem_score": 0.14, "harmonic_stem_score": 0.28, "bass_stem_score": 0.16, "vocal_focus_score": 0.58, "percussion_focus_score": 0.01, "instrumental_focus_score": 0.1, "vocal_stem_delta": -0.06},
                        "normalized": {"onset_density": 0.13, "energy_score": 0.33},
                        "rolling": {"medium": {"energy_mean": 0.335}, "short": {"harmonic_tension_mean": 0.19}},
                    },
                    {
                        "beat": 12,
                        "start_time": 12.0,
                        "end_time": 13.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": -0.03, "accent_intensity": 0.08, "bass_activation_score": 0.14, "vocal_presence_score": 0.18, "vocals_stem_score": 0.22, "drums_stem_score": 0.2, "harmonic_stem_score": 0.34, "bass_stem_score": 0.2, "vocal_focus_score": 0.2, "percussion_focus_score": 0.02, "instrumental_focus_score": 0.16, "vocal_stem_delta": -0.44},
                        "normalized": {"onset_density": 0.16, "energy_score": 0.31},
                        "rolling": {"medium": {"energy_mean": 0.32}, "short": {"harmonic_tension_mean": 0.18}},
                    },
                    {
                        "beat": 13,
                        "start_time": 13.0,
                        "end_time": 14.0,
                        "section_id": "section-001",
                        "derived": {"energy_delta": 0.0, "accent_intensity": 0.08, "bass_activation_score": 0.14, "vocal_presence_score": 0.12, "vocals_stem_score": 0.14, "drums_stem_score": 0.18, "harmonic_stem_score": 0.32, "bass_stem_score": 0.2, "vocal_focus_score": 0.12, "percussion_focus_score": 0.03, "instrumental_focus_score": 0.18, "vocal_stem_delta": -0.08},
                        "normalized": {"onset_density": 0.18, "energy_score": 0.3},
                        "rolling": {"medium": {"energy_mean": 0.305}, "short": {"harmonic_tension_mean": 0.18}},
                    },
                ]
            }
            rule_candidates = {"events": []}
            identifier_payload = {"events": []}
            symbolic = {"phrase_windows": [], "motif_summary": {"repeated_phrase_groups": []}}
            sections = {
                "sections": [
                    {"section_id": "section-001", "start": 10.0, "end": 14.0, "label": "vocal_lift", "section_character": "vocal_lift", "confidence": 0.88},
                ]
            }

            payload = generate_machine_events(paths, event_features, rule_candidates, identifier_payload, symbolic, sections)

            event_types = {event["type"] for event in payload["events"]}
            self.assertIn("vocal_spotlight", event_types)
            self.assertIn("vocal_tail", event_types)
            lyric_guided = [event for event in payload["events"] if event["created_by"] == "analyzer_lyric_guided_classifier"]
            self.assertTrue(lyric_guided)


if __name__ == "__main__":
    unittest.main()