"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of sibling `experiments/`
packages other than `voiceness_common` and `vocal_phrases` (both imported
directly — experiment-to-experiment is fine; the forbidden direction is
`src/` importing `experiments/`).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VOCAL_VOICENESS_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The four songs carrying hand-placed ground truth, matching every sibling
#: voiceness experiment (item 2's corpus) — the only songs a measured
#: comparison against the incumbents means anything for once ground truth
#: exists.
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]

#: `ayuni` is the song that surfaced the false-vocal question this item chases
#: (refinement doc: `arrangement_state.json` reports `vocals` 40.8% of the
#: song). Scoring corpus = gold songs + ayuni, matching demucs_ablation's
#: convention.
SCORING_CORPUS = GOLD_SONGS + ["ayuni"]


def vocals_stem_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / "vocals.wav"


def fft_bands_vocals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "essentia" / "fft_bands.vocals.json"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def proposal_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "vocal_voiceness.json"


def score_out_path() -> Path:
    return OUT_ROOT / "score.txt"
