"""CLI entry point.

    python -m experiments.arrangement_state.run score          [--all] [--song NAME]
    python -m experiments.arrangement_state.run export         [--all] [--song NAME]
    python -m experiments.arrangement_state.run ablation
    python -m experiments.arrangement_state.run margin-sweep   [--all] [--song NAME]
    python -m experiments.arrangement_state.run breath-compare
"""
from __future__ import annotations

import argparse

from . import export as export_mod, paths, score


def _write(name: str, text: str) -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (paths.OUT_ROOT / name).write_text(text)
    print(text)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cmd", choices=["score", "export", "ablation", "margin-sweep", "breath-compare"]
    )
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
    elif args.cmd == "export":
        export_mod.export_all(songs)
    elif args.cmd == "ablation":
        # Fixed song ("_test_song") regardless of --song/--all — the dense
        # texture-labelled corpus member this ablation is measured on.
        _write("ablation.txt", score.ablation_report("_test_song"))
    elif args.cmd == "margin-sweep":
        _write("margin_sweep.txt", score.margin_sweep_report(songs))
    elif args.cmd == "breath-compare":
        # Fixed song ("Armin - Revolution") regardless of --song/--all — the
        # only gold song carrying the hand-marked "Breath" hint.
        _write("breath_compare.txt", score.breath_compare_report("Armin - Revolution"))


if __name__ == "__main__":
    main()
