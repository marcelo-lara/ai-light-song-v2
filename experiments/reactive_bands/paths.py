"""Where this experiment reads and writes."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("REACTIVE_BANDS_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]

#: source id -> audio path resolver. "mix" reads the original song file; the
#: rest read the trusted demucs stems, matching `rms_loudness.json`'s sources.
STEM_IDS = ("bass", "drums", "harmonic", "vocals")


def all_songs() -> list[str]:
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "stems" / "bass.wav").exists()
    )


def mix_audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def stem_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / f"{stem}.wav"


def source_audio_path(song: str, source: str) -> Path:
    return mix_audio_path(song) if source == "mix" else stem_path(song, source)


def fft_bands_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "fft_bands.json"


def rms_loudness_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "rms_loudness.json"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def cache_path(song: str, source: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}__{source}.npz"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "reactive_bands.json"
