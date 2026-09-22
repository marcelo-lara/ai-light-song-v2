"""Read-only stdio MCP server for song comprehension.

`list_songs`, `get_song_overview` and `get_detail` are all implemented.
Song discovery and top-level file access live in `loaders.py` (stable); response
shaping lives in `serializers.py` (volatile — a tool-surface reshape touches
that file and its snapshots only).

The repo directory is named `mcp/` but is never imported as the `mcp` package:
`mcp/` has no `__init__.py`, so `import mcp` resolves to the installed SDK
(a regular package) and never to this namespace directory. `loaders` is imported
by bare name because this file's own directory is `sys.path[0]` when it runs.
"""

from __future__ import annotations

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
    list_songs as _list_songs,
    resolve_song_dir,
)
from serializers import DetailScopeError, build_detail, build_song_overview

server = MCPServer("ai-light-song-v2-mcp", version="0.1.0")


def _validate_song(song: str) -> None:
    """Resolve the song, translating discovery failures into a readable ToolError."""
    try:
        resolve_song_dir(song)
    except (SongNotFoundError, MissingTopLevelFileError) as exc:
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


if __name__ == "__main__":
    server.run(transport="stdio")
