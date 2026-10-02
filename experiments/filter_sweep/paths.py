"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only: `artifacts/essentia/fft_bands.{harmonic,bass}.json` (the published
per-stem FFT bands), top-level `loudness.json` (per-stem loudness) and
`beats.json` (beat spacing -> bar length only; never downbeats/bar numbers).
Writes: `cache/<song>.json` and `reference/proposals/filter_sweep.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("FILTER_SWEEP_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

STEMS = ("harmonic", "bass")


def fft_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / f"fft_bands.{stem}.json"


def mix_fft_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "fft_bands.json"


def loudness_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "loudness.json"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def timeline_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "song_event_timeline.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "filter_sweep.json"


def all_songs() -> list[str]:
    """Every song that has the inputs (both stem FFTs, loudness, beats)."""
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir()
        and all(fft_path(p.name, s).exists() for s in STEMS)
        and (p / "loudness.json").exists()
        and (p / "beats.json").exists()
    )
