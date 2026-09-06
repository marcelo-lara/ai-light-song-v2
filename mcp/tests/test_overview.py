"""get_song_overview (v3.1 item 9): golden snapshots + honesty / budget checks.

Snapshots are regenerated, not defended: run with ``MCP_REGEN_SNAPSHOTS=1`` to
re-record them in the same commit as a deliberate shape change, one line of
justification per changed file in the commit message.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = MCP_DIR / "tests" / "fixtures" / "analysis"
SNAP_DIR = MCP_DIR / "tests" / "__snapshots__"

sys.path.insert(0, str(MCP_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MCP_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serializers = _load("mcp_serializers", "serializers.py")

RESOLVABLE = ["McpFull - Fixture", "McpDegenerate - Fixture"]


def _serialize(payload: object) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _overview(song: str) -> dict:
    return serializers.build_song_overview(song, root=FIXTURE_ROOT)


@pytest.mark.parametrize("song", RESOLVABLE)
def test_overview_matches_snapshot(song: str) -> None:
    current = _serialize(_overview(song))
    snap = SNAP_DIR / f"get_song_overview__{song}.json"
    if os.environ.get("MCP_REGEN_SNAPSHOTS"):
        snap.write_text(current, encoding="utf-8")
        pytest.skip(f"regenerated {snap.name}")
    assert snap.is_file(), f"missing snapshot {snap}"
    assert current == snap.read_text(encoding="utf-8")


@pytest.mark.parametrize("song", RESOLVABLE)
def test_overview_is_deterministic(song: str) -> None:
    assert _serialize(_overview(song)) == _serialize(_overview(song))


def test_overview_budget_mcpfull_under_6kb() -> None:
    size = len(_serialize(_overview("McpFull - Fixture")).encode("utf-8"))
    # D25: the committed budget assert is fixture-based; 6 KB is the plan's
    # stated ceiling for Armin - Revolution (7 sections, 58 event rows).
    assert size < 6144, f"overview is {size} bytes, over the 6144-byte budget"


def test_overview_never_emits_the_beat_list() -> None:
    ov = _overview("McpFull - Fixture")
    assert "beats" not in ov["grid"]
    blob = json.dumps(ov)
    assert '"time": 0.5' not in blob  # a beat-grid time would leak the list


def test_overview_collapses_gesture_phases_to_one_row() -> None:
    timeline = json.loads(
        (FIXTURE_ROOT / "McpFull - Fixture" / "song_event_timeline.json").read_text()
    )
    phase_rows = [e for e in timeline["events"] if e.get("gesture_id")]
    gesture_ids = {e["gesture_id"] for e in phase_rows}
    rows = _overview("McpFull - Fixture")["gestures"]["rows"]
    assert len(rows) == len(gesture_ids)
    assert len(rows) < len(phase_rows)
    assert rows[0]["phases_present"] == ["approach", "build", "tension", "impact", "release"]
    assert rows[0]["phases_absent"] == []
    assert rows[0]["peak_intensity"] == 0.95


def test_overview_no_host_paths() -> None:
    for song in RESOLVABLE:
        assert "/data/" not in _serialize(_overview(song))


def test_overview_degenerate_surfaces_honest_uncertainty() -> None:
    ov = _overview("McpDegenerate - Fixture")
    assert all(r["function_status"] == "unknown" for r in ov["sections"]["rows"])
    assert ov["sections"]["caveat"] == "same_label_as is label repetition, not acoustic identity"
    assert ov["grid"]["downbeats_null_confidence"] == ov["grid"]["downbeat_count"]
    assert "do not trust bar numbers" in ov["grid"]["downbeat_note"]
    assert ov["gestures"]["rows"] == []


def test_overview_full_carries_field_sources_per_block() -> None:
    ov = _overview("McpFull - Fixture")
    assert ov["grid"]["field_sources"]["downbeat_confidence"] == "allin1"
    assert ov["sections"]["field_sources"]["function"] == "allin1"
    assert ov["gestures"]["field_sources"]["type"] == "gestures"
    assert ov["identity"]["field_sources"]["bpm"] == "essentia"


def test_overview_human_hint_verbatim_with_lighting() -> None:
    rows = _overview("McpFull - Fixture")["human_hints"]["rows"]
    assert len(rows) == 1
    assert rows[0]["title"] == "Breath"
    assert rows[0]["source"] == "human"
    assert rows[0]["lighting_hint"].startswith("soft motion")


def test_overview_partial_still_errors() -> None:
    from loaders import MissingTopLevelFileError

    with pytest.raises(MissingTopLevelFileError):
        serializers.build_song_overview("McpPartial - Fixture", root=FIXTURE_ROOT)
