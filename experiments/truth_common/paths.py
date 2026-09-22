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


def block_reviews_path(song: str) -> Path:
    """v3.7 item 1 — the operator's per-block verdict file
    (`docs/product-refinement-v3.7.md` item 1). The only `reference/human/`
    tier `block_reviews.py` reads."""
    return reference_path(song, "human", "block_reviews.json")


def gestures_timeline_path(song: str) -> Path:
    """`artifacts/gestures/song_event_timeline.json` — the pre-trim gesture
    events artifact (not `reference/`), used only to read the CURRENT run's
    block starts for the `gestures` lane's staleness match."""
    return ANALYSIS_ROOT / song / "artifacts" / "gestures" / "song_event_timeline.json"


def proposals_path(song: str, filename: str) -> Path:
    """`reference/proposals/{filename}` — an experiment's own candidate
    output. Read-only here: used by `adapters.py` to score a sibling
    experiment's existing proposal file through this family's scorer,
    without changing that experiment."""
    return reference_path(song, "proposals", filename)
