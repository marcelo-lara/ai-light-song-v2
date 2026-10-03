"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only: `artifacts/stems/harmonic.wav` (audio), top-level `beats.json`
(half-beat grid, bar numbers, off-grid spans). The aftermath classifier reads
`experiments/bar_features`' table, never a file of its own. Writes:
`cache/<song>.json`, `out/score.txt` and `reference/proposals/filter_sweep_v2.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("FILTER_SWEEP_V2_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"


def harmonic_wav_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / "harmonic.wav"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "filter_sweep_v2.json"


def all_songs() -> list[str]:
    return sorted(p.name for p in ANALYSIS_ROOT.iterdir()
                  if p.is_dir() and (p / "beats.json").exists() and harmonic_wav_path(p.name).exists())
