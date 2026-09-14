"""CLI entry point.

    python -m experiments.voice_multiplicity.run compute [--all] [--song NAME]
    python -m experiments.voice_multiplicity.run export  [--all] [--song NAME]
    python -m experiments.voice_multiplicity.run score
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod
from . import features
from . import paths
from . import score


def cmd_compute(songs: list[str]) -> None:
    for song in songs:
        try:
            print(f"computing {song} ...", flush=True)
            payload = features.compute_and_cache(song)
            print(f"  {len(payload['times'])} frames, {sum(payload['present'])} present")
        except Exception as e:
            print(f"  ERROR: {e}")


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
