"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). All reads
are of committed cache under `cache/` or of `data/analysis/**` (gitignored) —
`compute` re-derives the cache from `data/analysis/**` (including items 6 and 7's
`reference/proposals/` outputs — it READS them, it does not import their code);
`score` and `export` touch only the cache, so the tables reproduce on a checkout
with no `data/` and no audio.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(
    os.environ.get("STRUCTURAL_VS_MICRO_EXP_REPO", Path(__file__).resolve().parents[2])
)
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: the four hand-labelled gold songs (docs/experiments.md "Run against the four
#: gold songs"). The per-kind agreement metric is measured on these.
GOLD_SONGS = [
    "_test_song",
    "Titanium - David Guetta ft Sia",
    "Hideaway - Kiesza",
    "Armin - Revolution",
]

#: Queen of Kings carries the operator's richest micro/structural marking — the
#: 6-of-16 edge-lock table (refinement doc item 4) is reproduced from it. Not in
#: the F1 metric.
EXTRA_SONGS = ["Queen of Kings - Alessandra"]

SONGS = GOLD_SONGS + EXTRA_SONGS

PHRASE_BARS = 4


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def texture_novelty_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "texture_novelty.json"


def phrase_periodicity_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "phrase_periodicity.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.npz"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "structural_vs_micro.json"
