"""Where this experiment reads and writes. Candidate producer for
`rhythm.{drums,bass,harmonic,vocals}` (docs/product-refinement-v3.6.md item
5/6b): sub-beat autocorrelation of per-stem 20 ms loudness. Reads only
top-level published `data/analysis/{song}/*.json` (`loudness.json`,
`arrangement_state.json`, `beats.json`) plus segment spans from
`reference/human/segments.json` (falls back to `sections.json`).
"""
from __future__ import annotations

import os
from pathlib import Path

from experiments.segment_seeds import features as seed_features

REPO_ROOT = Path(
    os.environ.get("RHYTHM_STEM_AUTOCORR_EXP_REPO", Path(__file__).resolve().parents[2])
)
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"

SONGS = [
    "ayuni",
    "Cinderella - Ella Lee",
    "_test_song",
    "What a Feeling - Courtney Storm",
    "Armin - Revolution",
]

#: loudness.json / arrangement_state.json stem order after `mix`.
STEM_IDS = ("bass", "drums", "harmonic", "vocals")


def song_dir(song: str) -> Path:
    return ANALYSIS_ROOT / song


def segments_path(song: str) -> Path:
    return song_dir(song) / "reference" / "human" / "segments.json"


def sections_path(song: str) -> Path:
    return song_dir(song) / "sections.json"


def loudness_path(song: str) -> Path:
    return song_dir(song) / "loudness.json"


def arrangement_state_path(song: str) -> Path:
    return song_dir(song) / "arrangement_state.json"


def beats_path(song: str) -> Path:
    return song_dir(song) / "beats.json"


def spans(song: str) -> list[dict]:
    seg = seed_features.load_json(segments_path(song))
    if isinstance(seg, list) and seg:
        return [{"start": float(s["start"]), "end": float(s["end"])} for s in seg]
    sec = seed_features.load_json(sections_path(song)) or {}
    return [
        {"start": float(s["start"]), "end": float(s["end"])}
        for s in sec.get("sections", [])
    ]


def cache_path(song: str) -> Path:
    return Path(__file__).resolve().parent / "cache" / f"{song.replace('/', '_')}.json"


def proposals_path(song: str) -> Path:
    return song_dir(song) / "reference" / "proposals" / "rhythm_stem_autocorr.json"


def out_file(name: str) -> Path:
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(parents=True, exist_ok=True)
    return out / name
