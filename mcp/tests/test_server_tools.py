"""Server-level behaviour of the three tools: argument validation, error
translation, and the payloads `get_song_overview` / `get_detail` now return
(v3.1 items 9-10). A discovery failure or an invalid scope is translated into a
readable `ToolError` so the caller reads the message, not a generic crash string.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = MCP_DIR / "tests" / "fixtures" / "analysis"


def _load(name: str, filename: str):
    sys.path.insert(0, str(MCP_DIR))
    spec = importlib.util.spec_from_file_location(name, MCP_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load("mcp_local_server", "server.py")
loaders = _load("mcp_local_loaders2", "loaders.py")


@pytest.fixture(autouse=True)
def _point_at_fixtures(monkeypatch):
    monkeypatch.setenv("MCP_ANALYSIS_ROOT", str(FIXTURE_ROOT))


def test_get_song_overview_returns_a_payload_for_valid_song() -> None:
    ov = server.get_song_overview("McpFull - Fixture")
    assert ov["song_name"] == "McpFull - Fixture"
    assert ov["grid"]["bar_count"] > 0
    assert "beats" not in ov["grid"]


def test_get_detail_returns_dense_frames_for_a_window() -> None:
    resp = server.get_detail("McpFull - Fixture", start_ms=0, end_ms=3000, interval_ms=20)
    assert resp["dense"]["frame_count"] > 0
    assert resp["span"]["duration"] == 3.0


def test_get_song_overview_carries_arrangement_block() -> None:
    ov = server.get_song_overview("McpFull - Fixture")
    assert ov["arrangement"]["block_count"] >= 3


def test_get_detail_structural_view_carries_arrangement() -> None:
    resp = server.get_detail(
        "McpFull - Fixture", start_ms=0, end_ms=3000, interval_ms=20
    )
    assert "arrangement" in resp["structural"]


def test_get_detail_errors_on_zero_or_two_scopes() -> None:
    with pytest.raises(ToolError):
        server.get_detail("McpFull - Fixture")
    with pytest.raises(ToolError):
        server.get_detail(
            "McpFull - Fixture", section_id="section-002", gesture_id="gesture-001"
        )


def test_get_song_overview_validates_song_first() -> None:
    with pytest.raises(ToolError, match="mystery-song"):
        server.get_song_overview("mystery-song")
    with pytest.raises(ToolError, match="sections.json"):
        server.get_song_overview("McpPartial - Fixture")


def test_registered_tool_names() -> None:
    tools = asyncio.run(server.server.list_tools())
    assert [t.name for t in tools] == ["list_songs", "get_song_overview", "get_detail"]


def test_list_songs_tool_matches_loader() -> None:
    assert server.list_songs() == loaders.list_songs(FIXTURE_ROOT)


def test_fixtures_carry_no_inner_folders() -> None:
    for song_dir in FIXTURE_ROOT.iterdir():
        if not song_dir.is_dir():
            continue
        for child in song_dir.iterdir():
            assert child.is_file() and child.suffix == ".json", child
