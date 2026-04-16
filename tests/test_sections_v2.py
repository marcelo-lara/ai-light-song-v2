from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from analyzer.paths import SongPaths
from analyzer.stages.sections_v2 import _group_phrase_blocks, _refine_boundary_to_local_novelty, _section_character_labels, segment_sections


def _beat_row(time_s: float, energy: float, onset: float, flux: float, root_index: int) -> dict[str, object]:
    chord_histogram = np.zeros(12, dtype=float)
    chord_histogram[root_index] = 1.0
    return {
        "time": time_s,
        "energy": energy,
        "onset": onset,
        "flux": flux,
        "vector": np.concatenate([np.array([energy, onset, flux], dtype=float), chord_histogram]),
    }


class SectionSegmentationTests(unittest.TestCase):
    def test_boundary_refinement_can_move_one_beat_earlier(self) -> None:
        beat_rows = [
            _beat_row(0.5, 0.1, 0.1, 0.1, 0),
            _beat_row(1.0, 0.1, 0.1, 0.1, 0),
            _beat_row(1.5, 0.1, 0.1, 0.1, 0),
            _beat_row(2.0, 0.1, 0.1, 0.1, 0),
            _beat_row(2.5, 0.1, 0.1, 0.1, 0),
            _beat_row(3.0, 0.1, 0.1, 0.1, 0),
            _beat_row(3.5, 0.85, 0.8, 0.8, 7),
            _beat_row(4.0, 0.85, 0.8, 0.8, 7),
            _beat_row(4.5, 0.85, 0.8, 0.8, 7),
            _beat_row(5.0, 0.85, 0.8, 0.8, 7),
            _beat_row(5.5, 0.85, 0.8, 0.8, 7),
            _beat_row(6.0, 0.85, 0.8, 0.8, 7),
        ]

        refined_time = _refine_boundary_to_local_novelty(4.0, beat_rows)

        self.assertEqual(refined_time, 3.5)

    def test_boundary_refinement_keeps_coarse_time_when_local_region_is_uniform(self) -> None:
        beat_rows = [_beat_row(0.5 + (index * 0.5), 0.3, 0.2, 0.2, 0) for index in range(12)]

        refined_time = _refine_boundary_to_local_novelty(4.0, beat_rows)

        self.assertEqual(refined_time, 4.0)

    def test_group_phrase_blocks_preserves_strong_intro_boundary(self) -> None:
        first_vector = np.array([0.35, 0.35, 0.27] + [1.0] + [0.0] * 11, dtype=float)
        second_vector = np.array([0.346, 0.349, 0.281] + [0.0] * 7 + [1.0] + [0.0] * 4, dtype=float)
        first_vector = first_vector / np.linalg.norm(first_vector)
        second_vector = second_vector / np.linalg.norm(second_vector)
        blocks = [
            {
                "bar_start": 1,
                "bar_end": 8,
                "start_s": 0.5,
                "end_s": 16.0,
                "bar_count": 8,
                "energy": 0.35,
                "onset": 0.345,
                "flux": 0.27,
                "vector": first_vector,
            },
            {
                "bar_start": 9,
                "bar_end": 16,
                "start_s": 16.0,
                "end_s": 31.5,
                "bar_count": 8,
                "energy": 0.346,
                "onset": 0.349,
                "flux": 0.281,
                "vector": second_vector,
            },
            {
                "bar_start": 17,
                "bar_end": 24,
                "start_s": 31.5,
                "end_s": 47.0,
                "bar_count": 8,
                "energy": 0.39,
                "onset": 0.38,
                "flux": 0.31,
                "vector": second_vector,
            },
        ]
        beat_rows = [
            _beat_row(13.5, 0.12, 0.10, 0.09, 0),
            _beat_row(14.0, 0.12, 0.10, 0.09, 0),
            _beat_row(14.5, 0.12, 0.10, 0.09, 0),
            _beat_row(15.0, 0.12, 0.10, 0.09, 0),
            _beat_row(15.5, 0.11, 0.09, 0.08, 0),
            _beat_row(16.0, 0.62, 0.64, 0.63, 7),
            _beat_row(16.5, 0.65, 0.66, 0.64, 7),
            _beat_row(17.0, 0.65, 0.66, 0.64, 7),
            _beat_row(17.5, 0.65, 0.66, 0.64, 7),
        ]

        groups = _group_phrase_blocks(blocks, beat_rows)

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0][0]["bar_start"], 1)
        self.assertEqual(groups[0][0]["bar_end"], 8)
        self.assertEqual(groups[1][0]["bar_start"], 9)

    def test_section_character_labels_marks_low_energy_near_threshold_as_breath_space(self) -> None:
        sections = [
            {"energy": 0.35, "onset": 0.34, "flux": 0.33, "vector": np.array([1.0, 0.0, 0.0])},
            {"energy": 0.34, "onset": 0.30, "flux": 0.28, "vector": np.array([0.9, 0.1, 0.0])},
            {"energy": 0.41, "onset": 0.31, "flux": 0.30, "vector": np.array([0.2, 0.8, 0.0])},
            {"energy": 0.49, "onset": 0.42, "flux": 0.37, "vector": np.array([0.0, 1.0, 0.0])},
            {"energy": 0.32, "onset": 0.26, "flux": 0.24, "vector": np.array([0.0, 0.2, 0.8])},
            {"energy": 0.56, "onset": 0.43, "flux": 0.42, "vector": np.array([0.0, 0.0, 1.0])},
            {"energy": 0.33, "onset": 0.27, "flux": 0.25, "vector": np.array([0.4, 0.4, 0.2])},
        ]

        labels = _section_character_labels(sections)

        self.assertEqual(labels[1], "breath_space")

    def test_segment_sections_refines_boundary_before_next_bar(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            beats = []
            bars = []
            beat_features = []
            beat_time = 0.5
            for bar_number in range(1, 17):
                bar_start = beat_time
                for beat_in_bar in range(1, 5):
                    beats.append(
                        {
                            "index": len(beats) + 1,
                            "time": beat_time,
                            "bar": bar_number,
                            "beat_in_bar": beat_in_bar,
                            "type": "downbeat" if beat_in_bar == 1 else "beat",
                        }
                    )
                    is_changed_region = beat_time >= 16.0
                    beat_features.append(
                        {
                            "beat": len(beat_features) + 1,
                            "time": beat_time,
                            "loudness_avg": 0.9 if is_changed_region else 0.15,
                            "onset_density": 0.85 if is_changed_region else 0.1,
                            "flux_avg": 0.8 if is_changed_region else 0.1,
                        }
                    )
                    beat_time += 0.5
                bars.append({"bar": bar_number, "start_s": bar_start, "end_s": beat_time})

            timing = {"beats": beats, "bars": bars}
            harmonic = {
                "chords": [
                    {"time": 0.5, "end_s": 16.0, "bar": 1, "beat": 1, "chord": "C", "confidence": 1.0},
                    {"time": 16.0, "end_s": beat_time, "bar": 8, "beat": 4, "chord": "G", "confidence": 1.0},
                ]
            }
            energy = {"beat_features": beat_features}

            payload = segment_sections(paths, timing, harmonic, energy)

            self.assertEqual(len(payload["sections"]), 2)
            self.assertEqual(payload["sections"][1]["start"], 16.0)
            self.assertEqual(payload["sections"][0]["end"], 16.0)
            self.assertTrue(paths.artifact("section_segmentation", "sections.json").exists())

    def test_segment_sections_keeps_bar_boundary_with_reference_timing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            beats = []
            bars = []
            beat_features = []
            beat_time = 0.5
            for bar_number in range(1, 17):
                bar_start = beat_time
                for beat_in_bar in range(1, 5):
                    beats.append(
                        {
                            "index": len(beats) + 1,
                            "time": beat_time,
                            "bar": bar_number,
                            "beat_in_bar": beat_in_bar,
                            "type": "downbeat" if beat_in_bar == 1 else "beat",
                        }
                    )
                    is_changed_region = beat_time >= 16.0
                    beat_features.append(
                        {
                            "beat": len(beat_features) + 1,
                            "time": beat_time,
                            "loudness_avg": 0.9 if is_changed_region else 0.15,
                            "onset_density": 0.85 if is_changed_region else 0.1,
                            "flux_avg": 0.8 if is_changed_region else 0.1,
                        }
                    )
                    beat_time += 0.5
                bars.append({"bar": bar_number, "start_s": bar_start, "end_s": beat_time})

            timing = {
                "beats": beats,
                "bars": bars,
                "generated_from": {
                    "engine": "reference.moises.chords",
                    "dependencies": {"reference_chords": "/tmp/reference.json"},
                },
            }
            harmonic = {
                "chords": [
                    {"time": 0.5, "end_s": 16.0, "bar": 1, "beat": 1, "chord": "C", "confidence": 1.0},
                    {"time": 16.0, "end_s": beat_time, "bar": 8, "beat": 4, "chord": "G", "confidence": 1.0},
                ]
            }
            energy = {"beat_features": beat_features}

            payload = segment_sections(paths, timing, harmonic, energy)

            self.assertEqual(len(payload["sections"]), 2)
            self.assertEqual(payload["sections"][1]["start"], 16.5)
            self.assertEqual(payload["sections"][0]["end"], 16.5)

    def test_section_character_labels_marks_vocal_spotlight_when_voice_dominates(self) -> None:
        sections = [
            {"energy": 0.25, "onset": 0.15, "flux": 0.14, "vocals": 0.62, "drums": 0.08, "harmonic": 0.3, "bass": 0.18, "vector": np.array([1.0, 0.0, 0.0])},
            {"energy": 0.3, "onset": 0.18, "flux": 0.16, "vocals": 0.68, "drums": 0.12, "harmonic": 0.28, "bass": 0.16, "vector": np.array([0.9, 0.1, 0.0])},
            {"energy": 0.45, "onset": 0.32, "flux": 0.3, "vocals": 0.22, "drums": 0.46, "harmonic": 0.44, "bass": 0.3, "vector": np.array([0.0, 1.0, 0.0])},
        ]

        labels = _section_character_labels(sections)

        self.assertEqual(labels[1], "vocal_spotlight")


if __name__ == "__main__":
    unittest.main()