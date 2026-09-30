"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads:
top-level `loudness.json` / `beats.json` / `info.json` (the only inputs the
state machine itself uses); `artifacts/allin1/raw.json` and top-level
`arrangement_state.json`, read-only, as scoring incumbents; and
`reference/human/segments.json`, read-only, via `truth_common.structure`.
Writes: `cache/<song>.json` (this experiment's own per-bar intermediate) and
`reference/proposals/stem_presence_sections.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(
    os.environ.get("STEM_PRESENCE_SECTIONS_EXP_REPO", Path(__file__).resolve().parents[2])
)
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

STEM_IDS = ("bass", "drums", "harmonic", "vocals")


def all_songs() -> list[str]:
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "loudness.json").exists() and (p / "beats.json").exists()
    )


def loudness_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "loudness.json"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def info_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "info.json"


def allin1_raw_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "allin1" / "raw.json"


def arrangement_state_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "arrangement_state.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "stem_presence_sections.json"
