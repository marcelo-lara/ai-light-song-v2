"""Where this experiment reads and writes.

Deliberately independent of `src/analyzer` and of sibling `experiments/`
packages other than `voiceness_common` and `whisperx_vad` (both imported
directly — experiment-to-experiment is fine; the forbidden direction is
`src/` importing `experiments/`). `whisperx_vad`'s cache is read, never
recomputed — this experiment reuses its per-song `.npz` VAD activation
(`docs/experiments.md` "Singer Identity" — "reuse whisperx_vad's cached
activation"). Owns its own cache directory under `cache/`, one `.npz` per
song holding the embedded windows, their cluster assignments and the chosen
k.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("SINGER_IDENTITY_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The only three songs in this environment carrying three-class vocal
#: ground truth (`experiments/voiceness_common/vocal_ground_truth.json`) —
#: matches the spec's own scoring corpus for output 1, not the item 4-7
#: family's four-gold-song `GOLD_SONGS` (none of which have entries in that
#: map).
SCORING_CORPUS = ["ayuni", "Cinderella - Ella Lee", "Armin - Revolution"]

#: The one marked singer change in the corpus (`docs/experiments.md`,
#: "Scoring" — Armin - Revolution's male -> female handoff), for output 2.
ARMIN_SINGER_CHANGE_SONG = "Armin - Revolution"


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


def whisperx_vad_cache_path(song: str) -> Path:
    """`whisperx_vad`'s own cache — read-only, never recomputed here."""
    from experiments.whisperx_vad import paths as whisperx_vad_paths

    return whisperx_vad_paths.cache_path(song)


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.npz"


def proposal_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "singer_identity.json"


def score_out_path() -> Path:
    return OUT_ROOT / "score.txt"


def singer_ground_truth_path() -> Path:
    """Operator-declared `lead_voices`/`extra_speech` map — see the file's
    own `_note`. Read-only; never written by any stage."""
    return Path(__file__).resolve().parent / "singer_ground_truth.json"


def singer_count_report_path() -> Path:
    return OUT_ROOT / "singer_count_calibration.txt"
