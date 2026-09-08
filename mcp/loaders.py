"""Song discovery and top-level file access for the `mcp/` server.

This module is the *only* place the server touches the filesystem. It is written
so that no code path can descend into a song's inner folders (the raw-material
directories that phase 4 builds the top-level files from) — the server reads
top-level ``data/analysis/<song>/*.json`` and nothing else.
``mcp/tests/test_exposure.py`` greps this module for the two inner-folder path
fragments and fails on any hit; keep it clean.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_ANALYSIS_ROOT = Path("/data/analysis")

# Top-level files an analysed song must carry for the server to describe it.
# Deliberately short: these are the files the pipeline publishes at top level
# today. Signals still being migrated out of inner folders (genre, loudness,
# drum events) are not required here yet — that is later v3.1 plan work. A song
# missing one of these gets an explicit error, never a partial response.
REQUIRED_TOP_LEVEL_FILES: tuple[str, ...] = (
    "info.json",
    "beats.json",
    "sections.json",
    "song_event_timeline.json",
    "hints.json",
    "drum_events.json",
)


class SongNotFoundError(Exception):
    """Raised when a requested song directory does not exist."""


class MissingTopLevelFileError(Exception):
    """Raised when a song directory is missing a required top-level file."""


def get_analysis_root() -> Path:
    """The directory that holds one subdirectory per analysed song.

    `MCP_ANALYSIS_ROOT` overrides the default so the regression suite can point
    the server at its committed fixtures instead of a local pipeline run.
    """
    configured = os.environ.get("MCP_ANALYSIS_ROOT")
    return Path(configured) if configured else DEFAULT_ANALYSIS_ROOT


def _safe_top_level_name(filename: str) -> None:
    """Reject anything that is not a bare top-level `*.json` filename.

    No path separators, no parent refs, no reaching into inner folders. This is
    the structural guard behind the exposure rule.
    """
    if filename != Path(filename).name or filename in {"", ".", ".."}:
        raise ValueError(f"Not a top-level filename: {filename!r}")
    if not filename.endswith(".json"):
        raise ValueError(f"Not a JSON file: {filename!r}")


def resolve_song_dir(song_name: str, root: str | Path | None = None) -> Path:
    """Resolve a song by directory name and verify its required top-level files.

    Raises `SongNotFoundError` if the directory is absent and
    `MissingTopLevelFileError` (naming the file) if a required file is missing.
    """
    analysis_root = Path(root) if root is not None else get_analysis_root()
    song_dir = analysis_root / song_name

    if not song_dir.is_dir():
        # Name only — never the resolved absolute path, which must not cross to a
        # caller (see docs/mcp-definition.md: no delivery-surface host paths).
        raise SongNotFoundError(
            f"Unknown song: {song_name!r} — no such directory under the analysis root"
        )

    for required in REQUIRED_TOP_LEVEL_FILES:
        if not (song_dir / required).is_file():
            raise MissingTopLevelFileError(
                f"{song_name!r} is missing a required top-level file: {required}"
            )

    return song_dir


def load_top_level_json(song_dir: Path, filename: str) -> Any:
    """Load one top-level JSON file from a resolved song directory.

    `filename` must be a bare `*.json` name; the guard forbids any path that
    could reach an inner folder.
    """
    _safe_top_level_name(filename)
    path = song_dir / filename
    if path.parent != song_dir or not path.is_file():
        raise FileNotFoundError(f"No top-level file {filename} in {song_dir}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def list_songs(root: str | Path | None = None) -> list[dict[str, Any]]:
    """Every analysable song directory with `song_name`, `bpm` and `duration`.

    A directory counts as a song if it has an `info.json`. Values are read
    straight from that file — a missing field surfaces as `null`, never an
    invented default. An analysis root that does not exist yet returns `[]`.
    """
    analysis_root = Path(root) if root is not None else get_analysis_root()
    songs: list[dict[str, Any]] = []

    if not analysis_root.is_dir():
        return songs

    for song_dir in sorted(
        (p for p in analysis_root.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    ):
        info_path = song_dir / "info.json"
        if not info_path.is_file():
            continue
        with info_path.open("r", encoding="utf-8") as handle:
            info = json.load(handle)
        songs.append(
            {
                "song_name": info.get("song_name"),
                "bpm": info.get("bpm"),
                "duration": info.get("duration"),
            }
        )

    return songs
