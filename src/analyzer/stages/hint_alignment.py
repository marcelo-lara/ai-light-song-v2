from __future__ import annotations

from pathlib import Path

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


def _overlap_seconds(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def _load_json_if_exists(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return read_json(path)


def build_human_hints_alignment(paths: SongPaths) -> dict | None:
    reference_path = paths.reference("human", "human_hints.json")
    if reference_path is None or not reference_path.exists():
        return None

    hints_payload = read_json(reference_path)
    sections_payload = _load_json_if_exists(paths.sections_output_path) or []
    timeline_payload = _load_json_if_exists(paths.timeline_output_path) or {"events": []}
    patterns_payload = _load_json_if_exists(paths.artifact("layer_d_patterns.json")) or {"patterns": []}
    harmonic_payload = _load_json_if_exists(paths.artifact("layer_a_harmonic.json")) or {"chords": []}

    hints = hints_payload.get("human_hints", [])
    sections = sections_payload if isinstance(sections_payload, list) else sections_payload.get("sections", [])
    events = timeline_payload.get("events", []) if isinstance(timeline_payload, dict) else []
    patterns = patterns_payload.get("patterns", []) if isinstance(patterns_payload, dict) else []
    chords = harmonic_payload.get("chords", []) if isinstance(harmonic_payload, dict) else []

    alignment_rows = []
    with_section_overlap = 0
    with_event_overlap = 0
    with_pattern_overlap = 0
    with_chord_overlap = 0

    for hint in hints:
        hint_start = float(hint["start_time"])
        hint_end = float(hint["end_time"])

        overlapping_sections = []
        for section in sections:
            section_start = float(section["start"])
            section_end = float(section["end"])
            overlap = _overlap_seconds(hint_start, hint_end, section_start, section_end)
            if overlap <= 0:
                continue
            overlapping_sections.append({
                "label": section.get("label"),
                "start": round(section_start, 6),
                "end": round(section_end, 6),
                "overlap_seconds": round(overlap, 6),
            })

        overlapping_events = []
        event_type_counts: dict[str, int] = {}
        for event in events:
            event_start = float(event["start_time"])
            event_end = float(event["end_time"])
            overlap = _overlap_seconds(hint_start, hint_end, event_start, event_end)
            if overlap <= 0:
                continue
            event_type = str(event.get("type", "unknown"))
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            overlapping_events.append({
                "id": event.get("id"),
                "type": event_type,
                "start_time": round(event_start, 6),
                "end_time": round(event_end, 6),
                "section_name": event.get("section_name"),
                "overlap_seconds": round(overlap, 6),
            })

        overlapping_patterns = []
        for pattern in patterns:
            for occurrence in pattern.get("occurrences", []):
                occurrence_start = float(occurrence["start_s"])
                occurrence_end = float(occurrence["end_s"])
                overlap = _overlap_seconds(hint_start, hint_end, occurrence_start, occurrence_end)
                if overlap <= 0:
                    continue
                overlapping_patterns.append({
                    "pattern_id": pattern.get("id"),
                    "pattern_label": pattern.get("label"),
                    "sequence": occurrence.get("sequence") or pattern.get("sequence"),
                    "start_s": round(occurrence_start, 6),
                    "end_s": round(occurrence_end, 6),
                    "mismatch_count": occurrence.get("mismatch_count"),
                    "overlap_seconds": round(overlap, 6),
                })

        overlapping_chords = []
        for chord in chords:
            chord_start = float(chord["time"])
            chord_end = float(chord["end_s"])
            overlap = _overlap_seconds(hint_start, hint_end, chord_start, chord_end)
            if overlap <= 0:
                continue
            overlapping_chords.append({
                "chord": chord.get("chord"),
                "start_s": round(chord_start, 6),
                "end_s": round(chord_end, 6),
                "confidence": chord.get("confidence"),
                "overlap_seconds": round(overlap, 6),
            })

        if overlapping_sections:
            with_section_overlap += 1
        if overlapping_events:
            with_event_overlap += 1
        if overlapping_patterns:
            with_pattern_overlap += 1
        if overlapping_chords:
            with_chord_overlap += 1

        primary_section = max(overlapping_sections, key=lambda row: row["overlap_seconds"], default=None)
        alignment_rows.append({
            "hint_id": hint.get("id"),
            "title": hint.get("title", ""),
            "start_time": round(hint_start, 6),
            "end_time": round(hint_end, 6),
            "summary": hint.get("summary", ""),
            "lighting_hint": hint.get("lighting_hint", ""),
            "primary_section_label": primary_section.get("label") if primary_section else None,
            "section_overlap_count": len(overlapping_sections),
            "event_overlap_count": len(overlapping_events),
            "pattern_overlap_count": len(overlapping_patterns),
            "chord_overlap_count": len(overlapping_chords),
            "event_type_counts": event_type_counts,
            "overlapping_sections": overlapping_sections,
            "overlapping_events": overlapping_events[:12],
            "overlapping_patterns": overlapping_patterns[:12],
            "overlapping_chords": overlapping_chords[:12],
        })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "human_hints_file": str(reference_path),
            "sections_file": str(paths.sections_output_path),
            "event_timeline_file": str(paths.timeline_output_path),
            "patterns_file": str(paths.artifact("layer_d_patterns.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
        },
        "summary": {
            "hint_count": len(alignment_rows),
            "hints_with_section_overlap": with_section_overlap,
            "hints_with_event_overlap": with_event_overlap,
            "hints_with_pattern_overlap": with_pattern_overlap,
            "hints_with_chord_overlap": with_chord_overlap,
            "hints_without_event_overlap": [row["hint_id"] for row in alignment_rows if row["event_overlap_count"] == 0],
            "hints_without_pattern_overlap": [row["hint_id"] for row in alignment_rows if row["pattern_overlap_count"] == 0],
        },
        "alignments": alignment_rows,
    }

    json_path = paths.song_validation_dir / "human_hints_alignment.json"
    md_path = paths.song_validation_dir / "human_hints_alignment.md"
    write_json(json_path, payload)

    lines = [
        f"# Human Hints Alignment: {paths.song_name}",
        "",
        f"Hints reviewed: {len(alignment_rows)}",
        f"Hints with overlapping sections: {with_section_overlap}",
        f"Hints with overlapping events: {with_event_overlap}",
        f"Hints with overlapping patterns: {with_pattern_overlap}",
        f"Hints with overlapping chords: {with_chord_overlap}",
        "",
    ]
    for row in alignment_rows:
        lines.append(f"## {row['hint_id']} {row['title']}")
        lines.append("")
        lines.append(f"- Window: {row['start_time']}s -> {row['end_time']}s")
        if row["primary_section_label"]:
            lines.append(f"- Primary section: {row['primary_section_label']}")
        lines.append(f"- Event overlap count: {row['event_overlap_count']}")
        lines.append(f"- Pattern overlap count: {row['pattern_overlap_count']}")
        lines.append(f"- Chord overlap count: {row['chord_overlap_count']}")
        if row["event_type_counts"]:
            lines.append(f"- Event types: {row['event_type_counts']}")
        if row["summary"]:
            lines.append(f"- Human summary: {row['summary']}")
        lines.append("")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "payload": payload,
    }