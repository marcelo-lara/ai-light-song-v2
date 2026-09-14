"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). All reads
are of committed cache under `cache/` or of `data/analysis/**` (gitignored) —
`compute` re-derives the cache from `data/analysis/**`, `score` and `export`
touch only the cache.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("TEXTURE_NOVELTY_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
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

STEM_IDS = ("bass", "drums", "harmonic", "vocals")


def all_songs() -> list[str]:
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "essentia" / "fft_bands.json").exists()
    )


def mix_audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def fft_bands_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "fft_bands.json"


def fft_bands_stem_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / f"fft_bands.{stem}.json"


def hpcp_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "hpcp.json"


def loudness_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "loudness.json"


def sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def arrangement_state_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "arrangement_state.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.npz"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "texture_novelty.json"
