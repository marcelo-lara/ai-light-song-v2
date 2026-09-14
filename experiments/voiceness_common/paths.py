"""Where this package reads from.

Deliberately independent of `src/analyzer` (`src/` never imports from
`experiments/`). `experiments/vocal_phrases` is imported directly from
`incumbents.py` — that is experiment-to-experiment, not `src/`-to-
`experiments/`, and is fine (docs/experiments.md sandbox rule only forbids the
other direction).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VOICENESS_COMMON_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"


def arrangement_state_path(song: str) -> Path:
    """Top-level published file — the shipped `vocals` claim being audited."""
    return ANALYSIS_ROOT / song / "arrangement_state.json"


def loudness_path(song: str) -> Path:
    """Top-level published per-stem RMS series."""
    return ANALYSIS_ROOT / song / "loudness.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def proposals_path(song: str, experiment_name: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / f"{experiment_name}.json"
