from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.harmonic import build_reference_harmonic_layer
from analyzer.stages.validation import _validate_chords, _validate_sections, validate_beats


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ValidationDiagnosticsTests(unittest.TestCase):
    def test_validate_beats_reports_global_offset_and_local_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            reference_rows = [
                {"curr_beat_time": float(index), "bar_num": (index // 4) + 1, "beat_num": (index % 4) + 1}
                for index in range(8)
            ]
            reference_chords_path = paths.reference("moises", "chords.json")
            assert reference_chords_path is not None
            _write_json(reference_chords_path, reference_rows)
            timing = {
                "beats": [
                    {"index": index + 1, "type": "beat", "time": time_s}
                    for index, time_s in enumerate((0.18, 1.19, 2.20, 3.21, 4.42, 5.43, 6.44))
                ]
            }

            result = validate_beats(paths, timing, tolerance_seconds=0.10)

        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.diagnostics)
        assert result.diagnostics is not None
        self.assertTrue(result.diagnostics["global_offset_present"])
        self.assertTrue(result.diagnostics["local_drift_present"])
        self.assertEqual(result.diagnostics["global_offset_direction"], "late")
        self.assertEqual(result.diagnostics["reference_beat_interval_seconds"], 1.0)

    def test_validate_chords_attributes_mismatch_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            reference_rows = [
                {"curr_beat_time": 0.0, "bar_num": 1, "beat_num": 1, "chord_simple_pop": "C#:maj"},
                {"curr_beat_time": 1.0, "bar_num": 1, "beat_num": 2, "chord_simple_pop": "C#:maj"},
                {"curr_beat_time": 2.0, "bar_num": 1, "beat_num": 3, "chord_simple_pop": "D#:maj"},
                {"curr_beat_time": 3.0, "bar_num": 1, "beat_num": 4, "chord_simple_pop": "D#:maj"},
                {"curr_beat_time": 4.0, "bar_num": 2, "beat_num": 1, "chord_simple_pop": "D#:maj"},
            ]
            reference_chords_path = paths.reference("moises", "chords.json")
            assert reference_chords_path is not None
            _write_json(reference_chords_path, reference_rows)
            harmonic = {
                "chords": [
                    {"time": 0.0, "end_s": 2.0, "bar": 1, "beat": 1, "chord": "C#"},
                    {"time": 2.0, "end_s": 4.0, "bar": 1, "beat": 3, "chord": "Fm"},
                    {"time": 1.75, "end_s": 2.25, "bar": 1, "beat": 2, "chord": "D#"},
                    {"time": 4.2, "end_s": 4.6, "bar": 2, "beat": 2, "chord": "D#"},
                ]
            }

            result = _validate_chords(paths, harmonic, chord_min_overlap=0.75)

        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.diagnostics)
        assert result.diagnostics is not None
        self.assertEqual(result.diagnostics["matched_event_count"], 1)
        self.assertEqual(result.diagnostics["label_mismatch_count"], 1)
        self.assertEqual(result.diagnostics["timing_overlap_failure_count"], 1)
        self.assertEqual(result.diagnostics["no_reference_overlap_count"], 1)

    def test_validate_sections_reports_snap_like_boundary_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            reference_segments_path = paths.reference("moises", "segments.json")
            assert reference_segments_path is not None
            _write_json(
                reference_segments_path,
                [
                    {"start": 0.0, "label": "opening"},
                    {"start": 4.0, "label": "lift"},
                    {"start": 8.0, "label": "tail"},
                ],
            )
            reference_chords_path = paths.reference("moises", "chords.json")
            assert reference_chords_path is not None
            _write_json(
                reference_chords_path,
                [
                    {"curr_beat_time": float(index), "bar_num": (index // 4) + 1, "beat_num": (index % 4) + 1, "chord_simple_pop": "C#:maj"}
                    for index in range(12)
                ],
            )
            sections = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 5.0, "label": "opening"},
                    {"section_id": "section-002", "start": 5.0, "end": 9.0, "label": "lift"},
                    {"section_id": "section-003", "start": 9.0, "end": 12.0, "label": "tail"},
                ]
            }

            result = _validate_sections(paths, sections, tolerance_seconds=2.0)

        self.assertEqual(result.status, "passed")
        self.assertIsNotNone(result.diagnostics)
        assert result.diagnostics is not None
        self.assertEqual(result.diagnostics["dominant_snap_multiple_beats"], 1)
        self.assertEqual(result.diagnostics["snap_like_boundary_count"], 2)
        self.assertEqual(result.diagnostics["boundary_offset_direction"], "late")

    def test_build_reference_harmonic_layer_promotes_reference_chords(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            reference_chords_path = paths.reference("moises", "chords.json")
            assert reference_chords_path is not None
            _write_json(
                reference_chords_path,
                [
                    {"curr_beat_time": 0.5, "bar_num": 1, "beat_num": 1, "chord_simple_pop": "C#:maj"},
                    {"curr_beat_time": 1.0, "bar_num": 1, "beat_num": 2, "chord_simple_pop": "C#:maj"},
                    {"curr_beat_time": 1.5, "bar_num": 1, "beat_num": 3, "chord_simple_pop": "D#:maj"},
                    {"curr_beat_time": 2.0, "bar_num": 1, "beat_num": 4, "chord_simple_pop": "Fm:add9"},
                ],
            )
            timing = {
                "bars": [{"bar": 1, "start_s": 0.5, "end_s": 2.5}],
                "beats": [],
            }

            payload = build_reference_harmonic_layer(paths, timing, inferred_harmonic_path="/tmp/inferred.json")

        self.assertEqual([event["chord"] for event in payload["chords"]], ["C#", "D#", "Fm"])
        self.assertEqual(payload["generated_from"]["engine"], "reference.moises.chords.promotion")
        self.assertEqual(payload["generated_from"]["dependencies"]["inferred_harmonic_file"], "/tmp/inferred.json")


if __name__ == "__main__":
    unittest.main()