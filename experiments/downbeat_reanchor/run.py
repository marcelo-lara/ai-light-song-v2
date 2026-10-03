"""CLI entry point.

    python -m experiments.downbeat_reanchor.run export --song NAME [--song NAME ...] | --all-songs
    python -m experiments.downbeat_reanchor.run score
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod
from . import paths
from . import score as score_mod


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["export", "score"])
    parser.add_argument("--all-songs", action="store_true")
    parser.add_argument("--song", action="append")
    args = parser.parse_args(argv)
    if args.cmd == "score":
        score_mod.run()
        return
    if args.song:
        songs = args.song
    elif args.all_songs:
        songs = paths.all_songs()
    else:
        parser.error("export needs --song NAME [--song NAME ...] or --all-songs")
        return
    export_mod.export_all(songs)


if __name__ == "__main__":
    main(sys.argv[1:])
