"""Where every `truth_common` family reads from.

All truth lives under `reference/human/` (operator-authored) or
`reference/moises/` — and, for `moises`, only rows whose `confidence` is
exactly `"0.99"` count as truth (`docs/archive` convention: Moises inference
below that confidence is not curated). Deliberately independent of
`src/analyzer` — `src/` never imports from `experiments/`
(`docs/experiments.md` sandbox rule).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("TRUTH_COMMON_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"


def reference_path(song: str, producer: str, filename: str) -> Path:
    """`data/analysis/{song}/reference/{producer}/{filename}` — the only
    tier `truth_common` reads (`reference/`, never `artifacts/` — those hold
    candidate producer output, read by each experiment itself, not by the
    scorer)."""
    return ANALYSIS_ROOT / song / "reference" / producer / filename


def human_hints_path(song: str) -> Path:
    return reference_path(song, "human", "human_hints.json")


def human_segments_path(song: str) -> Path:
    return reference_path(song, "human", "segments.json")


def human_segments_seed_path(song: str) -> Path:
    """Written by plan item 4 — does not exist yet. Callers must handle
    absence gracefully (no seed rows available), never crash and never
    silently substitute a guess."""
    return reference_path(song, "human", "segments.seed.json")


def human_lyrics_path(song: str) -> Path:
    return reference_path(song, "human", "lyrics.json")


def moises_lyrics_path(song: str) -> Path:
    return reference_path(song, "moises", "lyrics.json")
