"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only, from `data/analysis/<song>/`:

* top-level: `beats.json` (beat times, `off_grid_spans`, and allin1's downbeat
  phase `type` / `downbeat_confidence` — used ONLY as the fallback where no
  anchor reaches, and as the incumbent being scored);
* the phrases experiment's proposals, as data: `reference/proposals/phrases.json`;
* baseline only: `artifacts/essentia/fft_bands.drums.json`;
* scoring only: `reference/moises/{beats,chords}.json`.

Writes: `reference/proposals/downbeat_anchors.json` and `out/score.txt`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("DOWNBEAT_ANCHORS_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
OUT_ROOT = Path(__file__).resolve().parent / "out"


def _song(song: str) -> Path:
    return ANALYSIS_ROOT / song


def beats_path(song: str) -> Path:
    return _song(song) / "beats.json"


def phrases_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "phrases.json"


def drums_fft_path(song: str) -> Path:
    return _song(song) / "artifacts" / "essentia" / "fft_bands.drums.json"


def moises_beats_path(song: str) -> Path:
    return _song(song) / "reference" / "moises" / "beats.json"


def moises_chords_path(song: str) -> Path:
    return _song(song) / "reference" / "moises" / "chords.json"


def proposals_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "downbeat_anchors.json"


def all_songs() -> list[str]:
    """Every song with beats.json and the phrases proposals."""
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and beats_path(p.name).exists() and phrases_path(p.name).exists()
    )


def scored_songs() -> list[str]:
    return [s for s in all_songs() if moises_beats_path(s).exists() and moises_chords_path(s).exists()]


CACHE_ROOT = Path(__file__).resolve().parent / "cache"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"
