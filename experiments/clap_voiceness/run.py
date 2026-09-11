"""CLI entry point.

`compute` needs `transformers`/`torch` for the CLAP forward pass — not
installed in the `app` image, only in the research sandbox
(`ai-light-song-v2-research:dev`, `experiments/drop_detection/research/Dockerfile`,
the same one `experiments/clap/` already uses). Run it through the sibling
experiment's own launcher — no new script, no new pin:

    ./experiments/clap/run_in_container.sh \\
        python -m experiments.clap_voiceness.run compute --song <name>

`export` and `score` only read the cache/JSON `compute` already wrote (numpy
+ stdlib json — no `transformers`), so they run in the plain `app` image:

    docker compose run --rm app python -m experiments.clap_voiceness.run export --song <name>
    docker compose run --rm app python -m experiments.clap_voiceness.run score

`compute` runs one CLAP audio forward pass + one text forward pass per song
(model.py) and caches the per-window differential under
`experiments/clap_voiceness/cache/`. `export` combines it into the shared
`voiceness_common` proposal shape and writes
`reference/proposals/clap_voiceness.json`. `score` runs the shared
`voiceness_common` scorer against the three incumbents.
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, model, paths, score


def cmd_compute(songs: list[str], device: str) -> None:
    from experiments.clap.model import _load as clap_load

    bundle = clap_load(device)
    text_emb = model.text_embeddings(device="cpu")
    failed = []
    for song in songs:
        print(f"computing {song!r} ...", flush=True)
        try:
            data = model.compute(song, device=device, bundle=bundle, text_emb=text_emb)
        except Exception as exc:  # noqa: BLE001 — research-sandbox script, surface and continue
            failed.append(song)
            print(f"  FAIL  {song}: {type(exc).__name__}: {exc}"[:200], flush=True)
            continue
        model.save(song, data)
        print(f"  cached {len(data['times'])} windows")
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
    parser.add_argument("--device", default="cuda", help="compute only — cuda by default")
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
