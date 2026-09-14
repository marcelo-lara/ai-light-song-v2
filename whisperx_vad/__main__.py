"""CLI entry point — `python -m whisperx_vad --song <path>` or `--all-songs`,
mirroring `./analyze`'s own surface (`analyzer.cli`, `analyzer.config`).

Only runs inside the `whisperx` Compose service (`torch~=2.8.0`, incompatible
with the `app` image's `torch==2.1.2` pin) — Docker only:

    docker compose run --rm whisperx --song /data/songs/<song>.mp3
    docker compose run --rm whisperx --all-songs

`--all-songs` isolates each song in its own subprocess, the same reasoning
`analyzer.cli._run_all_songs` gives: unstable native state (loaded torch
models) must not leak between songs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

from analyzer.config import build_song_paths, discover_song_files
from analyzer.exceptions import AnalyzerError

from . import export as export_mod


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="whisperx_vad")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--song", help="Path to one song's source .mp3")
    group.add_argument("--all-songs", action="store_true", help="Run over every .mp3 under the songs root")
    parser.add_argument("--analysis-root", default="/data/analysis", help="Root of data/analysis (default: /data/analysis, the container mount)")
    parser.add_argument("--songs-root", default=None, help="Songs directory for --all-songs. Defaults to <analysis-root parent>/songs")
    parser.add_argument("--device", default="cpu", help="torch device for the VAD model (default: cpu)")
    return parser


def _run_one_song(song: str, analysis_root: str, device: str) -> int:
    song_paths = build_song_paths(song, analysis_root)
    print(f"[{song_paths.song_name}] whisperx-vad ...", flush=True)
    try:
        export_mod.export(song_paths, device=device)
    except AnalyzerError as exc:
        print(f"[{song_paths.song_name}] FAILED: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 — surface any other failure loudly, no silent fallback
        print(f"[{song_paths.song_name}] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    print(f"[{song_paths.song_name}] wrote {export_mod.paths.output_path(song_paths)}")
    return 0


def _run_all_songs(analysis_root: str, songs_root: str | None, device: str) -> int:
    songs = discover_song_files(analysis_root, songs_root)
    exit_codes: list[int] = []
    total = len(songs)
    for index, song_path in enumerate(songs, start=1):
        print(f"[{index}/{total}] {song_path.name}", flush=True)
        command = [
            sys.executable, "-m", "whisperx_vad",
            "--song", str(song_path),
            "--analysis-root", analysis_root,
            "--device", device,
        ]
        if songs_root:
            command += ["--songs-root", songs_root]
        completed = subprocess.run(command, check=False)
        exit_codes.append(int(completed.returncode))

    passed = sum(1 for code in exit_codes if code == 0)
    failed = len(exit_codes) - passed
    print(f"Processed {len(exit_codes)} song(s): {passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.song:
        return _run_one_song(args.song, args.analysis_root, args.device)
    return _run_all_songs(args.analysis_root, args.songs_root, args.device)


if __name__ == "__main__":
    raise SystemExit(main())
