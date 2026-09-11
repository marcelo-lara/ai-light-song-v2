"""CLI entry point.

`compute` needs `torch`/`panns_inference` — not installed in the `app` image,
only in the new `svd-research` sandbox (`ai-light-song-v2-svd-research:dev`,
`experiments/svd_tagger/Dockerfile`). Run it through this experiment's own
launcher:

    ./experiments/svd_tagger/run_in_container.sh \\
        python -m experiments.svd_tagger.run compute --song <name>

`export` and `score` only read the cache/JSON `compute` already wrote (numpy
+ stdlib json — no `torch`), so they run in the plain `app` image:

    docker compose run --rm app python -m experiments.svd_tagger.run export --song <name>
    docker compose run --rm app python -m experiments.svd_tagger.run score

`compute` runs PANNs (`model.py`) over both the vocal stem and the mix, one
forward pass per 5s/1s-hop window, and caches both channels' scores under
`experiments/svd_tagger/cache/`. `export` combines them into the shared
`voiceness_common` proposal shape (channel-tagged rows) and writes
`reference/proposals/svd_tagger.json`. `score` runs the shared
`voiceness_common` scorer against the three incumbents, for both channels.
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, model, paths, score


def cmd_compute(songs: list[str], device: str) -> None:
    tagger = model._load(device)
    failed = []
    for song in songs:
        print(f"computing {song!r} ...", flush=True)
        try:
            data = model.compute(song, device=device, tagger=tagger)
        except Exception as exc:  # noqa: BLE001 — research-sandbox script, surface and continue
            failed.append(song)
            print(f"  FAIL  {song}: {type(exc).__name__}: {exc}"[:200], flush=True)
            continue
        model.save(song, data)
        print(f"  cached {len(data['stem_times'])} stem windows, {len(data['mix_times'])} mix windows")
    if failed:
        print(f"\n{len(failed)} song(s) failed: {', '.join(failed)}")


def cmd_export(songs: list[str]) -> None:
    export_mod.export_all(songs)


def cmd_score(songs: list[str] | None) -> None:
    score.write_report(songs)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score"])
    parser.add_argument("--all", action="store_true", help="run over every analysed song, not just the scoring corpus")
    parser.add_argument("--song", action="append", help="restrict to one song (repeatable)")
    parser.add_argument("--device", default="cpu", help="compute only — cpu by default (see Dockerfile rationale)")
    args = parser.parse_args(argv)

    if args.song:
        songs = args.song
    elif args.all:
        songs = paths.all_analysed_songs()
    else:
        songs = paths.SCORING_CORPUS

    if args.cmd == "compute":
        cmd_compute(songs, args.device)
    elif args.cmd == "export":
        cmd_export(songs)
    elif args.cmd == "score":
        cmd_score(args.song)


if __name__ == "__main__":
    main(sys.argv[1:])
