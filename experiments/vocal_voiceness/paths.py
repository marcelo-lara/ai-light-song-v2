"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of sibling `experiments/`
packages other than `voiceness_common` and `vocal_phrases` (both imported
directly — experiment-to-experiment is fine; the forbidden direction is
`src/` importing `experiments/`).
"""
from __future__ import annotations

import os
from pathlib import Path

from experiments.voiceness_common.scorer import scoreable_songs

REPO_ROOT = Path(os.environ.get("VOCAL_VOICENESS_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: Songs whose vocal ground truth is fully declared in
#: `voiceness_common/vocal_ground_truth.json` — shared by every voiceness sibling.
SCORING_CORPUS = scoreable_songs()


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
