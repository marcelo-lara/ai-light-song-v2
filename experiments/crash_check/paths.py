"""Where this experiment reads and writes. Reads: `artifacts/stems/drums.wav`,
`beats.json` (song beat length) and top-level `drum_events.json` (every
`crash` event to check). Writes: `cache/<song>.json` and
`reference/proposals/crash_check.json`."""
from __future__ import annotations

from pathlib import Path

from experiments.drum_hit_shape import ANALYSIS_ROOT, all_songs, drum_events_path  # noqa: F401

CACHE_ROOT = Path(__file__).resolve().parent / "cache"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "crash_check.json"
