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
    "vocal_spotlight": "Keep the visual focus intimate and voice-led rather than rhythm-led.",
    "vocal_tail": "Let the cue decay or hand off gently as the vocal energy falls away.",
    "groove_loop": "Maintain stable pulse-oriented lighting rather than forcing large structural motion.",
    "atmospheric_plateau": "Keep the cue spacious, restrained, and texture-focused.",
    "percussion_break": "Lean into drum-led motion and keep harmonic color restrained while percussion carries the scene.",
    "instrumental_bed": "Treat the section as accompaniment-led space with texture and support rather than lead-vocal focus.",
}


# v1.1 item 4.1 — a drop is one gesture with typed sub-phases, not a scatter of
# independent point events. In the exported timeline (the compact consumer
# projection) a build -> drop -> post_drop run collapses into one composite row
# whose `phases[]` cover its span contiguously. A build with no resolving drop
# becomes a composite with no `impact`/`release` phase (the fake_drop case), so a
# consumer never has to handle phases in two shapes.
_APPROACH_TYPES = {"breakdown", "pause_break", "tension_hold"}
_BUILD_TYPES = {"build"}
_IMPACT_TYPES = {"drop"}
_RECOVERY_TYPES = {"post_drop", "energy_reset"}
_UNRESOLVED_TYPES = {"fake_drop", "no_drop_plateau"}
_COMPOSITE_WINDOW_S = 8.0


def _phase(name: str, start: float, end: float, intensity: float) -> dict[str, Any]:
    return {
        "phase": name,
        "start_time": round(float(start), 6),
        "end_time": round(float(max(end, start)), 6),
        "intensity": round(float(max(0.0, min(1.0, intensity))), 6),
    }


def _fold_composites(events: list[dict]) -> list[dict]:
    """Collapse build/drop/post_drop (or build/fake_drop) runs into composites."""
    events = sorted(events, key=lambda row: float(row["start_time"]))
    consumed: set[str] = set()
    result: list[dict] = []

    for anchor in events:
        anchor_type = str(anchor["type"])
        if anchor["id"] in consumed or anchor_type not in (_IMPACT_TYPES | _UNRESOLVED_TYPES):
            continue
        anchor_start = float(anchor["start_time"])

        preceding = [
            candidate for candidate in events
            if candidate["id"] not in consumed
            and 0.0 <= anchor_start - float(candidate["end_time"]) <= _COMPOSITE_WINDOW_S
            and str(candidate["type"]) in (_BUILD_TYPES | _APPROACH_TYPES)
        ]
        following = [
            candidate for candidate in events
            if candidate["id"] not in consumed
            and 0.0 <= float(candidate["start_time"]) - float(anchor["end_time"]) <= _COMPOSITE_WINDOW_S
            and str(candidate["type"]) in _RECOVERY_TYPES
        ]
        builds = [candidate for candidate in preceding if str(candidate["type"]) in _BUILD_TYPES]
        approaches = [candidate for candidate in preceding if str(candidate["type"]) in _APPROACH_TYPES]

        if anchor_type in _UNRESOLVED_TYPES and not builds:
            # A bare unresolved marker with no build is not a composite gesture.
            continue

        members = approaches + builds + [anchor] + following
        for member in members:
            consumed.add(member["id"])

        phases: list[dict] = []
        for approach in approaches:
            phases.append(_phase("approach", approach["start_time"], approach["end_time"], approach["intensity"]))
        for build in builds:
            phases.append(_phase("build", build["start_time"], build["end_time"], build["intensity"]))
        if builds:
            tension_start = max(float(build["end_time"]) for build in builds)
            phases.append(_phase("tension", tension_start, anchor_start, min(1.0, float(anchor["intensity"]) + 0.1)))
        if anchor_type in _IMPACT_TYPES:
            phases.append(_phase("impact", anchor_start, anchor["end_time"], anchor["intensity"]))
            for recovery in following:
                phases.append(_phase("release", recovery["start_time"], recovery["end_time"], recovery["intensity"]))
        # unresolved -> no impact/release phase

        phases.sort(key=lambda row: row["start_time"])
        overall_start = min(float(member["start_time"]) for member in members)
        overall_end = max(float(member["end_time"]) for member in members)
        composite = dict(anchor)
        composite["id"] = f"composite_{anchor['id']}"
        composite["start_time"] = round(overall_start, 6)
        composite["end_time"] = round(overall_end, 6)
        composite["composite"] = True
        composite["phases"] = phases
        composite["member_event_ids"] = [member["id"] for member in members]
        composite["summary"] = (
            "Composite drop gesture: " + " → ".join(phase["phase"] for phase in phases)
            if anchor_type in _IMPACT_TYPES
            else "Composite build with no resolving drop (withheld release)."
        )
        result.append(composite)

    # Carry through every event that was not folded into a composite.
    for event in events:
        if event["id"] not in consumed:
            result.append(event)
    return sorted(result, key=lambda row: float(row["start_time"]))


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

    compact_events = _fold_composites(compact_events)

    payload = {
        "schema_version": "1.1",
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "llm-friendly-event-timeline-v2",
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
        for phase in event.get("phases", []):
            lines.append(
                f"  phase {phase['phase']}: {float(phase['start_time']):.2f}s-{float(phase['end_time']):.2f}s intensity={float(phase['intensity']):.2f}"
            )
    timeline_md_path = paths.timeline_md_path
    ensure_directory(paths.song_validation_dir)
    timeline_md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "timeline_json": str(timeline_json_path),
        "timeline_md": str(timeline_md_path),
    }