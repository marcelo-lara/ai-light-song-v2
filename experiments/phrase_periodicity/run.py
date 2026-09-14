"""CLI entry point.

    python -m experiments.phrase_periodicity.run compute [--all] [--song NAME]
    python -m experiments.phrase_periodicity.run export  [--all] [--song NAME]
    python -m experiments.phrase_periodicity.run score
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, features, paths, score


def cmd_compute(songs: list[str]) -> None:
    for song in songs:
        print(f"computing {song} ...", flush=True)
        payload = features.compute_and_cache(song)
        nbars = len(payload["z_bass"])
        print(f"  {len(payload['downbeats'])} downbeats, {nbars} bars, "
              f"{len(payload['block_starts'])} blocks")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--song", action="append")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    else:
        songs = paths.SONGS

    if args.cmd == "compute":
        cmd_compute(songs)
    elif args.cmd == "export":
        export_mod.export_all(songs)
    elif args.cmd == "score":
        score.write_report()


if __name__ == "__main__":
    main(sys.argv[1:])
