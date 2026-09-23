"""v3.7 item 10 — `propose_hint` / `propose_section_field` append to the
song's own `reference` / `proposals` / `pending.json` queue (path spelled out
via separate literals — see `proposals.py`'s own docstring for why) and never
write anywhere else. Each test works against a throwaway copy of the
`McpFull - Fixture` song so the committed fixtures stay untouched (and so
`test_fixtures_carry_no_inner_folders` in test_server_tools.py keeps passing
against the real fixture tree).
"""

from __future__ import annotations

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


server = _load("mcp_local_server_proposals", "server.py")


@pytest.fixture()
def writable_root(tmp_path, monkeypatch):
    root = tmp_path / "analysis"
    root.mkdir()
    shutil.copytree(FIXTURE_ROOT / "McpFull - Fixture", root / "McpFull - Fixture")
    monkeypatch.setenv("MCP_ANALYSIS_ROOT", str(root))
    return root


def _queue_path(root: Path) -> Path:
    return root / "McpFull - Fixture" / "reference" / "proposals" / "pending.json"


def test_propose_hint_requires_evidence_and_writes_nothing(writable_root) -> None:
    with pytest.raises(ToolError):
        server.propose_hint(
            "McpFull - Fixture",
            start=10.0,
            end=12.0,
            title="Drop payoff",
            summary="loudness spike",
            evidence="",
        )
    assert not _queue_path(writable_root).exists()


def test_propose_hint_appends_one_entry(writable_root) -> None:
    entry = server.propose_hint(
        "McpFull - Fixture",
        start=10.0,
        end=12.0,
        title="Drop payoff",
        summary="loudness spike at the section boundary",
        evidence="loudness.json shows a 6dB step at 10.0s",
    )
    assert entry["type"] == "hint"
    assert entry["status"] == "pending"
    payload = json.loads(_queue_path(writable_root).read_text())
    assert payload["schema_version"] == "1.0"
    assert payload["song_name"] == "McpFull - Fixture"
    assert len(payload["proposals"]) == 1
    assert payload["proposals"][0]["id"] == entry["id"]


def test_two_calls_append_two_distinct_entries(writable_root) -> None:
    first = server.propose_hint(
        "McpFull - Fixture",
        start=10.0,
        end=12.0,
        title="Drop payoff",
        summary="first",
        evidence="evidence one",
    )
    second = server.propose_section_field(
        "McpFull - Fixture",
        section_id="section-001",
        field="tension",
        value=4,
        evidence="evidence two",
    )
    assert first["id"] != second["id"]
    payload = json.loads(_queue_path(writable_root).read_text())
    assert [p["id"] for p in payload["proposals"]] == [first["id"], second["id"]]
    assert payload["proposals"][0]["hint"]["title"] == "Drop payoff"
    assert payload["proposals"][1]["section_field"] == {
        "section_id": "section-001",
        "field": "tension",
        "value": 4,
    }


def test_propose_section_field_rejects_unknown_section(writable_root) -> None:
    with pytest.raises(ToolError, match="section-999"):
        server.propose_section_field(
            "McpFull - Fixture",
            section_id="section-999",
            field="tension",
            value=3,
            evidence="evidence",
        )
    assert not _queue_path(writable_root).exists()


def test_propose_section_field_rejects_out_of_range_scalar(writable_root) -> None:
    with pytest.raises(ToolError):
        server.propose_section_field(
            "McpFull - Fixture",
            section_id="section-001",
            field="energy",
            value=9,
            evidence="evidence",
        )
    assert not _queue_path(writable_root).exists()


def test_propose_section_field_rejects_bad_rhythm_value(writable_root) -> None:
    with pytest.raises(ToolError):
        server.propose_section_field(
            "McpFull - Fixture",
            section_id="section-001",
            field="rhythm.drums",
            value="triplet-ish",
            evidence="evidence",
        )
    assert not _queue_path(writable_root).exists()


def test_propose_section_field_rejects_unknown_field_name(writable_root) -> None:
    with pytest.raises(ToolError):
        server.propose_section_field(
            "McpFull - Fixture",
            section_id="section-001",
            field="loudness",
            value=3,
            evidence="evidence",
        )
    assert not _queue_path(writable_root).exists()


def test_propose_section_field_accepts_a_valid_rhythm_value(writable_root) -> None:
    entry = server.propose_section_field(
        "McpFull - Fixture",
        section_id="section-002",
        field="rhythm.vocals",
        value="eighth",
        evidence="phrase onsets land on every eighth",
    )
    assert entry["section_field"]["value"] == "eighth"
