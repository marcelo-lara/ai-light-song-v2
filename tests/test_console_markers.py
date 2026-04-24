from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import call, patch

from analyzer.cli import SONG_SEPARATOR_WIDTH, _print_song_header, _run_single_song, _single_song_command
from analyzer.config import ValidationConfig
from analyzer.paths import SongPaths
from analyzer.pipeline import _print_phase_marker, _print_stage_marker, clear_batch_progress, run_phase_1, set_batch_progress
from analyzer.stages.validation import ValidationResult


class ConsoleMarkerTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_batch_progress()

    def test_print_song_header_writes_separator_and_song_name(self) -> None:
        with patch("builtins.print") as mock_print:
            _print_song_header("Example Song")

        self.assertEqual(
            mock_print.call_args_list,
            [
                call("-" * SONG_SEPARATOR_WIDTH, flush=True),
                call("Example Song", flush=True),
            ],
        )

    def test_print_song_header_includes_batch_progress_prefix(self) -> None:
        set_batch_progress(2, 20)

        with patch("builtins.print") as mock_print:
            _print_song_header("Example Song")

        self.assertEqual(
            mock_print.call_args_list,
            [
                call("-" * SONG_SEPARATOR_WIDTH, flush=True),
                call("[2/20]Example Song", flush=True),
            ],
        )

    def test_print_phase_marker_writes_song_phase_edge(self) -> None:
        with patch("builtins.print") as mock_print:
            _print_phase_marker("Example Song", "phase-1", "start")

        mock_print.assert_called_once_with("Example Song-phase-1-start", flush=True)

    def test_print_stage_marker_writes_song_phase_stage_start(self) -> None:
        with patch("builtins.print") as mock_print:
            _print_stage_marker("Example Song", "phase-1", "ensure-stems")

        mock_print.assert_called_once_with(
            "[1.1] Example Song | ensure-stems",
            flush=True,
        )

    def test_print_stage_marker_includes_batch_progress_prefix(self) -> None:
        set_batch_progress(2, 20)

        with patch("builtins.print") as mock_print:
            _print_stage_marker("Example Song", "phase-1", "ensure-stems")

        mock_print.assert_called_once_with(
            "[2/20][1.1] Example Song | ensure-stems",
            flush=True,
        )

    def test_print_stage_marker_falls_back_when_stage_is_unmapped(self) -> None:
        with patch("builtins.print") as mock_print:
            _print_stage_marker("Example Song", "phase-1", "unknown-stage")

        mock_print.assert_called_once_with(
            "Example Song | unknown-stage",
            flush=True,
        )

    def test_run_single_song_prints_song_header_before_running_pipeline(self) -> None:
        args = argparse.Namespace(
            song="/tmp/Example Song.mp3",
            artifacts_root="/tmp/artifacts",
            reference_root="/tmp/reference",
            fail_on_mismatch=False,
            beat_tolerance_seconds=0.1,
            tolerance_seconds=2.0,
            chord_min_overlap=0.5,
            device=None,
            verbose=False,
            batch_song_index=None,
            batch_song_total=None,
        )
        compare_targets = ("beats", "sections")
        paths = SongPaths(
            song_path=Path("/tmp/Example Song.mp3"),
            artifacts_root=Path("/tmp/artifacts"),
            reference_root=Path("/tmp/reference"),
            output_root=Path("/tmp/output"),
            stems_root=Path("/tmp/stems"),
        )

        with patch("analyzer.cli.build_song_paths", return_value=paths), patch(
            "analyzer.cli.default_validation_report_paths",
            return_value=(Path("/tmp/report.json"), Path("/tmp/report.md")),
        ), patch("analyzer.cli._print_song_header") as mock_header, patch(
            "analyzer.cli.run_phase_1",
            return_value=0,
        ) as mock_run_phase:
            exit_code = _run_single_song(args, compare_targets)

        self.assertEqual(exit_code, 0)
        mock_header.assert_called_once_with("Example Song")
        mock_run_phase.assert_called_once()

    def test_single_song_command_includes_batch_progress_flags(self) -> None:
        args = argparse.Namespace(
            artifacts_root="/tmp/artifacts",
            reference_root="/tmp/reference",
            compare="beats,sections",
            fail_on_mismatch=False,
            beat_tolerance_seconds=0.1,
            tolerance_seconds=2.0,
            chord_min_overlap=0.5,
            device=None,
            verbose=False,
        )

        command = _single_song_command(
            args,
            Path("/tmp/Example Song.mp3"),
            batch_song_index=2,
            batch_song_total=20,
        )

        self.assertEqual(
            command[-4:],
            ["--batch-song-index", "2", "--batch-song-total", "20"],
        )

    def test_run_phase_1_prints_end_marker_when_setup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            config = ValidationConfig(
                compare_targets=("beats",),
                report_json=root / "artifacts" / "Example Song" / "validation" / "phase_1_report.json",
                report_md=root / "artifacts" / "Example Song" / "validation" / "phase_1_report.md",
                fail_on_mismatch=False,
                beat_tolerance_seconds=0.1,
                tolerance_seconds=2.0,
                chord_min_overlap=0.5,
                device=None,
                verbose=False,
            )

            with patch("analyzer.pipeline._print_phase_marker") as mock_phase_marker, patch(
                "analyzer.pipeline.ensure_directory",
                side_effect=RuntimeError("boom"),
            ):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    run_phase_1(paths, config)

        self.assertEqual(
            mock_phase_marker.call_args_list,
            [
                call("Example Song", "phase-1", "start"),
                call("Example Song", "phase-1", "end"),
            ],
        )

    def test_run_phase_1_prints_stage_marker_before_first_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            config = ValidationConfig(
                compare_targets=("beats",),
                report_json=root / "artifacts" / "Example Song" / "validation" / "phase_1_report.json",
                report_md=root / "artifacts" / "Example Song" / "validation" / "phase_1_report.md",
                fail_on_mismatch=False,
                beat_tolerance_seconds=0.1,
                tolerance_seconds=2.0,
                chord_min_overlap=0.5,
                device=None,
                verbose=False,
            )

            with patch("analyzer.pipeline._print_stage_marker") as mock_stage_marker, patch(
                "analyzer.pipeline.ensure_stems",
                side_effect=RuntimeError("boom"),
            ):
                with self.assertRaisesRegex(RuntimeError, "boom"):
                    run_phase_1(paths, config)

        mock_stage_marker.assert_called_once_with("Example Song", "phase-1", "ensure-stems")

    def test_run_phase_1_uses_reference_timing_and_harmonic_when_moises_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            paths.song_path.parent.mkdir(parents=True, exist_ok=True)
            paths.song_path.write_text("", encoding="utf-8")
            reference_path = paths.reference("moises", "chords.json")
            assert reference_path is not None
            reference_path.parent.mkdir(parents=True, exist_ok=True)
            reference_path.write_text("[]", encoding="utf-8")

            config = ValidationConfig(
                compare_targets=("beats", "chords"),
                report_json=root / "artifacts" / "Example Song" / "validation" / "phase_1_report.json",
                report_md=root / "artifacts" / "Example Song" / "validation" / "phase_1_report.md",
                fail_on_mismatch=False,
                beat_tolerance_seconds=0.1,
                tolerance_seconds=2.0,
                chord_min_overlap=0.5,
                device=None,
                verbose=False,
            )

            inferred_timing = {
                "bpm": 120.0,
                "duration": 10.0,
                "beats": [{"index": 1, "time": 0.5, "bar": 1, "beat_in_bar": 1, "type": "downbeat"}],
                "bars": [{"bar": 1, "start_s": 0.5, "end_s": 2.5}],
            }
            reference_timing = {
                "bpm": 123.0,
                "duration": 10.0,
                "generated_from": {"engine": "reference.moises.chords", "dependencies": {"inferred_beats_file": str(paths.artifact("essentia", "beats_inferred.json"))}},
                "beats": [{"index": 1, "time": 1.5, "bar": 1, "beat_in_bar": 1, "type": "downbeat"}],
                "bars": [{"bar": 1, "start_s": 1.5, "end_s": 3.5}],
            }
            inferred_harmonic = {"chords": [{"time": 0.5, "end_s": 2.5, "bar": 1, "beat": 1, "chord": "C"}]}
            reference_harmonic = {
                "generated_from": {"engine": "reference.moises.chords.promotion", "dependencies": {"inferred_harmonic_file": str(paths.artifact("harmonic_inference", "layer_a_harmonic.inferred.json"))}},
                "chords": [{"time": 1.5, "end_s": 3.5, "bar": 1, "beat": 1, "chord": "D"}],
            }
            beat_validation = ValidationResult(status="passed", matched=4, mismatched=0, match_ratio=1.0, details=[], reference_file=str(reference_path), diagnostics=None)
            chord_validation = ValidationResult(status="passed", matched=4, mismatched=0, match_ratio=1.0, details=[], reference_file=str(reference_path), diagnostics=None)
            sections_payload = {"sections": [{"section_id": "section-001", "start": 1.5, "end": 3.5, "label": "reference_section", "confidence": 0.9}]}
            ui_outputs = {"beats": str(paths.beats_output_path), "sections": str(paths.sections_output_path)}
            hints_payload = {"hints": str(paths.hints_output_path), "symbolic_hints": []}
            energy_features = {"beat_features": []}
            symbolic = {"phrase_windows": [], "motif_summary": {"repeated_phrase_groups": []}}
            drum_events = {"generated_from": {"engine": "audiohacking.omnizart.drum"}}
            energy = {"sections": []}
            event_features = {"features": []}
            rule_candidates = {"events": []}
            event_identifiers = {"events": []}
            machine_events = {"events": []}
            review_outputs = {"merged_payload": {"events": []}}
            event_timeline = {"events": []}
            event_benchmark = {"status": "ok"}
            patterns = {"patterns": []}
            unified = {"sections": []}
            lighting = {"events": []}
            lighting_score = "score"
            fft_bands = {"bands": [{"id": "sub"}, {"id": "bass"}, {"id": "low_mid"}, {"id": "mid"}, {"id": "upper_mid"}, {"id": "presence"}, {"id": "brilliance"}]}
            loudness = {
                "rms_loudness": {"sources": [{"id": "mix"}, {"id": "bass"}, {"id": "drums"}, {"id": "harmonic"}, {"id": "vocals"}]},
                "loudness_envelope": {"sources": [{"id": "mix"}, {"id": "bass"}, {"id": "drums"}, {"id": "harmonic"}, {"id": "vocals"}]},
            }
            report = {"generated_artifacts": {}, "notes": [], "validation": {}, "status": "passed", "exit_code": 0}

            with ExitStack() as stack:
                stack.enter_context(patch("analyzer.pipeline.ensure_stems", return_value={"harmonic": "harmonic.wav", "bass": "bass.wav", "vocals": "vocals.wav", "drums": "drums.wav"}))
                stack.enter_context(patch("analyzer.pipeline.extract_timing_grid", return_value=inferred_timing))
                stack.enter_context(patch("analyzer.pipeline.extract_fft_bands", return_value=fft_bands))
                stack.enter_context(patch("analyzer.pipeline.extract_mix_stem_loudness", return_value=loudness))
                stack.enter_context(patch("analyzer.pipeline.validate_beats", return_value=beat_validation))
                mock_reference_timing = stack.enter_context(patch("analyzer.pipeline.build_reference_timing_grid", return_value=reference_timing))
                stack.enter_context(patch("analyzer.pipeline.classify_genre", return_value={"genres": []}))
                stack.enter_context(patch("analyzer.pipeline.extract_hpcp_and_chords", return_value=({}, inferred_harmonic)))
                stack.enter_context(patch("analyzer.pipeline.validate_chords", return_value=chord_validation))
                mock_reference_harmonic = stack.enter_context(patch("analyzer.pipeline.build_reference_harmonic_layer", return_value=reference_harmonic))
                stack.enter_context(patch("analyzer.pipeline.extract_energy_features", return_value=energy_features))
                mock_segment_sections = stack.enter_context(patch("analyzer.pipeline.segment_sections", return_value=sections_payload))
                stack.enter_context(patch("analyzer.pipeline.extract_symbolic_features", return_value=symbolic))
                stack.enter_context(patch("analyzer.pipeline.extract_drum_events", return_value=drum_events))
                stack.enter_context(patch("analyzer.pipeline.generate_section_hints", return_value=hints_payload))
                stack.enter_context(patch("analyzer.pipeline.build_ui_data", return_value=ui_outputs))
                stack.enter_context(patch("analyzer.pipeline.derive_energy_layer", return_value=energy))
                stack.enter_context(patch("analyzer.pipeline.build_event_feature_layer", return_value=event_features))
                stack.enter_context(patch("analyzer.pipeline.generate_rule_candidates", return_value=rule_candidates))
                stack.enter_context(patch("analyzer.pipeline.infer_song_identifiers", return_value=event_identifiers))
                stack.enter_context(patch("analyzer.pipeline.generate_machine_events", return_value=machine_events))
                stack.enter_context(patch("analyzer.pipeline.generate_event_review", return_value=review_outputs))
                stack.enter_context(patch("analyzer.pipeline.export_event_timeline", return_value=event_timeline))
                stack.enter_context(patch("analyzer.pipeline.benchmark_event_outputs", return_value=event_benchmark))
                stack.enter_context(patch("analyzer.pipeline.extract_chord_patterns", return_value=patterns))
                stack.enter_context(patch("analyzer.pipeline.assemble_music_feature_layers", return_value=unified))
                stack.enter_context(patch("analyzer.pipeline.generate_lighting_events", return_value=lighting))
                stack.enter_context(patch("analyzer.pipeline.generate_lighting_score", return_value=lighting_score))
                stack.enter_context(patch("analyzer.pipeline.build_human_hints_alignment", return_value=None))
                stack.enter_context(patch("analyzer.pipeline.build_validation_report", return_value=(report, 0)))
                stack.enter_context(patch("analyzer.pipeline.write_validation_report"))
                stack.enter_context(patch("analyzer.pipeline.write_validation_markdown"))
                exit_code = run_phase_1(paths, config)

            info_payload = json.loads(paths.info_output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        mock_reference_timing.assert_called_once()
        mock_reference_harmonic.assert_called_once()
        self.assertEqual(mock_segment_sections.call_args.args[2], reference_harmonic)
        self.assertEqual(mock_segment_sections.call_args.args[1], reference_timing)
        self.assertEqual(info_payload["artifacts"]["fft_bands"], str(paths.artifact("essentia", "fft_bands.json")))
        self.assertEqual(info_payload["artifacts"]["rms_loudness"], str(paths.artifact("essentia", "rms_loudness.json")))
        self.assertEqual(info_payload["artifacts"]["loudness_envelope"], str(paths.artifact("essentia", "loudness_envelope.json")))
        self.assertEqual(info_payload["generated_from"]["fft_bands_file"], str(paths.artifact("essentia", "fft_bands.json")))
        self.assertEqual(info_payload["generated_from"]["rms_loudness_file"], str(paths.artifact("essentia", "rms_loudness.json")))
        self.assertEqual(info_payload["generated_from"]["loudness_envelope_file"], str(paths.artifact("essentia", "loudness_envelope.json")))
        self.assertEqual(info_payload["debug"]["loudness_source_count"], 5)
        self.assertEqual(info_payload["debug"]["fft_band_count"], 7)


if __name__ == "__main__":
    unittest.main()
