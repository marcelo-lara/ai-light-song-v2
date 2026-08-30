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
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
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
                        "rolling": {"local": {"energy_mean": 0.5, "harmonic_tension_mean": 0.52}},
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
                        "rolling": {"local": {"energy_mean": 0.7, "harmonic_tension_mean": 0.8}},
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
                        "rolling": {"local": {"energy_mean": 0.3, "harmonic_tension_mean": 0.6}},
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
                        "rolling": {"local": {"energy_mean": 0.58, "harmonic_tension_mean": 0.32}},
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
                        "rolling": {"local": {"energy_mean": 0.59, "harmonic_tension_mean": 0.3}},
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
            # self.assertIn("drop", event_types)
            # self.assertIn("pause_break", event_types)
            # self.assertIn("groove_loop", event_types)
            self.assertTrue(all(event["created_by"] == "analyzer_rule_engine" for event in payload["events"]))
            self.assertTrue(paths.artifact("event_inference", "rule_candidates.json").exists())


    def test_weighted_evidence_detects_bass_reentry_drop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )

            def beat(n, *, bass_rel, flux_rel=0.3, onset_rel=0.3, e_delta=0.0, accent=0.2, ratio=1.0):
                return {
                    "beat": n,
                    "start_time": float(n - 1),
                    "end_time": float(n),
                    "section_id": "section-001",
                    "section_name": "x",
                    "normalized": {"energy_score": 0.6, "onset_density": 0.4},
                    "derived": {
                        "energy_delta": e_delta,
                        "density_delta": 0.0,
                        "silence_gap_seconds": 0.0,
                        "bass_activation_score": bass_rel,
                        "harmonic_tension_proxy": 0.3,
                        "accent_intensity": accent,
                        "bass_stem_rel": bass_rel,
                        "spectral_flux_rel": flux_rel,
                        "onset_density_rel": onset_rel,
                        "bass_att_ratio": ratio,
                    },
                    "rolling": {"local": {"energy_mean": 0.6, "harmonic_tension_mean": 0.3}},
                }

            # 8 beats of bass dropout, then a hard re-entry with an energy jump.
            rows = [beat(n, bass_rel=0.05, flux_rel=0.1, onset_rel=0.1) for n in range(1, 9)]
            rows.append(beat(9, bass_rel=0.95, flux_rel=0.9, onset_rel=0.9, e_delta=1.6, accent=0.9, ratio=2.2))
            rows.append(beat(10, bass_rel=0.9, flux_rel=0.8, onset_rel=0.8, e_delta=0.2, accent=0.6, ratio=1.4))

            sections = {"sections": [{"section_id": "section-001", "start": 0.0, "end": 10.0, "label": "x", "section_character": "x", "confidence": 0.8}]}
            payload = generate_rule_candidates(paths, {"features": rows}, sections, {"genres": ["dance"]})

            drops = [e for e in payload["events"] if e["type"] == "drop"]
            self.assertEqual(len(drops), 1)
            self.assertAlmostEqual(drops[0]["start_time"], 8.0)
            meta = drops[0]["evidence"]["metadata"]["drop_evidence"]
            self.assertEqual(meta["profile"], "stem_relative_weighted_v1")
            self.assertGreaterEqual(meta["score"], meta["decision_threshold"])
            names = {c["name"] for c in meta["contributions"]}
            self.assertIn("bass_reentry", names)

    def test_no_drop_without_bass_reentry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
            rows = [
                {
                    "beat": n, "start_time": float(n - 1), "end_time": float(n),
                    "section_id": "section-001", "section_name": "x",
                    "normalized": {"energy_score": 0.5, "onset_density": 0.4},
                    "derived": {
                        "energy_delta": 0.05, "density_delta": 0.0, "silence_gap_seconds": 0.0,
                        "bass_activation_score": 0.5, "harmonic_tension_proxy": 0.3,
                        "accent_intensity": 0.2, "bass_stem_rel": 0.5,
                        "spectral_flux_rel": 0.4, "onset_density_rel": 0.4, "bass_att_ratio": 1.0,
                    },
                    "rolling": {"local": {"energy_mean": 0.5, "harmonic_tension_mean": 0.3}},
                }
                for n in range(1, 11)
            ]
            sections = {"sections": [{"section_id": "section-001", "start": 0.0, "end": 10.0, "label": "x", "section_character": "x", "confidence": 0.8}]}
            payload = generate_rule_candidates(paths, {"features": rows}, sections, {"genres": ["dance"]})
            self.assertEqual([e for e in payload["events"] if e["type"] == "drop"], [])


if __name__ == "__main__":
    unittest.main()