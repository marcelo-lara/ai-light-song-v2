from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = MCP_DIR / "tests" / "fixtures" / "analysis"


def _load_loaders():
    spec = importlib.util.spec_from_file_location("mcp_local_loaders", MCP_DIR / "loaders.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


loaders = _load_loaders()


def test_list_songs_reads_fixture_root() -> None:
    songs = loaders.list_songs(FIXTURE_ROOT)
    assert [s["song_name"] for s in songs] == sorted(
        ["McpDegenerate - Fixture", "McpFull - Fixture", "McpPartial - Fixture"]
    )
    for song in songs:
        assert song["song_name"]
        assert song["bpm"] is not None
        assert song["duration"] is not None


def test_list_songs_on_empty_root_returns_empty_list(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert loaders.list_songs(empty) == []


def test_list_songs_on_missing_root_returns_empty_list(tmp_path: Path) -> None:
    assert loaders.list_songs(tmp_path / "does-not-exist") == []


def test_get_analysis_root_env_override() -> None:
    assert loaders.get_analysis_root() == Path("/data/analysis")
    with pytest.MonkeyPatch.context() as m:
        m.setenv("MCP_ANALYSIS_ROOT", "/tmp/custom-root")
        assert loaders.get_analysis_root() == Path("/tmp/custom-root")


def test_resolve_song_dir_unknown_song_names_it() -> None:
    with pytest.raises(loaders.SongNotFoundError, match="no-such-song"):
        loaders.resolve_song_dir("no-such-song", root=FIXTURE_ROOT)


def test_resolve_song_dir_missing_file_is_named() -> None:
    with pytest.raises(loaders.MissingTopLevelFileError, match="sections.json"):
        loaders.resolve_song_dir("McpPartial - Fixture", root=FIXTURE_ROOT)


def test_resolve_song_dir_ok_for_full_fixture() -> None:
    resolved = loaders.resolve_song_dir("McpFull - Fixture", root=FIXTURE_ROOT)
    assert resolved == FIXTURE_ROOT / "McpFull - Fixture"


def test_load_top_level_json_rejects_nested_paths() -> None:
    song_dir = FIXTURE_ROOT / "McpFull - Fixture"
    for bad in ["artifacts/x.json", "../info.json", "reference/human/h.json", "info.txt"]:
        with pytest.raises((ValueError, FileNotFoundError)):
            loaders.load_top_level_json(song_dir, bad)


def test_stdio_server_initializes_and_lists_expected_tools() -> None:
    async def _run() -> None:
        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        env = dict(os.environ)
        env["MCP_ANALYSIS_ROOT"] = str(FIXTURE_ROOT)
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(MCP_DIR / "server.py")],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [tool.name for tool in tools.tools]
                assert names == ["list_songs", "get_song_overview", "get_detail"]

    asyncio.run(_run())
