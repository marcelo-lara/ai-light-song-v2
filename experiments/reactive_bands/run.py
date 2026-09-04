"""CLI entry point.

    python -m experiments.reactive_bands.run compute [--all]
    python -m experiments.reactive_bands.run export [--all]
    python -m experiments.reactive_bands.run score
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, paths, pipeline, score


def cmd_compute(songs: list[str]) -> None:
    for song in songs:
        for source in ("mix",) + paths.STEM_IDS:
            print(f"computing {song} / {source} ...", flush=True)
            bp = pipeline.compute_and_cache(song, source)
            print(f"  {len(bp.times)} frames")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--song", action="append")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    elif args.all:
        songs = paths.all_songs()
    else:
        songs = paths.GOLD_SONGS

    if args.cmd == "compute":
        cmd_compute(songs)
    elif args.cmd == "export":
        export_mod.export_all(songs)
    elif args.cmd == "score":
        score.write_report()


if __name__ == "__main__":
    main(sys.argv[1:])
