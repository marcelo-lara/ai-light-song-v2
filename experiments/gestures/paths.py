"""Where this experiment reads and writes."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("GESTURES_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"

GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]

OUT_ROOT = Path(__file__).resolve().parent / "out"


def all_songs() -> list[str]:
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "essentia" / "fft_bands.json").exists()
    )


def fft_bands_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "fft_bands.json"


def rms_loudness_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "rms_loudness.json"


def drum_events_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "symbolic_transcription" / "drum_events.json"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def event_timeline_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "song_event_timeline.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "gestures.json"
