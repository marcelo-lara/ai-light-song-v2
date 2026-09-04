"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of the sibling `experiments/`
packages: an experiment that borrows another experiment's plumbing cannot be
deleted on its own.
"""
from __future__ import annotations

import os
from pathlib import Path

# Inside the app sandbox the repo is bind-mounted at /app and ./data at /data.
REPO_ROOT = Path(os.environ.get("VOCAL_PHRASES_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The four songs carrying hand-placed ground truth — the only ones a measured
#: comparison against the incumbent and a baseline means anything (constitution
#: §3.5).
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]

#: Only `_test_song`'s Moises transcript has genuine word-level timing (rebuilt
#: 2026-09-04). The other three gold songs' last-word-per-line offsets are
#: lumped across the following instrumental and are not usable ground truth for
#: phrase *offsets* — see this experiment's README.
WORD_LEVEL_LYRICS_SONG = "_test_song"


def all_songs() -> list[str]:
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "stems" / "vocals.wav").exists()
    )


def vocals_stem_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / "vocals.wav"


def mix_audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def rms_loudness_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "rms_loudness.json"


def shipped_sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def lyrics_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "moises" / "lyrics.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "vocal_phrases.json"
