from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from analyzer.event_contracts import normalize_event_type, validate_song_event_payload
from analyzer.io import ensure_directory, read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


CONFIDENCE_BANDS = {
    "high": 0.8,
    "medium": 0.55,
}


def _confidence_band(confidence: float) -> str:
    if confidence >= CONFIDENCE_BANDS["high"]:
        return "high"
    if confidence >= CONFIDENCE_BANDS["medium"]:
        return "medium"
    return "low"


def _is_ambiguous(event: dict) -> bool:
    candidates = event.get("candidates", [])
    if len(candidates) < 2:
        return False
    top = float(candidates[0].get("confidence", 0.0))
    second = float(candidates[1].get("confidence", 0.0))
    return abs(top - second) < 0.12


def _default_overrides_payload(paths: SongPaths, machine_file: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "event-overrides-template-v1",
            "dependencies": {
                "machine_events_file": str(machine_file),
            },
        },
        "notes": "Add operations to confirm, delete, retime, relabel, or annotate machine events without editing source artifacts.",
        "operations": [],
    }


def _load_or_create_overrides(paths: SongPaths, machine_file: Path) -> tuple[dict[str, Any], Path]:
    overrides_path = paths.overrides_path
    ensure_directory(paths.song_validation_dir)
    if overrides_path.exists():
        payload = read_json(overrides_path)
        if isinstance(payload, dict):
            return payload, overrides_path
    payload = _default_overrides_payload(paths, machine_file)
    write_json(overrides_path, payload)
    return payload, overrides_path


def apply_event_overrides(machine_payload: dict, overrides_payload: dict) -> dict[str, Any]:
    machine_events = [deepcopy(event) for event in machine_payload.get("events", [])]
    operations = [dict(row) for row in overrides_payload.get("operations", [])]
    operations_by_id: dict[str, list[dict[str, Any]]] = {}
    for operation in operations:
        event_id = str(operation.get("event_id", ""))
        if not event_id:
            continue
        operations_by_id.setdefault(event_id, []).append(operation)

    merged_events: list[dict[str, Any]] = []
    for event in machine_events:
        working = deepcopy(event)
        deleted = False
        for operation in operations_by_id.get(str(event["id"]), []):
            action = str(operation.get("action", "")).strip().lower()
            if action == "confirm":
                working["human_override"] = {"status": "confirmed", "notes": str(operation.get("note", "Confirmed during review."))}
            elif action == "delete":
                deleted = True
                break
            elif action == "retime":
                if "start_time" in operation:
                    working["start_time"] = float(operation["start_time"])
                if "end_time" in operation:
                    working["end_time"] = float(operation["end_time"])
                working["human_override"] = {
                    "status": "retimed",
                    "updated_start_time": float(working["start_time"]),
                    "updated_end_time": float(working["end_time"]),
                    "notes": str(operation.get("note", "Retimed during review.")),
                }
            elif action == "relabel":
                updated_type = normalize_event_type(str(operation.get("type", working["type"])))
                working["type"] = updated_type
                working["human_override"] = {
                    "status": "relabeled",
                    "updated_type": updated_type,
                    "notes": str(operation.get("note", "Relabeled during review.")),
                }
            elif action == "annotate":
                appended_note = str(operation.get("note", "Reviewed note."))
                working["notes"] = f"{working['notes']} {appended_note}".strip()
                working["human_override"] = {
                    "status": "annotated",
                    "notes": appended_note,
                }
        if deleted:
            continue
        merged_events.append(working)

    merged_payload = {
        "schema_version": machine_payload["schema_version"],
        "song_name": machine_payload["song_name"],
        "generated_from": {
            **machine_payload.get("generated_from", {}),
            "override_file": overrides_payload.get("generated_from", {}).get("dependencies", {}).get("machine_events_file"),
        },
        "review_status": "merged",
        "notes": "Merged machine events with deterministic override application.",
        "threshold_profile": machine_payload.get("threshold_profile", "default"),
        "metadata": dict(machine_payload.get("metadata", {})),
        "events": merged_events,
    }
    return validate_song_event_payload(merged_payload)


def generate_event_review(paths: SongPaths, machine_payload: dict) -> dict[str, Any]:
    machine_path = paths.artifact("event_inference", "events.machine.json")
    overrides_payload, overrides_path = _load_or_create_overrides(paths, machine_path)
    merged_payload = apply_event_overrides(machine_payload, overrides_payload)
    merged_payload.setdefault("generated_from", {})["override_file"] = str(overrides_path)

    review_rows = []
    for event in machine_payload.get("events", []):
        confidence = float(event.get("confidence", 0.0))
        review_rows.append(
            {
                "event_id": event["id"],
                "type": event["type"],
                "start_time": event["start_time"],
                "end_time": event["end_time"],
                "confidence": event["confidence"],
                "confidence_band": _confidence_band(confidence),
                "intensity": event["intensity"],
                "section_id": event.get("section_id"),
                "notes": event.get("notes"),
                "ambiguous": _is_ambiguous(event),
                "candidates": event.get("candidates", []),
                "provenance": "machine",
            }
        )

    review_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "event-review-export-v1",
            "dependencies": {
                "machine_events_file": str(machine_path),
                "overrides_file": str(overrides_path),
            },
        },
        "confidence_bands": {
            "high": {"minimum": CONFIDENCE_BANDS["high"]},
            "medium": {"minimum": CONFIDENCE_BANDS["medium"], "maximum": CONFIDENCE_BANDS["high"]},
            "low": {"maximum": CONFIDENCE_BANDS["medium"]},
        },
        "summary": {
            "machine_event_count": len(machine_payload.get("events", [])),
            "merged_event_count": len(merged_payload.get("events", [])),
            "ambiguous_event_count": sum(1 for row in review_rows if row["ambiguous"]),
        },
        "events": review_rows,
        "merged_events_preview": [
            {
                "event_id": event["id"],
                "type": event["type"],
                "start_time": event["start_time"],
                "end_time": event["end_time"],
                "provenance": "human-edited" if "human_override" in event else "machine-only",
            }
            for event in merged_payload.get("events", [])
        ],
    }
    review_json_path = paths.review_json_path
    write_json(review_json_path, review_payload)

    md_lines = [
        f"# Song Event Review: {paths.song_name}",
        "",
        f"Machine events: {review_payload['summary']['machine_event_count']}",
        f"Merged events preview: {review_payload['summary']['merged_event_count']}",
        f"Ambiguous windows: {review_payload['summary']['ambiguous_event_count']}",
        "",
        "## Events",
        "",
    ]
    for row in review_rows:
        md_lines.append(
            f"- {row['event_id']}: {row['type']} {row['start_time']:.2f}s-{row['end_time']:.2f}s confidence={row['confidence']:.2f} band={row['confidence_band']} ambiguous={row['ambiguous']}"
        )
    review_md_path = paths.review_md_path
    ensure_directory(paths.song_validation_dir)
    review_md_path.write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")

    return {
        "review_json": str(review_json_path),
        "review_md": str(review_md_path),
        "overrides": str(overrides_path),
        "merged_payload": merged_payload,
    }