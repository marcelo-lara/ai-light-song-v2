"""CLI entry point.

    # GPU step — needs the ACE-Step sandbox image, see run_in_container.sh
    ./experiments/acestep_transcriber/run_in_container.sh python -m experiments.rhythm_vocal_onsets.run compute --song NAME

    # no GPU — reads the cache `compute` wrote
    python -m experiments.rhythm_vocal_onsets.run export --song NAME
    python -m experiments.rhythm_vocal_onsets.run score

`compute` must never run through the normal `./experiment` queue path — see
`compute.py`'s docstring. This file exists so the CLI shape matches every
other experiment in the family; only the launcher differs.
"""
from __future__ import annotations

import argparse
import sys

from . import compute as compute_mod, export as export_mod, paths, score


def cmd_compute(songs: list[str]) -> None:
    for song in songs:
        rows = compute_mod.compute_and_cache(song)
        print(f"computing {song} ... {len(rows)} spans")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--song", action="append")
    args = parser.parse_args(argv)

    songs = args.song if args.song else paths.SONGS

    if args.cmd == "compute":
        cmd_compute(songs)
    elif args.cmd == "export":
        export_mod.export_all(songs)
    elif args.cmd == "score":
        score.write_report()


if __name__ == "__main__":
    main(sys.argv[1:])
