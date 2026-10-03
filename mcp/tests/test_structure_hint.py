"""v3.10 item 7 - `get_structure_hint_brief` / `write_structure_hint`.

Throwaway tmp roots only; the committed fixtures stay untouched."""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import shutil
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


server = _load("mcp_local_server_hint", "server.py")

ANALYSED = "McpFull - Fixture"
UNANALYSED = "McpUnanalysed - Fixture"


@pytest.fixture()
def roots(tmp_path, monkeypatch):
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    shutil.copytree(FIXTURE_ROOT / ANALYSED, analysis / ANALYSED)
    songs = tmp_path / "songs"
    songs.mkdir()
    (songs / f"{UNANALYSED}.mp3").write_bytes(b"stub-audio")
    monkeypatch.setenv("MCP_ANALYSIS_ROOT", str(analysis))
    monkeypatch.setenv("MCP_SONGS_ROOT", str(songs))
    return analysis


def _hint(song: str) -> dict:
    return {
        "schema_version": "1.1",
        "song_name": song,
        "generated_at": "2026-10-01",
        "track": {"artist": "A", "title": "T", "version": "extended",
                  "remixer": None, "version_duration_s": 400.5},
        "genre": {"family": "edm", "subgenre": "big_room", "bpm": 128},
        "shape": {
            "drops": {"value": 2, "basis": "stated", "source": 0, "quote": "It has two drops."},
            "chorus_is_drop": {"value": False, "basis": "inferred", "source": 0,
                               "quote": "A sung chorus follows the second drop."},
            "has_build_ups": {"value": None, "basis": None, "source": None, "quote": None},
            "vocals": None,
        },
        "confidence": 0.7,
        "sources": [{"url": "https://example.com/x", "title": "x"}],
    }


def _path(root: Path, song: str) -> Path:
    return root / song / "reference" / "pre-analysis" / "structure.json"


@pytest.mark.parametrize("song", [ANALYSED, UNANALYSED])
def test_valid_hint_round_trips_through_existing(roots, song) -> None:
    before = server.get_structure_hint_brief(song)
    assert before["existing"] is None
    server.write_structure_hint(song, _hint(song))
    assert json.loads(_path(roots, song).read_text()) == _hint(song)
    assert server.get_structure_hint_brief(song)["existing"] == _hint(song)


def test_brief_is_the_prompt_and_carries_the_rules(roots) -> None:
    brief = server.get_structure_hint_brief(UNANALYSED)["brief"]
    prompt = asyncio.run(server.server.get_prompt("structure_hint", {"song": UNANALYSED}))
    assert prompt.messages[0].content.text == brief
    low = brief.lower()
    for needle in ("inferred", "quote", "not a source", "never a bare guess", '"1.1"', "research", "version", "genre", "null", "at least one source", "never write a time"):
        assert needle in low


def _mutations():
    def enum(h): h["genre"]["family"] = "polka"
    def sub(h): h["genre"]["subgenre"] = "polka"
    def nosrc(h): h["sources"] = []
    def missing_src(h): del h["sources"]
    def time_top(h): h["timestamp"] = 12
    def time_nested(h): h["shape"]["drop_start"] = 61.0
    def time_in_source(h): h["sources"][0]["time"] = 3
    def missing_field(h): del h["track"]["remixer"]
    def wrong_name(h): h["song_name"] = "other"
    def conf(h): h["confidence"] = 1.5
    def noquote(h): h["shape"]["drops"]["quote"] = ""
    def nobasis(h): h["shape"]["chorus_is_drop"]["basis"] = None
    def badsrc(h): h["shape"]["drops"]["source"] = 1
    def v10(h):
        h["schema_version"] = "1.0"
        h["shape"] = {"drops": 2, "chorus_is_drop": False, "has_build_ups": True, "vocals": None}
    def nullwith(h): h["shape"]["has_build_ups"]["quote"] = "x"
    return [
        ("shape.drops.quote", noquote), ("shape.chorus_is_drop.basis", nobasis),
        ("shape.drops.source", badsrc), ("schema_version", v10),
        ("shape.has_build_ups.quote", nullwith),
        ("genre.family", enum), ("genre.subgenre", sub), ("sources", nosrc),
        ("sources", missing_src), ("timestamp", time_top),
        ("shape.drop_start", time_nested), ("sources[0].time", time_in_source),
        ("track.remixer", missing_field), ("song_name", wrong_name),
        ("confidence", conf),
    ]


@pytest.mark.parametrize("field,mutate", _mutations())
def test_invalid_hint_refused_naming_field_and_writes_nothing(roots, field, mutate) -> None:
    bad = copy.deepcopy(_hint(UNANALYSED))
    mutate(bad)
    with pytest.raises(ToolError, match=field.replace("[", r"\[").replace("]", r"\]")):
        server.write_structure_hint(UNANALYSED, bad)
    assert not _path(roots, UNANALYSED).exists()


def test_refusal_keeps_an_earlier_hint(roots) -> None:
    server.write_structure_hint(UNANALYSED, _hint(UNANALYSED))
    bad = _hint(UNANALYSED)
    bad["sources"] = []
    with pytest.raises(ToolError):
        server.write_structure_hint(UNANALYSED, bad)
    assert server.get_structure_hint_brief(UNANALYSED)["existing"] == _hint(UNANALYSED)


def test_unknown_song_and_bad_name_refused(roots) -> None:
    for fn, args in (
        (server.get_structure_hint_brief, ("No Such Song",)),
        (server.write_structure_hint, ("No Such Song", _hint("No Such Song"))),
        (server.get_structure_hint_brief, ("../evil",)),
    ):
        with pytest.raises(ToolError):
            fn(*args)
    assert not (roots / "No Such Song").exists()


def test_legacy_1_0_hint_is_readable_but_not_writable(roots) -> None:
    legacy = _hint(UNANALYSED)
    legacy["schema_version"] = "1.0"
    legacy["shape"] = {"drops": 2, "chorus_is_drop": False, "has_build_ups": True, "vocals": None}
    path = _path(roots, UNANALYSED)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(legacy))
    assert server.get_structure_hint_brief(UNANALYSED)["existing"] == legacy
    with pytest.raises(ToolError, match="schema_version"):
        server.write_structure_hint(UNANALYSED, legacy)
    assert json.loads(path.read_text()) == legacy
