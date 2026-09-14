"""Where this experiment reads and writes. Candidate producer for
`sections.json`'s `tension` field (docs/product-refinement-v3.6.md item
5/6). Reads only top-level published `data/analysis/{song}/*.json`
(`loudness.json`, `song_event_timeline.json`) plus segment spans from
`reference/human/segments.json` (falls back to `sections.json`), plus the
sibling `experiments/phrase_periodicity` experiment's own proposal output
(`reference/proposals/phrase_periodicity.json`) — a data dependency on a
file, not an import.
"""
from __future__ import annotations

import os
from pathlib import Path

from experiments.segment_seeds import features as seed_features

REPO_ROOT = Path(
    os.environ.get("TENSION_SHAPE_EXP_REPO", Path(__file__).resolve().parents[2])
)
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"

SONGS = [
    "ayuni",
    "Cinderella - Ella Lee",
    "_test_song",
    "What a Feeling - Courtney Storm",
    "Armin - Revolution",
]


def song_dir(song: str) -> Path:
    return ANALYSIS_ROOT / song


def segments_path(song: str) -> Path:
    return song_dir(song) / "reference" / "human" / "segments.json"


def sections_path(song: str) -> Path:
    return song_dir(song) / "sections.json"


def loudness_path(song: str) -> Path:
    return song_dir(song) / "loudness.json"


def song_event_timeline_path(song: str) -> Path:
    return song_dir(song) / "song_event_timeline.json"


def phrase_periodicity_path(song: str) -> Path:
    return song_dir(song) / "reference" / "proposals" / "phrase_periodicity.json"


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
    return song_dir(song) / "reference" / "proposals" / "tension_shape.json"


def out_file(name: str) -> Path:
    out = Path(__file__).resolve().parent / "out"
    out.mkdir(parents=True, exist_ok=True)
    return out / name
