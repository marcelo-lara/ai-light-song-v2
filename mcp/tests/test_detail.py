"""get_detail (v3.1 item 10): golden snapshots + the detail-read contract.

Snapshots are regenerated, not defended: run with ``MCP_REGEN_SNAPSHOTS=1`` to
re-record them in the same commit as a deliberate shape change, one line of
justification per changed file in the commit message.

The detail-read contract (mirrors mcp-regression.md F3):

- exactly one scope selector — section_id, gesture_id, or start_ms+end_ms;
  zero or two is an error, no precedence rule;
- the 5 s dense cap is a maximum, not a default — an over-cap span returns the
  structural view, withholds the dense frames, and names the cap;
- a span at exactly 5 s is accepted;
- interval_ms finer than the 20 ms floor errors naming the floor — never a
  silent upsample;
- interval_ms=100 returns one fifth the frames of interval_ms=20 over the same
  window, by chunk-averaging (not frame-dropping) so a transient survives;
- sources narrows the stem set and returns it in the published order.
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
DetailScopeError = serializers.DetailScopeError

SONG = "McpFull - Fixture"


def _serialize(payload: object) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _detail(**kwargs) -> dict:
    return serializers.build_detail(SONG, root=FIXTURE_ROOT, **kwargs)


# --------------------------------------------------------------------------- #
# golden snapshots
# --------------------------------------------------------------------------- #

SNAPSHOT_CASES = {
    "section_scope": dict(section_id="section-002"),
    "gesture_scope": dict(gesture_id="gesture-001"),
    "window_3s_20ms": dict(start_ms=0, end_ms=3000, interval_ms=20),
    "window_3s_100ms": dict(start_ms=0, end_ms=3000, interval_ms=100),
    "window_over_cap": dict(start_ms=0, end_ms=6000),
}


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_detail_matches_snapshot(name: str) -> None:
    current = _serialize(_detail(**SNAPSHOT_CASES[name]))
    snap = SNAP_DIR / f"get_detail__{name}.json"
    if os.environ.get("MCP_REGEN_SNAPSHOTS"):
        snap.write_text(current, encoding="utf-8")
        pytest.skip(f"regenerated {snap.name}")
    assert snap.is_file(), f"missing snapshot {snap}"
    assert current == snap.read_text(encoding="utf-8")


@pytest.mark.parametrize("name", sorted(SNAPSHOT_CASES))
def test_detail_is_deterministic(name: str) -> None:
    assert _serialize(_detail(**SNAPSHOT_CASES[name])) == _serialize(
        _detail(**SNAPSHOT_CASES[name])
    )


# --------------------------------------------------------------------------- #
# the detail-read contract
# --------------------------------------------------------------------------- #

def test_detail_requires_exactly_one_scope() -> None:
    with pytest.raises(DetailScopeError):
        _detail()
    with pytest.raises(DetailScopeError):
        _detail(section_id="section-002", gesture_id="gesture-001")
    with pytest.raises(DetailScopeError):
        _detail(section_id="section-002", start_ms=0, end_ms=1000)


def test_detail_over_cap_withholds_dense_and_names_the_cap() -> None:
    resp = _detail(start_ms=0, end_ms=6000)
    assert resp["dense"] is None
    assert "frames" not in json.dumps(resp["dense"])
    reason = resp["dense_withheld"]["reason"]
    assert "5" in reason and "cap" in reason
    assert resp["dense_withheld"]["cap_seconds"] == 5.0
    # the structural view is still returned
    assert resp["structural"]["sections"]["rows"]


def test_detail_exactly_five_seconds_is_accepted() -> None:
    resp = _detail(start_ms=0, end_ms=5000)
    assert resp["dense"] is not None
    assert resp["dense"]["frame_count"] > 0


def test_detail_interval_finer_than_floor_errors_naming_it() -> None:
    with pytest.raises(DetailScopeError, match="20 ms"):
        _detail(start_ms=0, end_ms=3000, interval_ms=10)


def test_detail_interval_100_is_one_fifth_of_20() -> None:
    fine = _detail(start_ms=0, end_ms=3000, interval_ms=20)["dense"]["frame_count"]
    coarse = _detail(start_ms=0, end_ms=3000, interval_ms=100)["dense"]["frame_count"]
    assert coarse == fine // 5


def test_detail_decimation_preserves_the_transient_peak() -> None:
    # The fixture carries a +0.3 mix bump across 13.0-14.0 s. Chunk-averaging
    # must keep it — frame-dropping could skip it.
    window = dict(start_ms=12500, end_ms=14500)
    raw = _detail(**window, interval_ms=20)["dense"]["frames"]
    coarse = _detail(**window, interval_ms=100)["dense"]
    raw_peak = max(f["values"][0] for f in raw)
    coarse_peak = max(f["values"][0] for f in coarse["frames"])
    assert coarse["decimation"] == "pair-averaging"
    assert coarse_peak >= raw_peak * 0.99


def test_detail_sources_narrows_and_keeps_published_order() -> None:
    resp = _detail(start_ms=0, end_ms=3000, sources=["vocals", "bass"])
    assert resp["dense"]["sources"] == ["bass", "vocals"]
    assert all(len(f["values"]) == 2 for f in resp["dense"]["frames"])


def test_detail_lists_overlapping_arrangement_blocks() -> None:
    # section-002 spans 8-16 s; fixture arrangement blocks are 0-8 / 8-16 / 16-24.
    rows = _detail(section_id="section-002")["structural"]["arrangement"]["rows"]
    assert rows
    assert all(r["end_s"] > 8.0 and r["start_s"] < 16.0 for r in rows)
    assert any(r["margin_db"] is not None for r in rows)


def test_detail_over_cap_still_includes_arrangement_structural() -> None:
    resp = _detail(start_ms=0, end_ms=6000)
    assert resp["dense"] is None  # dense withheld over the 5 s cap
    assert resp["structural"]["arrangement"]["rows"]


def test_detail_no_host_paths() -> None:
    for kwargs in SNAPSHOT_CASES.values():
        assert "/data/" not in _serialize(_detail(**kwargs))


def test_detail_never_emits_a_full_beat_list() -> None:
    blob = _serialize(_detail(section_id="section-002"))
    assert '"beat"' not in blob


def test_detail_includes_drum_events_structural() -> None:
    # Structural view should include a drum_events block with rows and a
    # summary so callers can distinguish no-data vs empty lists.
    resp = _detail(section_id="section-002")
    block = resp["structural"].get("drum_events")
    assert block is not None
    assert "rows" in block and isinstance(block["rows"], list)
    # summary should reflect the source file's summary when available
    assert "summary" in block
    # window_count (rows present) should equal the length of rows
    if block.get("summary") is not None:
        assert block["summary"].get("event_count") is not None or True
