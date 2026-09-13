"""CLI entry point.

`compute` needs `torch`/`speechbrain`/`sklearn`/`librosa` — `torch`/`librosa`
are already in the `app` image, but `speechbrain` and `scikit-learn` are not,
so `compute` needs the new `singer-identity-research` sandbox
(`ai-light-song-v2-singer-identity-research:dev`,
`experiments/singer_identity/Dockerfile`). Run it through this experiment's
own launcher:

    ./experiments/singer_identity/run_in_container.sh \\
        python -m experiments.singer_identity.run compute --song <name>

`export` and `score` only read the cache/JSON `compute` already wrote (numpy
+ stdlib json — no `torch`/`speechbrain`), so they run in the plain `app`
image:

    docker compose run --rm app python -m experiments.singer_identity.run export --song <name>
    docker compose run --rm app python -m experiments.singer_identity.run score
    docker compose run --rm app python -m experiments.singer_identity.run calibrate

`compute` reuses `whisperx_vad`'s cached activation (must already exist for
the song — this experiment never recomputes VAD itself), embeds the gated
windows with ECAPA-TDNN (`model.py`) and caches the result under
`experiments/singer_identity/cache/`. `export` writes the shared
`voiceness_common` proposal shape (plus the `singer_change` extra) to
`reference/proposals/singer_identity.json`. `score` runs the shared
`voiceness_common` scorer against `whisperx_vad` and the three incumbents.
`calibrate` scores the cluster count `k` itself against
`singer_ground_truth.json`'s declared `lead_voices` (see `score.py`) — reads
only the cache `compute` already wrote, no song argument.
"""
from __future__ import annotations

import argparse
import sys

from . import export as export_mod, model, paths, score


def cmd_compute(songs: list[str], device: str) -> None:
    encoder = model._load_encoder(device)
    failed = []
    for song in songs:
        print(f"computing {song!r} ...", flush=True)
        try:
            data = model.compute(song, device=device, encoder=encoder)
        except Exception as exc:  # noqa: BLE001 — research-sandbox script, surface and continue
            failed.append(song)
            print(f"  FAIL  {song}: {type(exc).__name__}: {exc}"[:200], flush=True)
            continue
        model.save(song, data)
        n_embedded = int((data["cluster_of_window"] >= 0).sum())
        print(f"  cached {len(data['starts'])} windows, {n_embedded} embedded, k={int(data['k'])}")
    if failed:
        print(f"\n{len(failed)} song(s) failed: {', '.join(failed)}")


def cmd_export(songs: list[str]) -> None:
    export_mod.export_all(songs)


def cmd_score(songs: list[str] | None) -> None:
    score.write_report(songs)


def cmd_calibrate() -> None:
    score.write_calibration_report()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["compute", "export", "score", "calibrate"])
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
    elif args.cmd == "calibrate":
        cmd_calibrate()


if __name__ == "__main__":
    main(sys.argv[1:])
