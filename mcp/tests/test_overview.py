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
    # v3.7 item 2 — `impact_alignment` is a new, always-resolved-or-omitted
    # section field (omitted when null, same convention as energy/tension —
    # see `_section_clue_fields`); the fixture carries one resolved example
    # so this test still exercises the non-null shape, so the ceiling moves
    # up by ~300 bytes to keep it, still well under the 8 KB the tool
    # description budgets for a fully-populated real song.
    assert size < 6450, f"overview is {size} bytes, over the 6450-byte budget"


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


def test_overview_human_hints_source_declared_once() -> None:
    ov = _overview("McpFull - Fixture")
    assert ov["human_hints"]["source"] == "human"
    assert all("source" not in r for r in ov["human_hints"]["rows"])


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
    assert rows[0]["lighting_hint"].startswith("soft motion")


_FIELD_SOURCE_VOCAB = {
    "essentia", "allin1", "harmonic", "omnizart", "demucs", "gestures",
    "genre", "human", "inference", "unknown", "arrangement_state",
    "energy_level", "tension_shape", "rhythm_drum_ioi",
    "rhythm_stem_autocorr", "rhythm_vocal_onsets", "seed_unreviewed",
}


def test_overview_review_warning_present_when_a_row_is_seed_unreviewed() -> None:
    # v3.6 item 10 — McpFull - Fixture's section-002 carries an
    # energy_source: "seed_unreviewed" override (see its sections.json).
    ov = _overview("McpFull - Fixture")
    assert "review_warning" in ov
    assert ov["review_warning"]["section_ids"] == ["section-002"]
    assert "seed_unreviewed" in ov["review_warning"]["text"]
    assert "not yet reviewed by the operator" in ov["review_warning"]["text"]


def test_overview_review_warning_absent_when_nothing_is_seed_unreviewed() -> None:
    # McpDegenerate - Fixture's sections.json carries no energy/tension/rhythm
    # fields at all, so certainly no seed_unreviewed source.
    ov = _overview("McpDegenerate - Fixture")
    assert "review_warning" not in ov


def test_overview_section_rows_carry_clue_fields_only_when_present() -> None:
    rows = {r["section_id"]: r for r in _overview("McpFull - Fixture")["sections"]["rows"]}
    assert rows["section-001"]["energy"] == 3
    assert rows["section-001"]["rhythm"]["drums"]["subdivision"] == "quarter"
    assert "energy_source" not in rows["section-001"]  # matches file default
    assert rows["section-002"]["energy_source"] == "seed_unreviewed"
    assert rows["section-002"]["energy_confidence"] is None
    assert "energy" not in rows["section-003"]  # no clue at all -> absent, never guessed
    assert "rhythm" not in rows["section-003"]


def test_overview_full_carries_arrangement_block() -> None:
    ov = _overview("McpFull - Fixture")
    blocks = json.loads(
        (FIXTURE_ROOT / "McpFull - Fixture" / "arrangement_state.json").read_text()
    )["blocks"]
    arr = ov["arrangement"]
    assert arr["block_count"] == len(blocks)
    assert arr["blocks"][0]["confidence"] is None
    assert arr["field_sources"]
    assert all(v in _FIELD_SOURCE_VOCAB for v in arr["field_sources"].values())


def test_overview_arrangement_present_on_every_song() -> None:
    # arrangement_state.json is one of the 9 required top-level files (v3.6
    # item 9 dropped the pre-v3.2 degraded/absent path) — the block is always
    # present, on the degenerate fixture too.
    ov = _overview("McpDegenerate - Fixture")
    assert "arrangement" in ov
    arr = ov["arrangement"]
    assert arr["block_count"] == 3
    assert "available" not in arr


def test_overview_partial_still_errors() -> None:
    from loaders import MissingTopLevelFileError

    with pytest.raises(MissingTopLevelFileError):
        serializers.build_song_overview("McpPartial - Fixture", root=FIXTURE_ROOT)


def test_overview_gesture_impact_time_present_and_null() -> None:
    full = _overview("McpFull - Fixture")
    # McpFull should have impact_time present on at least one gesture
    rows = full["gestures"]["rows"]
    assert any(r.get("impact_time") is not None for r in rows)


def test_overview_brief_scope_is_compact_and_omits_prose() -> None:
    ov = serializers.build_song_overview("McpFull - Fixture", root=FIXTURE_ROOT, scope="brief")
    # size target: under ~1000 tokens -> ~4000 bytes
    size = len(json.dumps(ov, indent=2, ensure_ascii=False).encode("utf-8"))
    assert size <= 4000, f"brief overview too large: {size} bytes"
    # sections in brief have only section_id (no description)
    assert all("description" not in r for r in ov["sections"]["rows"])
    # human_hints in brief is compact (total_hints only)
    assert "total_hints" in ov["human_hints"] and isinstance(ov["human_hints"]["total_hints"], int)
    # gestures in brief only include gesture_id and impact_time
    for r in ov["gestures"]["rows"]:
        assert set(r.keys()) <= {"gesture_id", "impact_time"}

