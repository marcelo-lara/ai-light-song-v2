"""CLI entry point.

    python -m experiments.vocal_voiceness.run compute --song <name>
    python -m experiments.vocal_voiceness.run export --song <name>
    python -m experiments.vocal_voiceness.run score

`compute` computes the three per-frame cues (features.py) and caches them
under `experiments/vocal_voiceness/cache/`. `export` combines them
(model.py) and writes `reference/proposals/vocal_voiceness.json`. `score`
runs the shared `voiceness_common` scorer against the three incumbents.
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, features, paths, score


def cmd_compute(songs: list[str]) -> None:
    for song in songs:
        print(f"computing {song!r} ...", flush=True)
        feat = features.compute_features(song)
        features.save_features(feat)
        print(f"  cached {len(feat.times)} frames")


def cmd_export(songs: list[str]) -> None:
    export_mod.export_all(songs)


def cmd_score(songs: list[str] | None) -> None:
    score.write_report(songs)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score"])
    parser.add_argument("--all", action="store_true", help="run over every analysed song, not just the scoring corpus")
    parser.add_argument("--song", action="append", help="restrict to one song (repeatable)")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    elif args.all:
        songs = sorted(
            p.name
            for p in paths.ANALYSIS_ROOT.iterdir()
            if p.is_dir() and (p / "artifacts" / "stems" / "vocals.wav").exists()
        )
    else:
        songs = paths.SCORING_CORPUS

    if args.cmd == "compute":
        cmd_compute(songs)
    elif args.cmd == "export":
        cmd_export(songs)
    elif args.cmd == "score":
        cmd_score(args.song)


if __name__ == "__main__":
    main(sys.argv[1:])
