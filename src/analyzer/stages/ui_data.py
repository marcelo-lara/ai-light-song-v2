from __future__ import annotations

import re

from analyzer.io import read_json, write_json
from analyzer.models import round_schema_float
from analyzer.paths import SongPaths


def _resolve_chord_for_time(time_s: float, chord_events: list[dict]) -> str | None:
    previous_label: str | None = None
    for event in chord_events:
        start_s = float(event["time"])
        end_s = float(event["end_s"])
        label = str(event["chord"])
        if start_s <= time_s < end_s:
            return label
        if time_s >= start_s:
            previous_label = label
        if time_s < start_s:
            break
    return previous_label or (str(chord_events[0]["chord"]) if chord_events else None)


def _section_index_prefix(section_id: str | None) -> str:
    if not section_id:
        return ""
    match = re.search(r"(\d+)", str(section_id))
    return f"{match.group(1)} " if match else ""


def _format_section_label(section: dict) -> str:
    """`<index> <Label> (<confidence>)`, e.g. `"003 Chorus (0.80)"`.

    `function_status == "unknown"` means allin1's name for this section is not
    trustworthy (constitution §2 — an honest `unknown` beats a confident wrong
    label), so the raw, un-title-cased label token is shown with an explicit
    `[unverified]` marker rather than a polished name that would read as
    confident. `function_confidence` still displays — it is what made the name
    untrustworthy in aggregate, not a claim being retracted here.
    """
    prefix = _section_index_prefix(section.get("section_id"))
    function = section.get("function")
    confidence = section.get("function_confidence")

    suffix = ""
    if confidence is not None:
        try:
            suffix = f" ({round_schema_float(float(confidence)):.2f})"
        except (TypeError, ValueError):
            suffix = ""

    if section.get("function_status") == "unknown":
        label_text = f"{function or 'unlabeled'} [unverified]"
        return f"{prefix}{label_text}{suffix}"

    label_text = str(function).replace("_", " ").title() if function else "Unlabeled"
    return f"{prefix}{label_text}{suffix}"


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _section_description(section: dict, occurrence: int) -> str:
    """One sentence built only from this section's own measured fields — its
    functional label, its position among same-labelled sections, its duration,
    and `same_label_as` — never an invented mood or energy claim."""
    function = section.get("function")
    try:
        duration_s = round(float(section["end"]) - float(section["start"]), 1)
    except (TypeError, ValueError, KeyError):
        duration_s = None
    duration_text = f"{duration_s:.1f}s" if duration_s is not None else "of unknown length"

    if not function or section.get("function_status") == "unknown":
        return f"Unverified section, {duration_text} — allin1's label for this song is not trustworthy."

    label_text = str(function).replace("_", " ")
    ordinal = _ordinal(occurrence)
    if section.get("same_label_as") is None:
        return f"The {ordinal} {label_text}, {duration_text} long."
    return f"The {ordinal} {label_text}, {duration_text} long, same label as the first {label_text}."


def build_ui_data(paths: SongPaths) -> dict[str, str]:
    beats_payload = read_json(paths.artifact("essentia", "beats.json"))
    harmonic_payload = read_json(paths.artifact("layer_a_harmonic.json"))
    sections_payload = read_json(paths.artifact("section_segmentation", "sections.json"))

    # v1.1 item 3.2 (B5) — validate the join key up front. The top-level section
    # list must be joinable to the segmentation list on section_id, never on
    # array position.
    raw_sections = list(sections_payload.get("sections", []))
    section_ids = [section.get("section_id") for section in raw_sections]
    if any(not section_id for section_id in section_ids):
        raise ValueError("section_segmentation/sections.json has a section without a section_id; cannot build a joinable UI section list")
    if len(set(section_ids)) != len(section_ids):
        raise ValueError(f"section_segmentation/sections.json has duplicate section_id values: {section_ids}")

    chord_events = harmonic_payload.get("chords", [])
    beat_points = beats_payload.get("beats", [])
    beat_rows = [
        {
            "time": round_schema_float(float(beat["time"])),
            "beat": int(beat["beat_in_bar"]),
            "bar": int(beat["bar"]),
            "chord": _resolve_chord_for_time(float(beat["time"]), chord_events),
            "type": str(beat["type"]),
            "confidence": beat.get("confidence"),
        }
        for beat in beat_points
    ]

    occurrence_counts: dict[str, int] = {}
    section_rows = []
    for section in raw_sections:
        function = section.get("function")
        if function:
            occurrence_counts[function] = occurrence_counts.get(function, 0) + 1
        section_rows.append(
            {
                "section_id": section["section_id"],
                "start": round_schema_float(float(section["start"])),
                "end": round_schema_float(float(section["end"])),
                "label": _format_section_label(section),
                "description": _section_description(section, occurrence_counts.get(function, 0)),
                "confidence": section.get("confidence"),
            }
        )

    beats_output_path = paths.beats_output_path
    sections_output_path = paths.sections_output_path
    write_json(beats_output_path, beat_rows)
    write_json(sections_output_path, section_rows)
    return {
        "beats": str(beats_output_path),
        "sections": str(sections_output_path),
    }
