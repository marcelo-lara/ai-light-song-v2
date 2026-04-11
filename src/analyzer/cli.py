from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from analyzer.config import (
    ValidationConfig,
    build_song_paths,
    default_validation_report_paths,
    discover_song_files,
)
from analyzer.exceptions import AnalyzerError, UsageError
from analyzer.pipeline import run_phase_1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m analyzer",
        description="Run the phase-1 analyzer pipeline and write validation reports.",
    )
    parser.add_argument("--song")
    parser.add_argument("--all-songs", action="store_true", help="Analyze every .mp3 under the songs root")
    parser.add_argument("--songs-root", help="Songs directory for --all-songs. Defaults to <artifacts-root parent>/songs")
    parser.add_argument("--artifacts-root", default="/data/artifacts")
    parser.add_argument("--reference-root", default="/data/reference")
    parser.add_argument("--compare", default="beats,chords,sections,energy,patterns,unified")
    parser.add_argument("--fail-on-mismatch", action="store_true")
    parser.add_argument("--beat-tolerance-seconds", type=float, default=0.10)
    parser.add_argument("--tolerance-seconds", type=float, default=2.0)
    parser.add_argument("--chord-min-overlap", type=float, default=0.5)
    parser.add_argument("--device")
    parser.add_argument("--verbose", action="store_true")
    return parser


def _build_validation_config(
    args: argparse.Namespace,
    compare_targets: tuple[str, ...],
    report_json: Path,
    report_md: Path,
) -> ValidationConfig:
    return ValidationConfig(
        compare_targets=compare_targets,
        report_json=report_json,
        report_md=report_md,
        fail_on_mismatch=args.fail_on_mismatch,
        beat_tolerance_seconds=args.beat_tolerance_seconds,
        tolerance_seconds=args.tolerance_seconds,
        chord_min_overlap=args.chord_min_overlap,
        device=args.device,
        verbose=args.verbose,
    )


def _validate_args(args: argparse.Namespace, supported_targets: set[str]) -> tuple[str, ...]:
    compare_targets = tuple(item.strip() for item in args.compare.split(",") if item.strip())
    if not compare_targets:
        raise UsageError("At least one compare target is required.")
    if not set(compare_targets).issubset(supported_targets):
        raise UsageError(f"Unsupported compare target. Supported values: {sorted(supported_targets)}")
    if bool(args.song) == bool(args.all_songs):
        raise UsageError("Pass exactly one of --song or --all-songs.")
    return compare_targets


def _run_single_song(args: argparse.Namespace, compare_targets: tuple[str, ...]) -> int:
    paths = build_song_paths(args.song, args.artifacts_root, args.reference_root)
    report_json, report_md = default_validation_report_paths(paths)
    config = _build_validation_config(
        args,
        compare_targets,
        report_json,
        report_md,
    )
    return run_phase_1(paths, config)


def _batch_exit_code(exit_codes: list[int]) -> int:
    if any(code == 3 for code in exit_codes):
        return 3
    if any(code == 1 for code in exit_codes):
        return 1
    return 0


def _run_all_songs(args: argparse.Namespace, compare_targets: tuple[str, ...]) -> int:
    exit_codes: list[int] = []
    songs = discover_song_files(args.artifacts_root, args.songs_root)
    for song_path in songs:
        paths = build_song_paths(str(song_path), args.artifacts_root, args.reference_root)
        report_json, report_md = default_validation_report_paths(paths)
        config = _build_validation_config(args, compare_targets, report_json, report_md)
        try:
            exit_code = run_phase_1(paths, config)
            print(f"[{paths.song_name}] wrote {report_json}")
        except AnalyzerError as exc:
            exit_code = exc.exit_code
            if args.verbose:
                print(f"[{paths.song_name}] failed", file=sys.stderr)
                traceback.print_exc()
            else:
                print(f"[{paths.song_name}] {exc}", file=sys.stderr)
        exit_codes.append(exit_code)

    passed = sum(1 for code in exit_codes if code == 0)
    failed = len(exit_codes) - passed
    print(f"Processed {len(exit_codes)} song(s): {passed} passed, {failed} failed.")
    return _batch_exit_code(exit_codes)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    supported_targets = {"beats", "chords", "sections", "energy", "patterns", "unified"}
    try:
        compare_targets = _validate_args(args, supported_targets)
        if args.all_songs:
            return _run_all_songs(args, compare_targets)
        return _run_single_song(args, compare_targets)
    except AnalyzerError as exc:
        if args.verbose:
            raise
        print(str(exc), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())