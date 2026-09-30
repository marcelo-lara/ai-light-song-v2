"""CLI entry point.

    python -m experiments.kick_check.run compute --song NAME [--song NAME ...]
    python -m experiments.kick_check.run compute --all-songs
    python -m experiments.kick_check.run export  --song NAME [--song NAME ...]
    python -m experiments.kick_check.run export  --all-songs
    python -m experiments.kick_check.run score
"""
from __future__ import annotations

import argparse
import sys

from experiments.drum_hit_shape import all_songs

from . import export as export_mod
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
        songs = all_songs()
    else:
        parser.error("compute/export need --song NAME [--song NAME ...] or --all-songs")
        return

    if args.cmd == "compute":
        for song in songs:
            print(f"computing {song} ...", flush=True)
            payload = export_mod.compute(song)
            kept = sum(1 for k in payload["kicks"] if k["verdict"] == "keep")
            print(f"  {len(payload['kicks'])} omnizart kicks, {kept} kept")
    elif args.cmd == "export":
        export_mod.export_all(songs)


if __name__ == "__main__":
    main(sys.argv[1:])
