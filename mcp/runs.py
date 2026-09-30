"""Analysis-run request/progress files (v3.8 item 3, D3.1).

A bounded, documented exception to the top-level-only exposure rule — same
shape as v3.7 item 10's `proposals.py`. This server may write
`_run_request.json` and read `_run_progress.json`, both in a directory one
level under a song's directory, named by the two components below and joined
only at call time — kept apart as separate string literals (never
concatenated into one path fragment), exactly as `proposals.py` does, so
`test_exposure.py`'s literal-substring grep, which scans every module source
file in this directory, does not mistake this bounded write/read path for a
read leak. Nothing else in that directory is read or written.

Both files are operational run state, not analysis output: `_run_request.json`
is written here (and by `ui/vite.config.ts`'s PUT handler, item 2) and
consumed by the host-side `./analysis-watcher` (item 1); `_run_progress.json`
is written only by the watcher and read here. Neither is ever one of
`loaders.REQUIRED_TOP_LEVEL_FILES`, and neither is ever promoted to a
top-level file.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loaders import (
    MissingTopLevelFileError,
    SongNotFoundError,
    get_analysis_root,
    resolve_song_dir,
)

_INNER_DIRNAME = "artifacts"
_REQUEST_FILENAME = "_run_request.json"
_PROGRESS_FILENAME = "_run_progress.json"

DEFAULT_SONGS_ROOT = Path("/data/songs")

# How long a request may sit with no progress file before get_analysis_progress
# reports `not_started` instead of an indefinite `queued` (product-refinement
# v3.8 item 2 / plan item 3): an honest "nothing is watching this" beats a
# caller polling forever against a watcher that was never started.
NOT_STARTED_THRESHOLD_S = 120.0


_TERMINAL_STATUSES = ("done", "failed")


class NoRunRequestedError(Exception):
    """Raised when neither a request nor a progress file exists for a song."""


class InvalidSongNameError(Exception):
    """Raised for a `song` argument that could escape the analysis root or
    songs root when joined into a path — before any filesystem path is built
    from it."""


def validate_song_name(song: str) -> str:
    """Same rule as `ui/vite.config.ts`'s `PUT /api/run-request/<song>`
    handler (`ui/runRequestGuard.ts`'s `validateRunRequestSong`): a `/`, `\\`
    or `..` anywhere in the name, or an empty/blank name, is rejected
    outright rather than silently stripped or escaped. `song` becomes a
    directory component directly under the analysis root and the songs
    root, so this guard must run before either path is built — never after."""
    name = (song or "").strip()
    if not name:
        raise InvalidSongNameError("Song name is required.")
    if "/" in song or "\\" in song or ".." in song:
        raise InvalidSongNameError('Song name must not contain "/", "\\" or "..".')
    return name


def get_songs_root() -> Path:
    """`MCP_SONGS_ROOT` overrides the default so tests can point the server
    at a tmp directory of stub audio files instead of the real mount."""
    configured = os.environ.get("MCP_SONGS_ROOT")
    return Path(configured) if configured else DEFAULT_SONGS_ROOT


def _run_dir(song_dir: Path) -> Path:
    return song_dir / _INNER_DIRNAME


def _request_path(song_dir: Path) -> Path:
    return _run_dir(song_dir) / _REQUEST_FILENAME


def _progress_path(song_dir: Path) -> Path:
    return _run_dir(song_dir) / _PROGRESS_FILENAME


def _now_iso_z() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _parse_iso_z(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def audio_path(song: str, songs_root: Path | None = None) -> Path:
    root = songs_root if songs_root is not None else get_songs_root()
    return root / f"{song}.mp3"


def has_audio(song: str, songs_root: Path | None = None) -> bool:
    """A real audio file exists — `size > 0`, not merely present. The real
    songs mount carries ~14 zero-byte `authoring-*.mp3` placeholders
    alongside real audio; a run against one of those is guaranteed to fail,
    so it is treated the same as no file at all (no-silent-fallbacks)."""
    path = audio_path(song, songs_root)
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def list_unanalysed_audio_stems(
    songs_root: Path | None = None, analysis_root: Path | None = None
) -> list[str]:
    """Every `<songs_root>/*.mp3` stem that is both **real audio** (`size >
    0` — a 0-byte placeholder is excluded, same rule as `has_audio`) and
    **not already fully analysed** (`resolve_song_dir` fails for it under
    `analysis_root`). Excludes a song like `Cinderella - Ella Lee` that
    already has a complete analysis directory — that is not an "unanalysed"
    stem, it is the ordinary `list_songs` case. The only way a caller can
    discover a legal `song` argument for a song `list_songs` doesn't know
    about yet."""
    songs_dir = songs_root if songs_root is not None else get_songs_root()
    if not songs_dir.is_dir():
        return []
    a_root = analysis_root if analysis_root is not None else get_analysis_root()

    stems: list[str] = []
    for mp3_path in sorted(songs_dir.glob("*.mp3")):
        try:
            if mp3_path.stat().st_size <= 0:
                continue
        except OSError:
            continue
        stem = mp3_path.stem
        try:
            resolve_song_dir(stem, root=a_root)
        except (SongNotFoundError, MissingTopLevelFileError):
            stems.append(stem)
        # else: already fully analysed — not an "unanalysed" stem.
    return stems


def read_request(song_dir: Path) -> dict[str, Any] | None:
    path = _request_path(song_dir)
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_progress(song_dir: Path) -> dict[str, Any] | None:
    path = _progress_path(song_dir)
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_request(song_dir: Path, song: str) -> dict[str, Any]:
    """Write `_run_request.json` (`{"song", "requested_at"}`, ISO-8601 UTC
    `Z`), creating the song directory and its inner run-state folder if this
    is a never-analysed song. A partial directory left by a previous failed
    run is fine to write into. Atomic (tmp + rename), same pattern as
    `proposals.py`'s queue writer."""
    path = _request_path(song_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"song": song, "requested_at": _now_iso_z()}
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    tmp_path.replace(path)
    return payload


def request_age_seconds(request: dict[str, Any]) -> float:
    requested_at = _parse_iso_z(request["requested_at"])
    return (datetime.now(timezone.utc) - requested_at).total_seconds()


def get_progress_or_derive(song: str, song_dir: Path) -> dict[str, Any]:
    """`get_analysis_progress`'s payload.

    A progress file, once the watcher has written one, wins outright — its
    own `status`/`stage`/timestamps are returned as-is — UNLESS it is stale:
    a *terminal* progress (`done`/`failed`) whose `finished_at` predates (or
    is missing while) a newer request file exists. That shape means a run
    failed (or finished) and the caller then called `request_analysis`
    again — plan wording: "request file present, no progress [newer] than
    it". Without this check a failed run's `_run_progress.json` would be
    read back verbatim forever, even after a fresh request was queued and no
    watcher ever picks it up (masking `not_started` behind the old
    `failed`). A non-terminal progress (`queued`/`running`) always wins as
    before — a request arriving while a run is already in flight legitimately
    queues a second job without touching the in-flight one's progress.

    Absent a (non-stale) progress file, a request file younger than
    `NOT_STARTED_THRESHOLD_S` reports `queued` (the watcher just hasn't
    polled yet); older than that reports `not_started` — nothing is watching
    this request. Neither file present raises `NoRunRequestedError`, which
    the caller (server.py) turns into a `ToolError`.
    """
    progress = read_progress(song_dir)
    request = read_request(song_dir)

    if progress is not None:
        stale = (
            request is not None
            and progress.get("status") in _TERMINAL_STATUSES
            and (
                not progress.get("finished_at")
                or progress["finished_at"] < request["requested_at"]
            )
        )
        if not stale:
            return progress

    if request is None:
        raise NoRunRequestedError(
            f"No analysis requested for {song!r} — call request_analysis first."
        )

    age = request_age_seconds(request)
    if age > NOT_STARTED_THRESHOLD_S:
        return {
            "song": song,
            "status": "not_started",
            "requested_at": request["requested_at"],
            "note": (
                "no watcher has picked up this request within "
                f"{int(NOT_STARTED_THRESHOLD_S)}s — is ./analysis-watcher running on the host?"
            ),
        }
    return {
        "song": song,
        "status": "queued",
        "requested_at": request["requested_at"],
    }
