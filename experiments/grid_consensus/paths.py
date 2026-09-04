"""Where this experiment reads and writes. Reads other experiments'
*cached outputs*, not their code — a data dependency, not an import, so any
one of these can be deleted without breaking the others (matches the pattern
already established by experiments/clap reading experiments/allin1's output).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("GRID_CONSENSUS_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
EXPERIMENTS_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = Path(__file__).resolve().parent / "out"

GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]


def all_songs() -> list[str]:
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (ANALYSIS_ROOT / p.name / "beats.json").exists()
    )


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def allin1_cache_path(song: str) -> Path:
    return EXPERIMENTS_ROOT / "allin1" / "cache" / f"{song}.json"


def beatthis_cache_path(song: str) -> Path:
    return EXPERIMENTS_ROOT / "drop_detection" / "research" / "cache" / "beatthis" / f"{song}.npz"


def drum_events_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "symbolic_transcription" / "drum_events.json"


def sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def gestures_proposal_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "gestures.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def allin1_transitions_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "allin1.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "grid.json"
