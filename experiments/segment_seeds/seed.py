"""CLI entry point.

    python -m experiments.segment_seeds.seed --song <name>
    python -m experiments.segment_seeds.seed --all-songs

For each song, computes the seed rows (refinement item 6 "Seeds first") and
writes them as a bare JSON array to `reference/human/segments.seed.json`.
Never writes `segments.json` (CLAUDE.md "no silent fallbacks" / this
experiment's one allowed write path — see `paths.seed_out_path`).
"""
from __future__ import annotations

import argparse
import json
import sys

from . import features, paths


def run_song(song: str) -> None:
    rows = features.compute_seed(song)
    out_path = paths.seed_out_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"{song}: {len(rows)} rows -> {out_path}", flush=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--song", action="append")
    parser.add_argument("--all-songs", action="store_true")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    elif args.all_songs:
        songs = paths.all_analysed_songs()
    else:
        parser.error("pass --song NAME (repeatable) or --all-songs")
        return

    for song in songs:
        run_song(song)


if __name__ == "__main__":
    main(sys.argv[1:])
