from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


EVENT_TOLERANCE_SECONDS = 1.5


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _annotation_path(song_name: str) -> Path:
    return _repo_root() / "benchmark_annotations" / f"{song_name}.json"


def _load_threshold_profiles() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "contracts" / "event_threshold_profiles.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _interval_overlap_ratio(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    overlap = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    duration = max(a_end - a_start, b_end - b_start, 1e-6)
    return overlap / duration


def benchmark_event_outputs(paths: SongPaths, merged_payload: dict, genre_result: dict | None = None) -> dict[str, Any]:
    annotation_path = _annotation_path(paths.song_name)
    report_path = paths.artifact("validation", "event_benchmark.json")
    profiles = _load_threshold_profiles()
    selected_profile = profiles["default_profile"]
    if genre_result and genre_result.get("genres"):
        label = str(genre_result["genres"][0]).casefold().replace(" ", "_")
        if label in profiles.get("profiles", {}):
            selected_profile = label

    base_report = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "selected_profile": selected_profile,
        "annotation_file": str(annotation_path),
        "generated_from": {
            "machine_events_file": str(paths.artifact("event_inference", "events.machine.json")),
            "timeline_file": str(paths.song_output_dir / "song_event_timeline.json"),
        },
    }

    if not annotation_path.exists():
        report = {
            **base_report,
            "status": "skipped",
            "reason": "No benchmark annotation file exists for this song.",
            "matched": 0,
            "missed": 0,
            "false_positives": 0,
            "details": [],
        }
        write_json(report_path, report)
        return report

    annotation_payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    if str(annotation_payload.get("annotation_status", "")).lower() != "reviewed":
        report = {
            **base_report,
            "status": "skipped",
            "reason": f"Annotation status is {annotation_payload.get('annotation_status', 'unknown')}.",
            "matched": 0,
            "missed": 0,
            "false_positives": 0,
            "details": [],
        }
        write_json(report_path, report)
        return report

    expected = [dict(row) for row in annotation_payload.get("events", [])]
    actual = [dict(row) for row in merged_payload.get("events", [])]
    matched = 0
    used_actual_indices: set[int] = set()
    details: list[dict[str, Any]] = []
    for expected_event in expected:
        best_index = None
        best_score = -1.0
        for index, actual_event in enumerate(actual):
            if index in used_actual_indices:
                continue
            if str(expected_event.get("type")) != str(actual_event.get("type")):
                continue
            start_delta = abs(float(expected_event["start_time"]) - float(actual_event["start_time"]))
            end_delta = abs(float(expected_event["end_time"]) - float(actual_event["end_time"]))
            if start_delta > EVENT_TOLERANCE_SECONDS and end_delta > EVENT_TOLERANCE_SECONDS:
                continue
            overlap = _interval_overlap_ratio(
                float(expected_event["start_time"]),
                float(expected_event["end_time"]),
                float(actual_event["start_time"]),
                float(actual_event["end_time"]),
            )
            if overlap > best_score:
                best_score = overlap
                best_index = index
        if best_index is None:
            details.append({"match_type": "missed", "expected": expected_event})
            continue
        used_actual_indices.add(best_index)
        matched += 1
        actual_event = actual[best_index]
        details.append(
            {
                "match_type": "matched",
                "expected": expected_event,
                "actual": {
                    "id": actual_event.get("id"),
                    "type": actual_event.get("type"),
                    "start_time": actual_event.get("start_time"),
                    "end_time": actual_event.get("end_time"),
                },
                "overlap_ratio": round(best_score, 6),
            }
        )

    false_positives = 0
    for index, actual_event in enumerate(actual):
        if index in used_actual_indices:
            continue
        false_positives += 1
        details.append({"match_type": "false_positive", "actual": actual_event})

    report = {
        **base_report,
        "status": "passed" if (len(expected) == matched and false_positives == 0) else "failed",
        "matched": matched,
        "missed": len(expected) - matched,
        "false_positives": false_positives,
        "details": details,
    }
    write_json(report_path, report)
    return report