"""The two substantive tools are registered but must NOT return a payload yet.

Response shaping (serializers) is v3.1 items 9-10. For the scaffold the honest
behaviour is: validate arguments, then fail with an explicit not-implemented
message (a `ToolError`, so the caller reads the message rather than a generic
crash string).
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


def test_get_song_overview_not_implemented_for_valid_song() -> None:
    with pytest.raises(ToolError, match="not implemented yet"):
        server.get_song_overview("McpFull - Fixture")


def test_get_detail_not_implemented_for_valid_song() -> None:
    with pytest.raises(ToolError, match="not implemented yet"):
        server.get_detail("McpFull - Fixture", scope="time_window")


def test_get_song_overview_validates_before_reporting_not_implemented() -> None:
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
