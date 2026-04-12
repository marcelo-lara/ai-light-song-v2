from __future__ import annotations

from typing import Any

from analyzer.io import ensure_directory, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


LIGHTING_HINTS = {
    "drop_explode": "Use a full-energy release cue with broad intensity jump and short-lived impact emphasis.",
    "drop_groove": "Favor sustained motion and groove continuity over a single flash-heavy accent.",
    "drop_punch": "Keep the release compact and impact-forward rather than fully blooming.",
    "soft_release": "Use a smoother landing with controlled intensity and less abrupt contrast.",
    "anthem_call": "Frame the phrase as a crowd-facing focal moment with space for response.",
    "hook_phrase": "Support recognisable phrase recall with repeatable but still editable cue language.",
    "groove_loop": "Maintain stable pulse-oriented lighting rather than forcing large structural motion.",
    "atmospheric_plateau": "Keep the cue spacious, restrained, and texture-focused.",
}


def export_event_timeline(paths: SongPaths, merged_payload: dict) -> dict[str, Any]:
    compact_events = []
    for event in merged_payload.get("events", []):
        provenance = "human-edited" if "human_override" in event else "machine-only"
        compact_events.append(
            {
                "id": event["id"],
                "type": event["type"],
                "start_time": event["start_time"],
                "end_time": event["end_time"],
                "confidence": event["confidence"],
                "intensity": event["intensity"],
                "section_id": event.get("section_id"),
                "section_name": event.get("section_name"),
                "provenance": provenance,
                "summary": event.get("notes"),
                "created_by": event.get("created_by", "analyzer_unknown_source"),
                "evidence_summary": event.get("evidence", {}).get("summary"),
                "lighting_hint": LIGHTING_HINTS.get(str(event["type"]), "Use the event as a high-level musical cue, not a fixture-specific instruction."),
                "evidence_ref": {
                    "machine_event_id": event["id"],
                    "machine_file": str(paths.artifact("event_inference", "events.machine.json")),
                },
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "llm-friendly-event-timeline-v1",
            "dependencies": {
                "machine_events_file": str(paths.artifact("event_inference", "events.machine.json")),
                "review_file": str(paths.review_json_path),
                "overrides_file": str(paths.overrides_path),
            },
        },
        "events": compact_events,
    }
    timeline_json_path = paths.timeline_output_path
    write_json(timeline_json_path, payload)

    lines = [
        f"# Song Event Timeline: {paths.song_name}",
        "",
        "## Events",
        "",
    ]
    for event in compact_events:
        lines.append(
            f"- {event['type']} {float(event['start_time']):.2f}s-{float(event['end_time']):.2f}s confidence={float(event['confidence']):.2f} intensity={float(event['intensity']):.2f} provenance={event['provenance']}"
        )
        lines.append(f"  note: {event['summary']}")
        lines.append(f"  evidence: {event['evidence_summary']}")
        lines.append(f"  lighting hint: {event['lighting_hint']}")
    timeline_md_path = paths.timeline_md_path
    ensure_directory(paths.song_validation_dir)
    timeline_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "timeline_json": str(timeline_json_path),
        "timeline_md": str(timeline_md_path),
    }