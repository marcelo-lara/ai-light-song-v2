"""Tests for sparse-event cap behavior (D3.4).

These tests create a temporary minimal fixture when necessary to exercise the
sparse-cap-hit path without modifying the committed fixtures.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from serializers import build_detail, DetailScopeError


def _write_json(p: Path, obj: Any) -> None:
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def test_over_cap_still_includes_sparse_events() -> None:
    # Over the dense cap (6 s) returns structural view with drum events present
    resp = build_detail("McpFull - Fixture", start_ms=0, end_ms=6000, root=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "analysis")
    assert resp["dense"] is None
    drum = resp["structural"].get("drum_events")
    assert drum is not None
    assert isinstance(drum.get("rows"), list)


def test_sparse_cap_hit_reports_withheld() -> None:
    # Create a temporary analysis root with a song carrying > SPARSE_ROW_CAP drum events
    from serializers import SPARSE_ROW_CAP
    TMP = Path(tempfile.mkdtemp())
    analysis = TMP / "analysis"
    song = analysis / "BigDrums - Temp"
    song.mkdir(parents=True)

    # Minimal required top-level files
    _write_json(song / "info.json", {"song_name": "BigDrums - Temp", "bpm": 120, "duration": 60})
    _write_json(song / "beats.json", {"beats": [] , "field_sources": {}})
    _write_json(song / "sections.json", {"sections": [{"section_id": "s1", "start": 0, "end": 60000, "function_status": "unknown"}], "field_sources": {}})
    _write_json(song / "song_event_timeline.json", {"events": [], "field_sources": {}})
    _write_json(song / "hints.json", {"sections": [], "field_sources": {}})

    # Create drum_events with SPARSE_ROW_CAP + 10 rows
    events = []
    for i in range(SPARSE_ROW_CAP + 10):
        events.append({"time": float(i) * 0.01, "event_type": "kick", "confidence": None})
    drum_doc = {
        "schema_version": "3.0",
        "song_name": "BigDrums - Temp",
        "field_sources": {"time": "omnizart", "event_type": "omnizart", "confidence": "omnizart"},
        "summary": {"event_count": len(events)},
        "events": events,
    }
    _write_json(song / "drum_events.json", drum_doc)

    # Call build_detail for the full section; it should report sparse_withheld
    resp = build_detail("BigDrums - Temp", section_id="s1", root=analysis)
    drum = resp["structural"].get("drum_events")
    assert drum is not None
    assert drum.get("sparse_withheld") is not None
    assert drum["sparse_withheld"]["observed_rows"] == SPARSE_ROW_CAP + 10
    assert drum["sparse_withheld"]["cap_rows"] == SPARSE_ROW_CAP
