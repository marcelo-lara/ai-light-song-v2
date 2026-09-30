"""Stdio MCP server for song comprehension — read-only except for two
propose-and-queue tools (v3.7 item 10) and one run-request tool (v3.8 item 3).

`list_songs`, `get_song_overview` and `get_detail` are the read surface.
`propose_hint` and `propose_section_field` are one write path: they only ever
append to a song's own proposals queue (`proposals.py`), never to a top-level
file or the operator's own hand-authored one — see docs/mcp-definition.md's
"Correction proposals" section. `request_analysis` and `get_analysis_progress`
are the other write/read path (`runs.py`, D3.1): they write/read a song's own
`_run_request.json`/`_run_progress.json`, one level under the song directory,
never a top-level or analyzer-owned file — see docs/mcp-definition.md's "The
hard boundary". Song discovery and top-level file access live in `loaders.py`
(stable); response shaping lives in `serializers.py` (volatile — a
tool-surface reshape touches that file and its snapshots only).

The repo directory is named `mcp/` but is never imported as the `mcp` package:
`mcp/` has no `__init__.py`, so `import mcp` resolves to the installed SDK
(a regular package) and never to this namespace directory. `loaders` is imported
by bare name because this file's own directory is `sys.path[0]` when it runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server import MCPServer

# Deep import: ToolError is not re-exported higher up. Raising it (rather than an
# arbitrary exception) returns is_error=True with our message intact for the
# caller to read — an arbitrary exception is treated as a crash and the caller
# sees only "Error executing tool <name>".
from mcp.server.mcpserver.exceptions import ToolError

from loaders import (
    MissingTopLevelFileError,
    SongNotFoundError,
    get_analysis_root,
    list_songs as _list_songs,
    load_top_level_json,
    resolve_song_dir,
)
from proposals import (
    ProposalValidationError,
    append_hint_proposal,
    append_section_field_proposal,
)
from runs import (
    InvalidSongNameError,
    NoRunRequestedError,
    get_progress_or_derive,
    get_songs_root,
    has_audio,
    list_unanalysed_audio_stems,
    read_progress,
    validate_song_name,
    write_request,
)
from serializers import DetailScopeError, build_detail, build_song_overview

server = MCPServer("ai-light-song-v2-mcp", version="0.1.0")


def _validate_song(song: str) -> None:
    """Resolve the song, translating discovery failures into a readable ToolError."""
    try:
        resolve_song_dir(song)
    except (SongNotFoundError, MissingTopLevelFileError) as exc:
        raise ToolError(str(exc)) from exc


def _resolve_song_or_error(song: str) -> Path:
    """Like `_validate_song`, but hands back the resolved directory for the
    two write-a-proposal tools, which need it to place the queue file."""
    try:
        return resolve_song_dir(song)
    except (SongNotFoundError, MissingTopLevelFileError) as exc:
        raise ToolError(str(exc)) from exc


def _validate_run_song_or_error(song: str) -> str:
    """`request_analysis`/`get_analysis_progress` build filesystem paths
    directly from `song` (`get_analysis_root() / song`,
    `<songs_root>/<song>.mp3`) — unlike the three read tools above, which
    only ever reach a path through `resolve_song_dir`'s own guard. Reject a
    `/`, `\\`, `..` or empty name before either path is built, same rule as
    the UI's `PUT /api/run-request/<song>` handler."""
    try:
        return validate_song_name(song)
    except InvalidSongNameError as exc:
        raise ToolError(str(exc)) from exc


@server.tool(name="list_songs")
def list_songs() -> list[dict[str, Any]]:
    """Every analysable song directory with its song_name, bpm and duration.

    A client cannot guess directory names, so this is the entry point for every
    other call.
    """
    return _list_songs()


@server.tool(name="get_song_overview")
def get_song_overview(song: str, scope: str | None = None) -> dict[str, Any]:
    """Whole-song overview (identity, grid, sections, gestures, transitions, hints).

    One small call, whole song. Optionally accepts scope="brief" to return a
    compact overview suitable for the concept-pass read (D3.3). The default
    is the full overview.

    Genre guidance (moved here from the now-dropped per-song `genre.json`
    `guidance` field, v3.6 item 8 — the text was identical across the whole
    corpus, so it is stated once, here, rather than repeated per song):
    use the genre only as review guidance for what song parts are likely to
    matter. Do not assume genre-specific drops or section semantics unless
    downstream evidence supports them.
    """
    _validate_song(song)
    return build_song_overview(song, scope=scope)


@server.tool(name="get_detail")
def get_detail(
    song: str,
    section_id: str | None = None,
    gesture_id: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    bars: list[int] | None = None,
    interval_ms: int | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """On-demand dense detail for one resolved span.

    Exactly one scope selector is required: ``section_id``, ``gesture_id``,
    ``start_ms`` + ``end_ms``, or ``bars`` (v3.7 item 5 — ``[start_bar,
    end_bar]``, inclusive, 1-indexed). Zero or two is an error — there is no
    precedence rule. A resolved span over the 5 s cap (a maximum, not a
    default) returns the structural view with the dense frames withheld and
    the cap named. ``interval_ms`` is caller-chosen and decimates the
    published 20 ms series by chunk-averaging; finer than 20 ms is an error,
    never a silent upsample. ``sources`` narrows the stem set (default all
    five, stable order).
    """
    _validate_song(song)
    try:
        return build_detail(
            song,
            section_id=section_id,
            gesture_id=gesture_id,
            start_ms=start_ms,
            end_ms=end_ms,
            bars=bars,
            interval_ms=interval_ms,
            sources=sources,
        )
    except DetailScopeError as exc:
        raise ToolError(str(exc)) from exc


@server.tool(name="propose_hint")
def propose_hint(
    song: str,
    start: float,
    end: float,
    title: str,
    summary: str,
    evidence: str,
) -> dict[str, Any]:
    """Queue a new lighting hint for operator review — never applied.

    The server stays read-only by the hard boundary in
    docs/mcp-definition.md: this appends one entry to the song's own
    proposals queue and nothing else. It never becomes a published field
    until an operator reviews and approves it in the debugger UI, which is
    the only surface that may write the operator's own hints file and the
    only one that triggers a republish. ``evidence`` is required — an empty
    or missing value is rejected and nothing is written.
    """
    song_dir = _resolve_song_or_error(song)
    try:
        return append_hint_proposal(
            song_dir,
            song,
            start=start,
            end=end,
            title=title,
            summary=summary,
            evidence=evidence,
        )
    except ProposalValidationError as exc:
        raise ToolError(str(exc)) from exc


@server.tool(name="propose_section_field")
def propose_section_field(
    song: str,
    section_id: str,
    field: str,
    value: Any,
    evidence: str,
) -> dict[str, Any]:
    """Queue a correction to one section's ``energy``, ``tension`` or
    ``rhythm.<stem>`` (``rhythm.drums``/``rhythm.bass``/``rhythm.harmonic``/
    ``rhythm.vocals``) — never applied.

    Same read-only boundary as ``propose_hint``: this appends to the song's
    proposals queue only. ``section_id`` must name a row already published on
    ``sections.json``. ``evidence`` is required — an empty or missing value
    is rejected and nothing is written. Approval — the only path to the
    operator's own file, and the only trigger for the ``section-clues``
    republish that would surface it as ``*_source: "human"`` — happens in
    the debugger UI.
    """
    song_dir = _resolve_song_or_error(song)
    sections_payload = load_top_level_json(song_dir, "sections.json")
    known_ids = {row.get("section_id") for row in sections_payload.get("sections", [])}
    if section_id not in known_ids:
        raise ToolError(f"Unknown section_id: {section_id!r}")
    try:
        return append_section_field_proposal(
            song_dir,
            song,
            section_id=section_id,
            field=field,
            value=value,
            evidence=evidence,
        )
    except ProposalValidationError as exc:
        raise ToolError(str(exc)) from exc


@server.tool(name="request_analysis")
def request_analysis(song: str) -> dict[str, Any]:
    """Request a full ``./analyze`` run for a song with no analysis yet.

    Reuses v3.8 item 1's request/progress files: whether a run was started
    from the debugger button or from here, the same host-side
    ``./analysis-watcher`` and the same ``_run_progress.json`` serve both
    (D3.1 — a bounded, documented exception to the top-level-only exposure
    rule; see docs/mcp-definition.md's "The hard boundary").

    Refuses outright for a song that already has a complete analysis — use
    ``get_song_overview``/``get_detail`` instead of requesting a redundant
    run — and for a song with no *non-empty* audio file to analyze (a 0-byte
    placeholder counts as no file: a run against it is guaranteed to fail).
    Returns immediately without waiting for the run to finish; poll
    ``get_analysis_progress`` roughly once a minute rather than re-calling
    this tool.
    """
    song = _validate_run_song_or_error(song)

    try:
        resolve_song_dir(song)
    except (SongNotFoundError, MissingTopLevelFileError):
        pass
    else:
        raise ToolError(
            f"{song!r} is already fully analysed — use get_song_overview or "
            "get_detail instead of requesting a new run."
        )

    song_dir = get_analysis_root() / song
    progress = read_progress(song_dir)
    if progress is not None and progress.get("status") in ("queued", "running"):
        return progress

    if not has_audio(song):
        stems = list_unanalysed_audio_stems()
        raise ToolError(
            f"No audio found for {song!r} ({song}.mp3) under the configured "
            f"songs root. Unanalysed audio available: {stems}"
        )

    request = write_request(song_dir, song)
    return {
        "status": "requested",
        "song": song,
        "requested_at": request["requested_at"],
        "poll_with": "get_analysis_progress",
        "poll_every_s": 60,
        "note": "analysis takes several minutes; poll about once a minute",
    }


@server.tool(name="get_analysis_progress")
def get_analysis_progress(song: str) -> dict[str, Any]:
    """Poll the status of a run started with ``request_analysis``.

    Once the host-side ``./analysis-watcher`` has picked up the request this
    reads ``_run_progress.json`` verbatim (``status``: ``queued``/
    ``running``/``done``/``failed``, plus ``stage`` while running). Before
    that: ``queued`` while the request is fresh, or ``not_started`` once it
    has sat unpicked-up past the threshold — meaning no watcher appears to be
    running (no-silent-fallbacks: an honest "nothing is watching this" beats
    an indefinite poll loop). Errors if nothing was ever requested for this
    song.
    """
    song = _validate_run_song_or_error(song)

    song_dir = get_analysis_root() / song
    try:
        return get_progress_or_derive(song, song_dir)
    except NoRunRequestedError as exc:
        raise ToolError(str(exc)) from exc


if __name__ == "__main__":
    server.run(transport="stdio")
