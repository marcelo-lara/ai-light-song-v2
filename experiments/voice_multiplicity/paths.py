"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). All reads
are of committed cache under `cache/` or of `data/analysis/**` (gitignored) —
`compute` re-derives the cache from `data/analysis/**`, `score` and `export`
touch only the cache.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VOICE_MULTIPLICITY_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: the four hand-labelled gold songs (docs/experiments.md "Run against the four
#: gold songs"). Ground truth for every number this experiment reports.
GOLD_SONGS = [
    "_test_song",
    "Titanium - David Guetta ft Sia",
    "Hideaway - Kiesza",
    "Armin - Revolution",
]


def all_songs() -> list[str]:
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "stems" / "vocals.wav").exists()
    )


def vocals_stem_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / "vocals.wav"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "voice_multiplicity.json"
