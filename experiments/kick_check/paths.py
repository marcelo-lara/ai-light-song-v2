"""Where this experiment reads and writes. Reads: `artifacts/stems/drums.wav`
and top-level `drum_events.json` (every `kick` event to check — the only
field of that file this experiment trusts is `time`; `event_type` is exactly
what is being checked). Writes: `cache/<song>.json` and
`reference/proposals/kick_check.json`."""
from __future__ import annotations

from pathlib import Path

from experiments.drum_hit_shape import ANALYSIS_ROOT, all_songs, drum_events_path  # noqa: F401

CACHE_ROOT = Path(__file__).resolve().parent / "cache"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "kick_check.json"
