"""CLI entry point.

`compute` needs `torch`/`whisperx` — not installed in the `app` image, only
in the new `whisperx-research` sandbox (`ai-light-song-v2-whisperx-research:dev`,
`experiments/whisperx_vad/Dockerfile`). Run it through this experiment's own
launcher:

    ./experiments/whisperx_vad/run_in_container.sh \\
        python -m experiments.whisperx_vad.run compute --song <name>

`export` and `score` only read the cache/JSON `compute` already wrote (numpy
+ stdlib json — no `torch`), so they run in the plain `app` image:

    docker compose run --rm app python -m experiments.whisperx_vad.run export --song <name>
    docker compose run --rm app python -m experiments.whisperx_vad.run score

`compute` runs whisperX's VAD front-end (`model.py`) over the vocal stem and
caches the activation curve + binarized phrase spans under
`experiments/whisperx_vad/cache/`. `export` writes the shared
`voiceness_common` proposal shape to `reference/proposals/whisperx_vad.json`.
`score` runs the shared `voiceness_common` scorer against the three
incumbents.
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, model, paths, score


def cmd_compute(songs: list[str], device: str) -> None:
    vad_model = model._load_vad(device)
    failed = []
    for song in songs:
        print(f"computing {song!r} ...", flush=True)
        try:
            data = model.compute(song, device=device, vad_model=vad_model)
        except Exception as exc:  # noqa: BLE001 — research-sandbox script, surface and continue
            failed.append(song)
            print(f"  FAIL  {song}: {type(exc).__name__}: {exc}"[:200], flush=True)
            continue
        model.save(song, data)
        print(f"  cached {len(data['times'])} frames, {len(data['phrase_starts'])} phrases")
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
