"""Read-only stdio MCP server for song comprehension.

`list_songs` and `get_song_overview` are implemented; `get_detail` validates its
argument and raises an explicit not-implemented error (lands in v3.1 item 10).
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
from serializers import build_song_overview

server = MCPServer("ai-light-song-v2-mcp", version="0.1.0")

_NOT_READY = "response shaping lands in a later v3.1 plan item"


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
def get_song_overview(song: str) -> dict[str, Any]:
    """Whole-song overview (identity, grid, sections, gestures, transitions, hints).

    One small call, whole song. The grid is a summary with an honest downbeat
    note — never the beat list. Gestures are grouped one row per composite
    gesture. Human hints are verbatim and outrank every inferred field.
    """
    _validate_song(song)
    return build_song_overview(song)


@server.tool(name="get_detail")
def get_detail(
    song: str,
    scope: str,
    interval_ms: int | None = None,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """On-demand dense detail for one resolved span.

    Not implemented yet: the song argument is validated and then an explicit
    not-implemented error is raised.
    """
    _validate_song(song)
    raise ToolError(f"get_detail is not implemented yet — {_NOT_READY}")


if __name__ == "__main__":
    server.run(transport="stdio")
