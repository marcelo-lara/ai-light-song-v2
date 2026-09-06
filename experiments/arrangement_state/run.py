"""CLI entry point.

    python -m experiments.arrangement_state.run score  [--all] [--song NAME]
    python -m experiments.arrangement_state.run export [--all] [--song NAME]
"""
from __future__ import annotations

import argparse

from . import export as export_mod, paths, score


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["score", "export"])
    parser.add_argument("--all", action="store_true", help="every analysed song, not just the gold set")
    parser.add_argument("--song", action="append", help="restrict to one song (repeatable)")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    elif args.all:
        songs = paths.all_songs()
    else:
        songs = paths.GOLD_SONGS

    if args.cmd == "score":
        score.write_report(songs)
    else:
        export_mod.export_all(songs)


if __name__ == "__main__":
    main()
