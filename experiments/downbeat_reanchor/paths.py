"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only, from `data/analysis/<song>/`:

* top-level: `beats.json` (beat times, `off_grid_spans`, allin1 phase as the
  last-resort fallback and as the incumbent being scored), `song_event_timeline.json`
  (impacts), `arrangement_state.json` (bass/drums entries);
* `reference/proposals/kick_attacks.json` (v3.12 item 29);
* scoring only: `reference/moises/{beats,chords}.json`.

Writes: `reference/proposals/downbeat_reanchor.json` and `out/score.txt`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("DOWNBEAT_REANCHOR_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
OUT_ROOT = Path(__file__).resolve().parent / "out"


def _song(song: str) -> Path:
    return ANALYSIS_ROOT / song


def beats_path(song: str) -> Path:
    return _song(song) / "beats.json"


def timeline_path(song: str) -> Path:
    return _song(song) / "song_event_timeline.json"


def arrangement_path(song: str) -> Path:
    return _song(song) / "arrangement_state.json"


def kick_attacks_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "kick_attacks.json"


def moises_beats_path(song: str) -> Path:
    return _song(song) / "reference" / "moises" / "beats.json"


def moises_chords_path(song: str) -> Path:
    return _song(song) / "reference" / "moises" / "chords.json"


def proposals_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "downbeat_reanchor.json"


def all_songs() -> list[str]:
    """Every song with beats.json and the kick-attacks proposals."""
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and beats_path(p.name).exists() and kick_attacks_path(p.name).exists()
    )


def scored_songs() -> list[str]:
    return [s for s in all_songs() if moises_beats_path(s).exists() and moises_chords_path(s).exists()]
