"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of sibling `experiments/`
packages other than `voiceness_common` (imported directly — experiment-to-
experiment is fine; the forbidden direction is `src/` importing
`experiments/`). Owns its own cache directory under `cache/`, one `.npz` per
song holding the VAD span series.

Single producer, single channel: unlike `svd_tagger` (item 6), this
candidate runs the VAD front-end over the vocal stem only, so there is no
`channel` axis to fuse — same shape as `vocal_voiceness` (item 4) and
`clap_voiceness` (item 5).
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("WHISPERX_VAD_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The four songs carrying hand-placed ground truth, matching every sibling
#: voiceness experiment (item 2's corpus).
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]

#: `ayuni` is the song that surfaced the false-vocal question this family of
#: items chases (refinement doc: `arrangement_state.json` reports `vocals`
#: present 40.8% of `ayuni`). Matches items 3-6's scoring corpus.
SCORING_CORPUS = GOLD_SONGS + ["ayuni"]


def all_analysed_songs() -> list[str]:
    """Every song that has been through the pipeline at all (has a vocal
    stem), for `--all` — not restricted to the scoring corpus."""
    return sorted(
        p.name
        for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (p / "artifacts" / "stems" / "vocals.wav").exists()
    )


def vocals_stem_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / "vocals.wav"


def hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.npz"


def proposal_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "whisperx_vad.json"


def score_out_path() -> Path:
    return OUT_ROOT / "score.txt"
