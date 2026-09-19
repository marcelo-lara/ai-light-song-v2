"""CLI entry point.

    python -m experiments.allin1_posterior.run export [--song <name> ...] [--all]
    python -m experiments.allin1_posterior.run score [--song <name> ...] [--all]

No `compute` subcommand — this experiment reads the already-cached
`artifacts/allin1/raw.json` the production pipeline writes; there is nothing
to compute that isn't already on disk.
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, paths, score


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["export", "score"])
    parser.add_argument("--song", action="append", help="restrict to one song (repeatable)")
    parser.add_argument("--all", action="store_true", help="run over every analysed song with an allin1 cache")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    elif args.all:
        songs = paths.all_songs()
    else:
        songs = paths.GOLD_SONGS

    if args.cmd == "export":
        export_mod.export_all(songs)
    elif args.cmd == "score":
        score.write_report(songs)


if __name__ == "__main__":
    main(sys.argv[1:])
