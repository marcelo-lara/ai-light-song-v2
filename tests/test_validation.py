from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.validation.beats import validate_beats
from analyzer.stages.validation.chords import _validate_chords
from analyzer.stages.validation.drums import validate_drums
from analyzer.stages.validation.sections import _validate_sections


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_timing(bar_chords: list[str]) -> dict:
    beats: list[dict[str, object]] = []
    bars: list[dict[str, object]] = []
    beat_time = 0.0
    for bar_number in range(1, len(bar_chords) + 1):
        bar_start = beat_time
        for beat_in_bar in range(1, 5):
            beats.append(
                {
                    "index": len(beats) + 1,
                    "time": round(beat_time, 6),
                    "bar": bar_number,
                    "beat_in_bar": beat_in_bar,
                    "type": "downbeat" if beat_in_bar == 1 else "beat",
                }
            )
            beat_time += 0.5
        bars.append(
            {
                "bar": bar_number,
                "start_s": round(bar_start, 6),
                "end_s": round(beat_time, 6),
            }
        )

    return {
        "beats": beats,
        "bars": bars,
        "bpm": 120.0,
        "duration": round(beat_time, 6),
    }


def _build_harmonic(bar_chords: list[str]) -> dict:
    chords: list[dict[str, object]] = []
    for bar_index, chord in enumerate(bar_chords):
        start_s = round(bar_index * 2.0, 6)
        chords.append(
            {
                "time": start_s,
                "end_s": round(start_s + 2.0, 6),
                "bar": bar_index + 1,
                "beat": 1,
                "chord": chord,
                "confidence": 1.0,
            }
        )
    return {"chords": chords}


class ValidationDiagnosticsTests(unittest.TestCase):
    def test_validate_drums_reports_debug_paths_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            timing = _build_timing(["C#", "D#"])
            _write_json(
                paths.artifact("symbolic_transcription", "drum_events.json"),
                {
                    "schema_version": "1.0",
                    "song_name": "_test_song",
                    "generated_from": {
                        "source_song_path": str(paths.song_path),
                        "engine": "audiohacking.omnizart.drum",
                        "dependencies": {
                            "drums_stem": str(paths.stems_dir / "drums.wav"),
                            "beats_file": str(paths.artifact("essentia", "beats.json")),
                            "raw_midi_cache": str(paths.artifact("symbolic_transcription", "omnizart", "drums.mid")),
                        },
                        "debug_sources": {
                            "full_mix": str(paths.song_path),
                            "drums_stem": str(paths.stems_dir / "drums.wav"),
                        },
                    },
                    "summary": {
                        "event_count": 4,
                        "kick_count": 1,
                        "snare_count": 1,
                        "hat_count": 2,
                        "unresolved_count": 0,
                    },
                    "events": [
                        {
                            "event_id": "drum-event-00001",
                            "time": 0.0,
                            "event_type": "kick",
                            "alignment_resolved": True,
                            "aligned_bar": 1,
                            "aligned_beat": 1,
                            "aligned_beat_global": 1,
                        },
                        {
                            "event_id": "drum-event-00002",
                            "time": 0.25,
                            "event_type": "hat",
                            "alignment_resolved": True,
                            "aligned_bar": 1,
                            "aligned_beat": 1,
                            "aligned_beat_global": 1,
                        },
                        {
                            "event_id": "drum-event-00003",
                            "time": 0.5,
                            "event_type": "snare",
                            "alignment_resolved": True,
                            "aligned_bar": 1,
                            "aligned_beat": 2,
                            "aligned_beat_global": 2,
                        },
                        {
                            "event_id": "drum-event-00004",
                            "time": 0.75,
                            "event_type": "hat",
                            "alignment_resolved": True,
                            "aligned_bar": 1,
                            "aligned_beat": 2,
                            "aligned_beat_global": 2,
                        },
                    ],
                },
            )
            drum_midi_path = paths.artifact("symbolic_transcription", "omnizart", "drums.mid")
            drum_midi_path.parent.mkdir(parents=True, exist_ok=True)
            drum_midi_path.write_bytes(b"MThd")

            result = validate_drums(paths, timing)

        self.assertEqual(result.status, "passed")
        self.assertIsNotNone(result.diagnostics)
        assert result.diagnostics is not None
        self.assertEqual(result.diagnostics["kick_count"], 1)
        self.assertEqual(result.diagnostics["snare_count"], 1)
        self.assertFalse(result.diagnostics["recognizable_hat_pulse"])

    def test_validate_beats_reports_global_offset_and_local_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
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
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            # Real reference/moises/chords.json rows carry no bar_num/beat_num
            # of their own -- only curr_beat_time and the chord_* columns.
            reference_rows = [
                {"curr_beat_time": 0.0, "chord_simple_pop": "C#:maj"},
                {"curr_beat_time": 1.0, "chord_simple_pop": "C#:maj"},
                {"curr_beat_time": 2.0, "chord_simple_pop": "D#:maj"},
                {"curr_beat_time": 3.0, "chord_simple_pop": "D#:maj"},
                {"curr_beat_time": 4.0, "chord_simple_pop": "D#:maj"},
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
            timing = _build_timing(["C#", "D#"])

            result = _validate_chords(paths, harmonic, timing, chord_min_overlap=0.75)

        self.assertEqual(result.status, "failed")
        self.assertIsNotNone(result.diagnostics)
        assert result.diagnostics is not None
        self.assertEqual(result.diagnostics["matched_event_count"], 1)
        self.assertEqual(result.diagnostics["label_mismatch_count"], 1)
        self.assertEqual(result.diagnostics["timing_overlap_failure_count"], 1)
        self.assertEqual(result.diagnostics["no_reference_overlap_count"], 1)

    def test_validate_chords_marks_unknown_position_when_grid_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            reference_rows = [
                {"curr_beat_time": 0.0, "chord_simple_pop": "C#:maj"},
                {"curr_beat_time": 2.0, "chord_simple_pop": "D#:maj"},
            ]
            reference_chords_path = paths.reference("moises", "chords.json")
            assert reference_chords_path is not None
            _write_json(reference_chords_path, reference_rows)
            harmonic = {"chords": [{"time": 0.0, "end_s": 2.0, "bar": 1, "beat": 1, "chord": "C#"}]}

            # No beats in the grid at all -- position is genuinely unknown, not
            # invented as bar 0 / beat 0 (no silent fallbacks).
            result = _validate_chords(paths, harmonic, timing={"beats": []}, chord_min_overlap=0.75)

        self.assertEqual(result.status, "passed")
        matched_reference = result.details[0]["reference"]
        self.assertIsNotNone(matched_reference)
        self.assertIsNone(matched_reference["bar"])
        self.assertIsNone(matched_reference["beat"])

    def test_validate_sections_reports_snap_like_boundary_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
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
                    {"section_id": "section-001", "start": 0.0, "end": 5.0, "function": "opening"},
                    {"section_id": "section-002", "start": 5.0, "end": 9.0, "function": "lift"},
                    {"section_id": "section-003", "start": 9.0, "end": 12.0, "function": "tail"},
                ]
            }

            result = _validate_sections(paths, sections, tolerance_seconds=2.0)

        self.assertEqual(result.status, "passed")
        self.assertIsNotNone(result.diagnostics)
        assert result.diagnostics is not None
        self.assertEqual(result.diagnostics["dominant_snap_multiple_beats"], 1)
        self.assertEqual(result.diagnostics["snap_like_boundary_count"], 2)
        self.assertEqual(result.diagnostics["boundary_offset_direction"], "late")

if __name__ == "__main__":
    unittest.main()