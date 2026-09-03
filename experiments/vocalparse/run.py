"""CLI for the VocalParse experiment.

    # GPU steps — need the sandbox image (see run_in_container.sh)
    ./experiments/vocalparse/run_in_container.sh python -m experiments.vocalparse.run cache-baseline
    ./experiments/vocalparse/run_in_container.sh python -m experiments.vocalparse.run cache

    # these read the caches, no GPU
    python -m experiments.vocalparse.run export
    python -m experiments.vocalparse.run score

Commands
    cache-baseline  whisper-large-v3 word timestamps over the vocal stems
    cache           VocalParse raw transcription per song
    export          write the vocalparse + baseline rows into
                    reference/proposals/vocal_transcription.json
    score           lyric WER + word-onset MAE vs reference/moises
"""
from __future__ import annotations

import sys

from . import export, model, score, whisper_baseline
from .paths import all_songs, out_file


def _songs(argv: list[str]) -> list[str]:
    return [a for a in argv if not a.startswith("--")] or all_songs()


def cmd_cache_baseline(argv: list[str]) -> int:
    failed = []
    for song in _songs(argv):
        try:
            data = whisper_baseline.load(song, rebuild="--rebuild" in argv)
            print(f"  whisper  {song:<40} {len(data['lines']):4d} lines  ({data['language']})", flush=True)
        except Exception as exc:  # noqa: BLE001 — sandbox script
            failed.append(song)
            print(f"  FAIL     {song:<40} {type(exc).__name__}: {exc}"[:200], flush=True)
    return 1 if failed else 0


def cmd_cache(argv: list[str]) -> int:
    failed = []
    for song in _songs(argv):
        try:
            data = model.load(song, rebuild="--rebuild" in argv)
            print(f"  vocalparse  {song:<40} {len(data.get('syllables', []))} syllables  bpm={data.get('bpm')}", flush=True)
        except Exception as exc:  # noqa: BLE001
            failed.append(song)
            print(f"  FAIL        {song:<40} {type(exc).__name__}: {exc}"[:200], flush=True)
    return 1 if failed else 0


def cmd_export(argv: list[str]) -> int:
    songs = [s for s in _songs(argv) if s in model.cached_songs([s])]
    if not songs:
        print("No cached VocalParse output. Run `cache` in the sandbox image first.")
        return 1
    for song in songs:
        print(export.summary_line(song, export.export_song(song)))
    print(f"\nWrote {len(songs)} file(s) to reference/proposals/vocal_transcription.json")
    return 0


def cmd_score(argv: list[str]) -> int:
    text = score.report(_songs(argv) if argv and not argv[0].startswith("--") else score.default_songs())
    print(text)
    out_file("score.txt").write_text(text + "\n")
    print(f"\n(also written to {out_file('score.txt')})")
    return 0


COMMANDS = {
    "cache-baseline": cmd_cache_baseline,
    "cache": cmd_cache,
    "export": cmd_export,
    "score": cmd_score,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 1
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
