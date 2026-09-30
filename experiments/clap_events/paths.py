"""Where this experiment reads and writes. Reads: `artifacts/stems/drums.wav`
(the only input — never omnizart's `drum_events.json` label). Writes:
`cache/<song>.json` (this experiment's own per-candidate intermediate) and
`reference/proposals/clap_events.json`."""
from __future__ import annotations

from pathlib import Path

from experiments.drum_hit_shape import ANALYSIS_ROOT, all_songs  # noqa: F401 re-export

CACHE_ROOT = Path(__file__).resolve().parent / "cache"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "clap_events.json"
