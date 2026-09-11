"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of sibling `experiments/`
packages other than `voiceness_common` (shared scoring scaffolding, imported
the same way `vocal_voiceness` etc. do). Never writes under
`data/analysis/*/artifacts/stems/` — variant stems are cached entirely under
this experiment's own `cache/`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("DEMUCS_ABLATION_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

VARIANTS = ("htdemucs", "htdemucs_ft", "htdemucs_6s")

#: The four gold songs + `ayuni` (the song that surfaced the false-vocal
#: question). Item 1's "second leaky track" is left out here — the operator
#: had not named or marked one at the time this item ran; see README.md.
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]
SCORING_CORPUS = GOLD_SONGS + ["ayuni"]


def song_audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def stems_dir(song: str, variant: str) -> Path:
    return CACHE_ROOT / song.replace("/", "_") / variant


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def score_out_path() -> Path:
    return OUT_ROOT / "score.json"
