"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). All reads
are of committed cache under `cache/` or of `data/analysis/**` (gitignored) —
`compute` re-derives the cache from `data/analysis/**`; `score` and `export`
touch only the cache, so the tables reproduce on a checkout with no `data/` and
no audio.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(
    os.environ.get("PHRASE_PERIODICITY_EXP_REPO", Path(__file__).resolve().parents[2])
)
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: the four hand-labelled gold songs (docs/experiments.md "Run against the four
#: gold songs").
GOLD_SONGS = [
    "_test_song",
    "Titanium - David Guetta ft Sia",
    "Hideaway - Kiesza",
    "Armin - Revolution",
]

#: operator-truth songs the plan names for phrase length / regime. `Chimera`'s
#: bass repeats every 8 bars "almost exact"; `Queen of Kings`'s blocks are the
#: marked regime ground truth (refinement doc item 3).
EXTRA_SONGS = [
    "Chimera - Hana",
    "Queen of Kings - Alessandra",
]

SONGS = GOLD_SONGS + EXTRA_SONGS

#: loudness.json per-stem RMS order after `mix`.
STEM_IDS = ("bass", "drums", "harmonic", "vocals")


def loudness_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "loudness.json"


def fft_bands_stem_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / f"fft_bands.{stem}.json"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.npz"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "phrase_periodicity.json"
