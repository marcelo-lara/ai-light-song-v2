"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only: the mix audio `data/songs/<song>.mp3`, top-level `beats.json` (grid
for the off-grid rule) and `drum_events.json` (only scored against, never an
input to detection). Writes: `cache/<song>.json`, `out/score.txt` and
`reference/proposals/kick_attacks.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("KICK_ATTACKS_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"


def mix_audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def beats_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "beats.json"


def drum_events_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "drum_events.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "kick_attacks.json"


def all_songs() -> list[str]:
    return sorted(p.name for p in ANALYSIS_ROOT.iterdir()
                  if p.is_dir() and (p / "beats.json").exists() and mix_audio_path(p.name).exists())
