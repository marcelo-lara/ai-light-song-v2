"""Where this experiment reads and writes.

Reads only top-level published `data/analysis/{song}/*.json` (never
`artifacts/`) plus, for spans, `reference/human/segments.json` when present.
Writes only `reference/human/segments.seed.json` — the one file this
experiment is allowed to put under `reference/human/`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(
    os.environ.get("SEGMENT_SEEDS_EXP_REPO", Path(__file__).resolve().parents[2])
)
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"

#: refinement item 6 "Seeds first" — the four segment songs.
SONGS = [
    "ayuni",
    "Cinderella - Ella Lee",
    "_test_song",
    "What a Feeling - Courtney Storm",
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


def drum_events_path(song: str) -> Path:
    return song_dir(song) / "drum_events.json"


def beats_path(song: str) -> Path:
    return song_dir(song) / "beats.json"


def song_event_timeline_path(song: str) -> Path:
    return song_dir(song) / "song_event_timeline.json"


def seed_out_path(song: str) -> Path:
    return song_dir(song) / "reference" / "human" / "segments.seed.json"
