from __future__ import annotations

from collections import defaultdict
from typing import Any

from analyzer.event_contracts import validate_song_event_payload
from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


DEFAULT_THRESHOLD_PROFILE = {
    "name": "default",
    "transition": {
        "build_energy_delta": 0.08,
        "build_tension_mean": 0.25,
        "build_energy_mean": 0.45,
        "breakdown_energy_delta": -0.2,
        "breakdown_density_delta": -0.15,
        "drop_energy_delta": 0.22,
        "drop_onset_min": 0.55,
        "drop_bass_min": 0.3,
        "drop_accent_min": 0.3,
        "fake_drop_tension_mean": 0.45,
        "impact_intensity_min": 0.75,
        "pause_gap_seconds": 0.75,
        "pause_energy_max": 0.35
    },
    "state": {
        "groove_energy_min": 0.45,
        "groove_bass_min": 0.35,
        "groove_volatility_max": 0.25,
        "atmo_energy_max": 0.35,
        "atmo_onset_max": 0.3,
        "atmo_volatility_max": 0.2,
        "tension_mean_min": 0.45,
        "no_drop_energy_min": 0.35,
        "no_drop_energy_max": 0.6
    }
}


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _event_window_refs(rows: list[dict], section: dict | None = None) -> list[dict]:
    if not rows:
        return []
    references = [
        {
            "layer": "event_features",
            "start_time": round(float(rows[0]["start_time"]), 6),
            "end_time": round(float(rows[-1]["end_time"]), 6),
            "ref": f"beats:{rows[0]['beat']}-{rows[-1]['beat']}",
            "metric_names": [
                "energy_score",
                "symbolic_density",
                "harmonic_tension_proxy",
            ],
        }
    ]
    if section is not None:
        references.append(
            {
                "layer": "sections",
                "start_time": round(float(section["start"]), 6),
                "end_time": round(float(section["end"]), 6),
                "ref": str(section["section_id"]),
                "metric_names": ["section_character", "confidence"],
            }
        )
    return references


def _build_event(
    *,
    event_id: str,
    event_type: str,
    rows: list[dict],
    section: dict | None,
    confidence: float,
    intensity: float,
    summary: str,
    rule_names: list[str],
    metrics: list[dict],
    notes: str,
    candidates: list[dict] | None = None,
) -> dict[str, Any]:
    event = {
        "id": event_id,
        "type": event_type,
        "created_by": "analyzer_rule_engine",
        "start_time": round(float(rows[0]["start_time"]), 6),
        "end_time": round(float(rows[-1]["end_time"]), 6),
        "confidence": round(confidence, 6),
        "intensity": round(intensity, 6),
        "evidence": {
            "summary": summary,
            "source_windows": _event_window_refs(rows, section),
            "metrics": metrics,
            "reasons": [summary],
            "rule_names": rule_names,
        },
        "notes": notes,
        "source_layers": ["event_features", "sections"],
    }
    if section is not None:
        event["section_id"] = section.get("section_id")
        event["section_name"] = section.get("section_character") or section.get("label")
    if candidates:
        event["candidates"] = candidates
    return event


def _merge_anchor_rows(anchor_rows: list[dict]) -> list[list[dict]]:
    if not anchor_rows:
        return []
    merged: list[list[dict]] = [[anchor_rows[0]]]
    for row in anchor_rows[1:]:
        previous = merged[-1][-1]
        contiguous = int(row["beat"]) == int(previous["beat"]) + 1
        same_section = row.get("section_id") == previous.get("section_id")
        if contiguous and same_section:
            merged[-1].append(row)
        else:
            merged.append([row])
    return merged


def _state_section_rows(features: list[dict], section_id: str) -> list[dict]:
    return [row for row in features if row.get("section_id") == section_id]



__all__ = ['_section_for_time', '_clamp01', '_mean', '_event_window_refs', '_build_event', '_merge_anchor_rows', '_state_section_rows']
