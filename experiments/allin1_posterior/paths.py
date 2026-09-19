"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of sibling `experiments/`
packages — reads only the already-committed `artifacts/allin1/raw.json` cache
and the already-published `sections.json`/`human_hints.json`, no model run.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("ALLIN1_POSTERIOR_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The four songs carrying hand-placed ground truth.
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]


def allin1_raw_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "allin1" / "raw.json"


def sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "allin1_posterior.json"


def all_songs() -> list[str]:
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir() if p.is_dir() and allin1_raw_path(p.name).exists()
    )
