"""CLI entry point.

    python -m experiments.bar_features.run compute --song NAME [--song NAME ...] | --all-songs
    python -m experiments.bar_features.run export  --song NAME [--song NAME ...] | --all-songs
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod
from . import features, paths


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export"])
    parser.add_argument("--all-songs", action="store_true")
    parser.add_argument("--song", action="append")
    args = parser.parse_args(argv)
    if args.song:
        songs = args.song
    elif args.all_songs:
        songs = paths.all_songs()
    else:
        parser.error("need --song NAME [--song NAME ...] or --all-songs")
        return
    if args.cmd == "compute":
        for song in songs:
            print(f"computing {song} ...", flush=True)
            p = features.compute_and_cache(song)
            print(f"  {len(p['bars'])} bars, {len(p['half_beats'])} half-beats")
    else:
        export_mod.export_all(songs)


if __name__ == "__main__":
    main(sys.argv[1:])
