from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

from analyzer.cli import SONG_SEPARATOR_WIDTH, _print_song_header, _run_single_song
from analyzer.config import ValidationConfig
from analyzer.paths import SongPaths
from analyzer.pipeline import _print_phase_marker, run_phase_1


class ConsoleMarkerTests(unittest.TestCase):
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

    def test_print_phase_marker_writes_song_phase_edge(self) -> None:
        with patch("builtins.print") as mock_print:
            _print_phase_marker("Example Song", "phase-1", "start")

        mock_print.assert_called_once_with("Example Song-phase-1-start", flush=True)

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


if __name__ == "__main__":
    unittest.main()