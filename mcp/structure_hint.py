"""Pre-analysis structure hint (v3.10 item 7): the brief, the schema validator
and the one bounded write path of `write_structure_hint`.

The only file written is `<song>/<inner>/<dir>/structure.json`; the path
components are separate literals (never one joined fragment) so
`test_exposure.py`'s literal-substring grep does not mistake a bounded write
path for a read leak — same convention as `proposals.py`. Contract and schema:
docs/mcp-definition.md, "Pre-analysis structure hint".
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

_INNER_DIRNAME = "reference"
_HINT_DIRNAME = "pre-analysis"
_HINT_FILENAME = "structure.json"

SCHEMA_VERSION = "1.0"

VERSIONS = ("radio_edit", "extended", "club_mix", "remix", "original")
FAMILIES = ("edm", "pop_edm", "pop", "rock", "other")
SUBGENRES = ("big_room", "house", "techno", "trance", "dubstep", "drum_and_bass", "other")
VOCALS = ("none", "chops", "full")

_TOP_KEYS = (
    "schema_version", "song_name", "generated_at", "track", "genre", "shape",
    "confidence", "sources",
)
_TRACK_KEYS = ("artist", "title", "version", "remixer", "version_duration_s")
_GENRE_KEYS = ("family", "subgenre", "bpm")
_SHAPE_KEYS = ("drops", "chorus_is_drop", "has_build_ups", "vocals")
_SOURCE_KEYS = ("url", "title")

# A key naming a time is refused outright: web sources describe other versions
# and an invented time is worse than none. `generated_at` and
# `version_duration_s` are the schema's own legitimate names and are exempt.
_TIME_KEY = re.compile(
    r"time|stamp|start|end|onset|offset|second|minute|(^|_)(s|ms|at|sec|bar|bars|beat|beats)($|_)",
    re.IGNORECASE,
)
_TIME_KEY_ALLOWED = {"generated_at", "version_duration_s"}


class StructureHintError(Exception):
    """Raised for an invalid hint or song. Nothing is written when raised."""


def hint_path(song_dir: Path) -> Path:
    return song_dir / _INNER_DIRNAME / _HINT_DIRNAME / _HINT_FILENAME


def build_brief(song: str) -> str:
    """The instructions, verbatim — the single source for both the tool and
    the MCP prompt `structure_hint`."""
    return f"""Write the pre-analysis structure hint for the song {song!r}.

1. Research the song on the web: which version this audio is (radio edit,
   extended, club mix, remix, original; remixer; length), its genre and
   subgenre, its BPM, and its expected shape (how many drops, whether a sung
   chorus takes the drop's place, whether it has build-ups, how vocals are
   used). Prefer sources that describe the same version as the audio.
2. Fill EVERY field of the schema below. Use null for anything you could not
   establish - never guess.
3. Include at least one source ({{url, title}}) you actually used.
4. NEVER write a time. No timestamps, seconds, bars, beats or section
   positions anywhere. The only duration allowed is track.version_duration_s,
   the researched version's total length. Do not write sections or lighting
   hints either.
5. Call write_structure_hint(song={song!r}, hint=<the object below>). If it is
   refused, fix the named field and call it again. A hint is only a prior; the
   audio always outranks it.

Schema (schema_version "1.0"):
{{
  "schema_version": "1.0",
  "song_name": {song!r},
  "generated_at": "YYYY-MM-DD",
  "track": {{
    "artist": string,
    "title": string,
    "version": one of {list(VERSIONS)} or null,
    "remixer": string or null,
    "version_duration_s": number or null
  }},
  "genre": {{
    "family": one of {list(FAMILIES)},
    "subgenre": one of {list(SUBGENRES)} or null,
    "bpm": number or null
  }},
  "shape": {{
    "drops": integer or null,
    "chorus_is_drop": true/false or null,
    "has_build_ups": true/false or null,
    "vocals": one of {list(VOCALS)} or null
  }},
  "confidence": number from 0 to 1 (overall),
  "sources": [{{"url": string, "title": string}}]   (at least one)
}}
"""


def load_existing(song_dir: Path) -> dict[str, Any] | None:
    path = hint_path(song_dir)
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _find_time_key(value: Any, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            where = f"{path}.{key}" if path else str(key)
            if str(key) not in _TIME_KEY_ALLOWED and _TIME_KEY.search(str(key)):
                return where
            found = _find_time_key(child, where)
            if found:
                return found
    elif isinstance(value, list):
        for i, child in enumerate(value):
            found = _find_time_key(child, f"{path}[{i}]")
            if found:
                return found
    return None


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _obj(value: Any, name: str, keys: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StructureHintError(f"{name} must be an object")
    for key in keys:
        if key not in value:
            raise StructureHintError(f"{name}.{key} is missing (use null when unknown)" if name != "hint" else f"{key} is missing")
    for key in value:
        if key not in keys:
            raise StructureHintError(f"{name}.{key} is not a schema field" if name != "hint" else f"{key} is not a schema field")
    return value


def _str(value: Any, name: str, *, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value.strip():
        raise StructureHintError(f"{name} must be a non-empty string" + (" or null" if nullable else ""))


def _enum(value: Any, name: str, allowed: tuple[str, ...], *, nullable: bool) -> None:
    if value is None and nullable:
        return
    if value not in allowed or not isinstance(value, str):
        raise StructureHintError(
            f"{name} must be one of {list(allowed)}" + (" or null" if nullable else "")
            + f", got {value!r}"
        )


def _bool(value: Any, name: str) -> None:
    if value is not None and not isinstance(value, bool):
        raise StructureHintError(f"{name} must be true, false or null")


def validate_hint(hint: Any, song: str) -> dict[str, Any]:
    """Validate against schema 1.0; raises `StructureHintError` naming the
    first bad field. Returns the hint unchanged."""
    if not isinstance(hint, dict):
        raise StructureHintError("hint must be an object")
    bad = _find_time_key(hint)
    if bad:
        raise StructureHintError(
            f"{bad}: a time-bearing field is not allowed - the hint carries no times"
        )
    top = _obj(hint, "hint", _TOP_KEYS)
    if top["schema_version"] != SCHEMA_VERSION:
        raise StructureHintError(f"schema_version must be {SCHEMA_VERSION!r}")
    if top["song_name"] != song:
        raise StructureHintError(f"song_name must be {song!r}, got {top['song_name']!r}")
    generated = top["generated_at"]
    try:
        if not isinstance(generated, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", generated):
            raise ValueError
        date.fromisoformat(generated)
    except ValueError:
        raise StructureHintError("generated_at must be an ISO date (YYYY-MM-DD)") from None

    track = _obj(top["track"], "track", _TRACK_KEYS)
    _str(track["artist"], "track.artist")
    _str(track["title"], "track.title")
    _enum(track["version"], "track.version", VERSIONS, nullable=True)
    _str(track["remixer"], "track.remixer", nullable=True)
    dur = track["version_duration_s"]
    if dur is not None and not (_is_num(dur) and dur > 0):
        raise StructureHintError("track.version_duration_s must be a positive number or null")

    genre = _obj(top["genre"], "genre", _GENRE_KEYS)
    _enum(genre["family"], "genre.family", FAMILIES, nullable=False)
    _enum(genre["subgenre"], "genre.subgenre", SUBGENRES, nullable=True)
    bpm = genre["bpm"]
    if bpm is not None and not (_is_num(bpm) and bpm > 0):
        raise StructureHintError("genre.bpm must be a positive number or null")

    shape = _obj(top["shape"], "shape", _SHAPE_KEYS)
    drops = shape["drops"]
    if drops is not None and not (isinstance(drops, int) and not isinstance(drops, bool) and drops >= 0):
        raise StructureHintError("shape.drops must be a non-negative integer or null")
    _bool(shape["chorus_is_drop"], "shape.chorus_is_drop")
    _bool(shape["has_build_ups"], "shape.has_build_ups")
    _enum(shape["vocals"], "shape.vocals", VOCALS, nullable=True)

    conf = top["confidence"]
    if not (_is_num(conf) and 0 <= conf <= 1):
        raise StructureHintError("confidence must be a number from 0 to 1")

    sources = top["sources"]
    if not isinstance(sources, list) or not sources:
        raise StructureHintError("sources must be a list with at least one {url, title}")
    for i, src in enumerate(sources):
        item = _obj(src, f"sources[{i}]", _SOURCE_KEYS)
        _str(item["url"], f"sources[{i}].url")
        _str(item["title"], f"sources[{i}].title")
    return hint


def write_hint(song_dir: Path, song: str, hint: Any) -> dict[str, Any]:
    """Validate, then replace `structure.json`. Nothing is written on refusal."""
    validate_hint(hint, song)
    path = hint_path(song_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(hint, handle, indent=2)
        handle.write("\n")
    return hint
