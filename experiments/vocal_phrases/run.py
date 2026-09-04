"""CLI entry point.

    python -m experiments.vocal_phrases.run detect [--all]
    python -m experiments.vocal_phrases.run export [--all]
    python -m experiments.vocal_phrases.run score
"""
from __future__ import annotations

import argparse
import sys

from . import detector, export as export_mod, paths, score


def cmd_detect(songs: list[str]) -> None:
    for song in songs:
        print(f"detecting {song} ...", flush=True)
        env = detector.compute_envelope(song)
        detector.save_envelope(env)
        print(f"  cached {len(env.times)} frames")


def cmd_export(songs: list[str]) -> None:
    export_mod.export_all(songs)


def cmd_score() -> None:
    score.write_report()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["detect", "export", "score"])
    parser.add_argument("--all", action="store_true", help="run over every analysed song, not just gold set")
    parser.add_argument("--song", action="append", help="restrict to one song (repeatable)")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    elif args.all:
        songs = paths.all_songs()
    else:
        songs = paths.GOLD_SONGS

    if args.cmd == "detect":
        cmd_detect(songs)
    elif args.cmd == "export":
        cmd_export(songs)
    elif args.cmd == "score":
        cmd_score()


if __name__ == "__main__":
    main(sys.argv[1:])
