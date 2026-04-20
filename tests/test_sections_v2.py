from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _bar_config(
    energy: float,
    onset: float,
    flux: float,
    *,
    root_index: int,
    vocals: float = 0.0,
    drums: float = 0.0,
    harmonic: float = 0.0,
    bass: float = 0.0,
) -> dict[str, float]:
    return {
        "energy": energy,
        "onset": onset,
        "flux": flux,
        "root_index": float(root_index),
        "vocals": vocals,
        "drums": drums,
        "harmonic": harmonic,
        "bass": bass,
    }


def _song_payload_from_bars(bar_configs: list[dict[str, float]]) -> tuple[dict, dict, dict, dict[str, list[float]]]:
    beats = []
    bars = []
    beat_features = []
    stem_activity = {"vocals": [], "drums": [], "harmonic": [], "bass": []}
    harmonic_chords = []
    beat_time = 0.5
    active_root: int | None = None
    active_start = beat_time

    for bar_number, config in enumerate(bar_configs, start=1):
        bar_start = beat_time
        root_index = int(config["root_index"])
        if active_root is None:
            active_root = root_index
            active_start = bar_start
        elif root_index != active_root:
            harmonic_chords.append(
                {
                    "time": active_start,
                    "end_s": bar_start,
                    "bar": max(1, bar_number - 1),
                    "beat": 1,
                    "chord": NOTE_NAMES[active_root],
                    "confidence": 1.0,
                }
            )
            active_root = root_index
            active_start = bar_start

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
            beat_features.append(
                {
                    "beat": len(beat_features) + 1,
                    "time": beat_time,
                    "loudness_avg": config["energy"],
                    "onset_density": config["onset"],
                    "flux_avg": config["flux"],
                }
            )
            for key in stem_activity:
                stem_activity[key].append(float(config[key]))
            beat_time += 0.5

        bars.append({"bar": bar_number, "start_s": bar_start, "end_s": beat_time})

    if active_root is not None:
        harmonic_chords.append(
            {
                "time": active_start,
                "end_s": beat_time,
                "bar": len(bar_configs),
                "beat": 1,
                "chord": NOTE_NAMES[active_root],
                "confidence": 1.0,
            }
        )

    return {"beats": beats, "bars": bars}, {"chords": harmonic_chords}, {"beat_features": beat_features}, stem_activity


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

    def test_segment_sections_splits_on_sustained_internal_drum_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            bar_configs = (
                [_bar_config(0.15, 0.10, 0.10, root_index=0, vocals=0.12, drums=0.04, harmonic=0.48, bass=0.18) for _ in range(8)]
                + [_bar_config(0.24, 0.18, 0.12, root_index=5, vocals=0.55, drums=0.06, harmonic=0.10, bass=0.06) for _ in range(4)]
                + [_bar_config(0.52, 0.49, 0.18, root_index=7, vocals=0.28, drums=0.92, harmonic=0.08, bass=0.62) for _ in range(4)]
                + [_bar_config(0.43, 0.42, 0.22, root_index=2, vocals=0.04, drums=0.95, harmonic=0.03, bass=0.54) for _ in range(4)]
                + [_bar_config(0.22, 0.16, 0.12, root_index=0, vocals=0.08, drums=0.10, harmonic=0.36, bass=0.20) for _ in range(4)]
            )
            timing, harmonic, energy, stem_activity = _song_payload_from_bars(bar_configs)

            with patch(
                "analyzer.stages.sections_v2.estimate_stem_activity_by_beat",
                side_effect=[
                    stem_activity["vocals"],
                    stem_activity["drums"],
                    stem_activity["harmonic"],
                    stem_activity["bass"],
                ],
            ):
                payload = segment_sections(paths, timing, harmonic, energy)

            starts = [section["start"] for section in payload["sections"]]
            self.assertIn(24.5, starts)
            split_section = next(section for section in payload["sections"] if section["start"] == 24.5)
            self.assertIn(split_section["label"], {"momentum_lift", "groove_plateau"})

    def test_segment_sections_does_not_split_for_brief_internal_accent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            bar_configs = (
                [_bar_config(0.16, 0.10, 0.10, root_index=0, vocals=0.10, drums=0.04, harmonic=0.50, bass=0.18) for _ in range(8)]
                + [_bar_config(0.24, 0.18, 0.12, root_index=5, vocals=0.52, drums=0.06, harmonic=0.10, bass=0.06) for _ in range(4)]
                + [_bar_config(0.50, 0.46, 0.18, root_index=7, vocals=0.26, drums=0.90, harmonic=0.08, bass=0.60)]
                + [_bar_config(0.27, 0.20, 0.13, root_index=5, vocals=0.48, drums=0.08, harmonic=0.12, bass=0.08) for _ in range(3)]
                + [_bar_config(0.42, 0.40, 0.21, root_index=2, vocals=0.04, drums=0.94, harmonic=0.03, bass=0.52) for _ in range(4)]
                + [_bar_config(0.22, 0.16, 0.12, root_index=0, vocals=0.08, drums=0.10, harmonic=0.36, bass=0.20) for _ in range(4)]
            )
            timing, harmonic, energy, stem_activity = _song_payload_from_bars(bar_configs)

            with patch(
                "analyzer.stages.sections_v2.estimate_stem_activity_by_beat",
                side_effect=[
                    stem_activity["vocals"],
                    stem_activity["drums"],
                    stem_activity["harmonic"],
                    stem_activity["bass"],
                ],
            ):
                payload = segment_sections(paths, timing, harmonic, energy)

            starts = [section["start"] for section in payload["sections"]]
            self.assertNotIn(24.5, starts)

    def test_section_character_labels_prefers_pulse_entry_over_percussion_break(self) -> None:
        sections = [
            {"energy": 0.18, "onset": 0.12, "flux": 0.11, "vocals": 0.12, "drums": 0.04, "harmonic": 0.45, "bass": 0.18, "vector": np.array([1.0, 0.0, 0.0])},
            {"energy": 0.24, "onset": 0.20, "flux": 0.14, "vocals": 0.52, "drums": 0.06, "harmonic": 0.10, "bass": 0.06, "vector": np.array([0.9, 0.1, 0.0])},
            {"energy": 0.52, "onset": 0.50, "flux": 0.20, "vocals": 0.18, "drums": 0.90, "harmonic": 0.08, "bass": 0.62, "vector": np.array([0.0, 1.0, 0.0])},
            {"energy": 0.44, "onset": 0.43, "flux": 0.23, "vocals": 0.02, "drums": 0.95, "harmonic": 0.02, "bass": 0.54, "vector": np.array([0.0, 0.9, 0.1])},
            {"energy": 0.20, "onset": 0.14, "flux": 0.11, "vocals": 0.06, "drums": 0.08, "harmonic": 0.32, "bass": 0.18, "vector": np.array([0.2, 0.0, 0.8])},
        ]

        labels = _section_character_labels(sections)

        self.assertIn(labels[2], {"momentum_lift", "groove_plateau"})
        self.assertNotIn(labels[2], {"breath_space", "percussion_break"})
        self.assertEqual(labels[3], "percussion_break")


if __name__ == "__main__":
    unittest.main()
