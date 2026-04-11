from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.event_features import build_event_feature_layer


class EventFeatureLayerTests(unittest.TestCase):
    def test_build_event_feature_layer_writes_aligned_features(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            timing = {
                "beats": [
                    {"index": 1, "time": 0.0, "bar": 1, "beat_in_bar": 1},
                    {"index": 2, "time": 1.0, "bar": 1, "beat_in_bar": 2},
                    {"index": 3, "time": 2.0, "bar": 1, "beat_in_bar": 3},
                    {"index": 4, "time": 3.0, "bar": 1, "beat_in_bar": 4},
                ],
                "bars": [
                    {"bar": 1, "start_s": 0.0, "end_s": 4.0},
                ],
            }
            harmonic = {
                "chords": [
                    {"time": 0.0, "end_s": 2.0, "bar": 1, "beat": 1, "chord": "Am", "confidence": 0.8},
                    {"time": 2.0, "end_s": 4.0, "bar": 1, "beat": 3, "chord": "F", "confidence": 0.6},
                ]
            }
            symbolic = {
                "note_events": [
                    {"time": 0.0, "end_s": 0.75, "source_stem": "vocals"},
                    {"time": 1.0, "end_s": 1.5, "source_stem": "bass"},
                    {"time": 2.0, "end_s": 2.75, "source_stem": "vocals"},
                ],
                "density_per_beat": [
                    {"beat": 1, "density": 2.0, "note_count": 1},
                    {"beat": 2, "density": 1.0, "note_count": 1},
                    {"beat": 3, "density": 0.0, "note_count": 0},
                    {"beat": 4, "density": 3.0, "note_count": 2},
                ],
                "phrase_windows": [
                    {"id": "phrase-001", "phrase_group_id": "group-001", "section_id": "section-001", "start_s": 0.0, "end_s": 2.0},
                    {"id": "phrase-002", "phrase_group_id": "group-002", "section_id": "section-001", "start_s": 2.0, "end_s": 4.0},
                ],
            }
            energy_features = {
                "beat_features": [
                    {"beat": 1, "time": 0.0, "loudness_avg": 0.2, "centroid_avg": 100.0, "flux_avg": 0.1, "onset_density": 0.15},
                    {"beat": 2, "time": 1.0, "loudness_avg": 0.5, "centroid_avg": 150.0, "flux_avg": 0.2, "onset_density": 0.3},
                    {"beat": 3, "time": 2.0, "loudness_avg": 0.4, "centroid_avg": 170.0, "flux_avg": 0.25, "onset_density": 0.25},
                    {"beat": 4, "time": 3.0, "loudness_avg": 0.9, "centroid_avg": 220.0, "flux_avg": 0.5, "onset_density": 0.6},
                ]
            }
            energy_layer = {
                "beat_energy": [
                    {"beat": 1, "time": 0.0, "energy_score": 0.2},
                    {"beat": 2, "time": 1.0, "energy_score": 0.45},
                    {"beat": 3, "time": 2.0, "energy_score": 0.4},
                    {"beat": 4, "time": 3.0, "energy_score": 0.9},
                ],
                "accent_candidates": [
                    {"id": "accent_001", "time": 3.0, "kind": "hit", "intensity": 0.8},
                ],
            }
            sections = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 4.0, "label": "steady_flow", "section_character": "steady_flow", "confidence": 0.9},
                ]
            }
            genre = {"genres": ["dance"], "top_predictions": [{"label": "dance", "confidence": 0.7}]}

            payload = build_event_feature_layer(
                paths,
                timing,
                harmonic,
                symbolic,
                energy_features,
                energy_layer,
                sections,
                genre,
            )

            self.assertEqual(len(payload["features"]), 4)
            self.assertEqual(payload["metadata"]["genres"], ["dance"])
            self.assertTrue(paths.artifact("event_inference", "features.json").exists())
            self.assertTrue(paths.artifact("event_inference", "timeline_index.json").exists())
            self.assertAlmostEqual(payload["features"][2]["derived"]["silence_gap_seconds"], 1.0)
            self.assertEqual(payload["features"][3]["source_refs"]["accent_id"], "accent_001")
            for row in payload["features"]:
                for value in row["normalized"].values():
                    self.assertGreaterEqual(float(value), 0.0)
                    self.assertLessEqual(float(value), 1.0)


if __name__ == "__main__":
    unittest.main()