"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of the sibling `experiments/`
packages: an experiment that borrows another experiment's plumbing cannot be
deleted on its own.
"""
from __future__ import annotations

import os
from pathlib import Path

# Inside the app sandbox the repo is bind-mounted at /app and ./data at /data.
REPO_ROOT = Path(os.environ.get("ARRANGEMENT_STATE_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The four songs carrying hand-placed ground truth — the only place a measured
#: comparison against the incumbent and a baseline means anything.
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
        if p.is_dir() and (p / "loudness.json").exists()
    )


def loudness_path(song: str) -> Path:
    """The *published* per-stem RMS series — top level, not `artifacts/`.

    Reading the delivery surface rather than the artifact is the point: it
    proves a phase-3 stage could produce this without touching audio.
    """
    return ANALYSIS_ROOT / song / "loudness.json"


def shipped_sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "arrangement_state.json"


def character_proposal_path(song: str) -> Path:
    """The CLAP character-block proposal (`experiments/clap`), read-only here."""
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "character.json"
