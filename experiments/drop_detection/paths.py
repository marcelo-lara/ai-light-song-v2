from __future__ import annotations

import os
from pathlib import Path

# Inside the container the repo is at /app and ./data is bind-mounted at /app/data.
REPO_ROOT = Path(os.environ.get("DROP_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"

GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]


def all_songs() -> list[str]:
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "stems" / "bass.wav").exists()
    )


def stem_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / f"{stem}.wav"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "beats.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def cache_path(song: str) -> Path:
    safe = song.replace("/", "_")
    return CACHE_ROOT / f"{safe}.npz"
