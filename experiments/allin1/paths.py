"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of the sibling
`experiments/drop_detection` package: an experiment that borrows another
experiment's plumbing cannot be deleted on its own.
"""
from __future__ import annotations

import os
from pathlib import Path

# Inside the sandbox image the repo is bind-mounted at /app and ./data at /data.
REPO_ROOT = Path(os.environ.get("ALLIN1_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The four songs carrying hand-placed `drop impact` marks — seven impacts total.
#: Everything scoreable in this experiment is scored against these and nothing else.
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]


def all_songs() -> list[str]:
    """Every analysed song that has stems — allin1 is seeded from them."""
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "stems" / "bass.wav").exists()
    )


def audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def stem_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / f"{stem}.wav"


def essentia_beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "beats.json"


def shipped_sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def human_hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def raw_cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    """The reviewable output — a proposal, never a deliverable (constitution §3.2)."""
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "allin1.json"


def out_file(name: str) -> Path:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    return OUT_ROOT / name
