"""CLI entry point.

    python -m experiments.demucs_ablation.run compute --song <name> --variant <htdemucs|htdemucs_ft|htdemucs_6s>
    python -m experiments.demucs_ablation.run export [--song <name> ...] [--variant <name> ...]

`compute` runs Demucs separation for one song x one variant and caches the
stems under `experiments/demucs_ablation/cache/` — never touches
`data/analysis/*/artifacts/stems/`. `export` scores whatever is already
cached and writes `out/score.json`.
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, paths, separate


def cmd_compute(songs: list[str], variants: list[str], force: bool) -> None:
    for song in songs:
        for variant in variants:
            print(f"separating {song!r} under {variant!r} ...", flush=True)
            try:
                stems = separate.separate(song, variant, force=force)
            except Exception as exc:  # noqa: BLE001 — reported, not swallowed
                print(f"  FAILED: {exc}", flush=True)
                continue
            print(f"  cached: {list(stems.keys())}")


def cmd_export(songs: list[str], variants: list[str]) -> None:
    export_mod.write_report(songs, variants)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export"])
    parser.add_argument("--song", action="append", help="restrict to one song (repeatable)")
    parser.add_argument("--variant", action="append", choices=list(paths.VARIANTS), help="restrict to one variant (repeatable)")
    parser.add_argument("--force", action="store_true", help="re-separate even if cached")
    args = parser.parse_args(argv)

    songs = args.song if args.song else paths.SCORING_CORPUS
    variants = args.variant if args.variant else list(paths.VARIANTS)

    if args.cmd == "compute":
        cmd_compute(songs, variants, args.force)
    elif args.cmd == "export":
        cmd_export(songs, variants)


if __name__ == "__main__":
    main(sys.argv[1:])
