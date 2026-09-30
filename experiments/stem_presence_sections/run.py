"""CLI entry point.

    python -m experiments.stem_presence_sections.run compute --song NAME [--song NAME ...]
    python -m experiments.stem_presence_sections.run compute --all-songs
    python -m experiments.stem_presence_sections.run export  --song NAME [--song NAME ...]
    python -m experiments.stem_presence_sections.run export  --all-songs
    python -m experiments.stem_presence_sections.run score

Runs over any song in `data/analysis/`, not only the four gold songs —
`score` is the only subcommand restricted to the scoring corpus (it needs
`reference/human/segments.json`, which only those songs have).
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod
from . import features
from . import paths
from . import score as score_mod


def cmd_compute(songs: list[str]) -> None:
    for song in songs:
        print(f"computing {song} ...", flush=True)
        payload = features.compute_and_cache(song)
        print(f"  {len(payload['bars'])} bars")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score"])
    parser.add_argument("--all-songs", action="store_true")
    parser.add_argument("--song", action="append")
    args = parser.parse_args(argv)

    if args.cmd == "score":
        score_mod.write_report()
        return

    if args.song:
        songs = args.song
    elif args.all_songs:
        songs = paths.all_songs()
    else:
        parser.error("compute/export need --song NAME [--song NAME ...] or --all-songs")
        return

    if args.cmd == "compute":
        cmd_compute(songs)
    elif args.cmd == "export":
        export_mod.export_all(songs)


if __name__ == "__main__":
    main(sys.argv[1:])
