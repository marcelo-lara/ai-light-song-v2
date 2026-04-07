from __future__ import annotations

import argparse
import sys
from pathlib import Path

from analyzer.config import ValidationConfig, build_song_paths
from analyzer.exceptions import AnalyzerError, UsageError
from analyzer.pipeline import run_phase_1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m analyzer.cli")
    subparsers = parser.add_subparsers(dest="command")

    validate = subparsers.add_parser("validate-phase-1", help="Run the phase-1 analyzer and optional validation")
    validate.add_argument("--song", required=True)
    validate.add_argument("--artifacts-root", required=True)
    validate.add_argument("--reference-root")
    validate.add_argument("--compare", default="chords,sections")
    validate.add_argument("--report-json", required=True)
    validate.add_argument("--report-md")
    validate.add_argument("--fail-on-mismatch", action="store_true")
    validate.add_argument("--tolerance-seconds", type=float, default=2.0)
    validate.add_argument("--chord-min-overlap", type=float, default=0.5)
    validate.add_argument("--device")
    validate.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "validate-phase-1":
        parser.print_help()
        return 2

    compare_targets = tuple(item.strip() for item in args.compare.split(",") if item.strip())
    supported_targets = {"chords", "sections"}
    try:
        if not set(compare_targets).issubset(supported_targets):
            raise UsageError(f"Unsupported compare target. Supported values: {sorted(supported_targets)}")

        paths = build_song_paths(args.song, args.artifacts_root, args.reference_root)
        config = ValidationConfig(
            compare_targets=compare_targets,
            report_json=Path(args.report_json),
            report_md=Path(args.report_md) if args.report_md else None,
            fail_on_mismatch=args.fail_on_mismatch,
            tolerance_seconds=args.tolerance_seconds,
            chord_min_overlap=args.chord_min_overlap,
            device=args.device,
            verbose=args.verbose,
        )
        return run_phase_1(paths, config)
    except AnalyzerError as exc:
        if args.verbose:
            raise
        print(str(exc), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())