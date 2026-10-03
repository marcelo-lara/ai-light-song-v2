"""Where this experiment reads and writes.

`src/` never imports this package. Reads: `reference/proposals/bar_features.json`
(item 1's table — the detector's only musical input), plus the per-stem FFT
bands for the `texture_novelty` signal. Writes: `cache/<song>.json` and
`reference/proposals/light_changes.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("LIGHT_CHANGES_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

STEMS = ("bass", "drums", "harmonic", "vocals")


def bar_features_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "bar_features.json"


def fft_stem_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / f"fft_bands.{stem}.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "light_changes.json"


def all_songs() -> list[str]:
    return sorted(p.name for p in ANALYSIS_ROOT.iterdir() if p.is_dir() and bar_features_path(p.name).exists())
