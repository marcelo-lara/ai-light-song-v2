"""CLI entry point.

    python -m experiments.filter_sweep.run compute --song NAME [--song NAME ...] | --all-songs
    python -m experiments.filter_sweep.run export  --song NAME [--song NAME ...] | --all-songs
    python -m experiments.filter_sweep.run score
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod
from . import features, paths
from . import score as score_mod


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score"])
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
        parser.error("compute/export need --song NAME [--song NAME ...] or --all-songs")
        return
    if args.cmd == "compute":
        for song in songs:
            print(f"computing {song} ...", flush=True)
            p = features.compute_and_cache(song)
            print(f"  {len(p['series']['harmonic']['centroid'])} grid samples")
    else:
        export_mod.export_all(songs)


if __name__ == "__main__":
    main(sys.argv[1:])
