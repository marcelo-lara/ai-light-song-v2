"""Where this experiment reads and writes.

Independent of `src/analyzer` and of the sibling experiments' code. It does read
one sibling's *output* — `reference/proposals/allin1.json` supplies the section
boundaries CLAP embeddings are pooled inside — but that is a data dependency on
a file, not an import, so either experiment can be deleted without breaking the
other's code.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("CLAP_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

#: The four songs carrying hand-placed `drop impact` marks — seven impacts.
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]


def all_songs() -> list[str]:
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and (SONGS_ROOT / f"{p.name}.mp3").exists()
    )


def audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def allin1_path(song: str) -> Path:
    """The sibling experiment's proposal — the section boundaries to pool inside."""
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "allin1.json"


def shipped_sections_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "sections.json"


def human_hints_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.npz"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / "clap_identity.json"


def out_file(name: str) -> Path:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    return OUT_ROOT / name


def human_impacts(song: str) -> list[float]:
    path = human_hints_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return sorted(
        float(h["start_time"]) for h in payload.get("human_hints", [])
        if str(h.get("title", "")).strip().casefold() == "drop impact"
    )


def allin1_sections(song: str) -> list[dict]:
    """Merged allin1 sections, or [] when the sibling experiment has not run."""
    path = allin1_path(song)
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("sections", [])
