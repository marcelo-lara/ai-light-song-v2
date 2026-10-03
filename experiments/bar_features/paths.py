"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only, existing analysis data only: top-level `beats.json`, `loudness.json`,
`drum_events.json`, `arrangement_state.json`, `song_event_timeline.json`;
`artifacts/essentia/fft_bands{,.<stem>}.json`; `reference/proposals/filter_sweep.json`, `reference/proposals/kick_attacks.json`.
Writes: `cache/<song>.json` and `reference/proposals/bar_features.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("BAR_FEATURES_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"

SOURCES = ("mix", "bass", "drums", "harmonic", "vocals")  # == loudness.json source_order


def song_dir(song: str) -> Path:
    return ANALYSIS_ROOT / song


def fft_path(song: str, source: str) -> Path:
    name = "fft_bands.json" if source == "mix" else f"fft_bands.{source}.json"
    return song_dir(song) / "artifacts" / "essentia" / name


def top_path(song: str, name: str) -> Path:
    return song_dir(song) / name


def filter_sweep_path(song: str) -> Path:
    return song_dir(song) / "reference" / "proposals" / "filter_sweep.json"


def kick_attacks_path(song: str) -> Path:
    return song_dir(song) / "reference" / "proposals" / "kick_attacks.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return song_dir(song) / "reference" / "proposals" / "bar_features.json"


def all_songs() -> list[str]:
    return sorted(p.name for p in ANALYSIS_ROOT.iterdir() if p.is_dir() and (p / "beats.json").exists())
