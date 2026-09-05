from __future__ import annotations

import re

from analyzer.io import read_json, write_json
from analyzer.models import round_schema_float
from analyzer.paths import SongPaths


SECTION_DESCRIPTIONS = {
    "ambient_opening": "Restrained opening space with low-volatility motion and room for atmosphere.",
    "vocal_spotlight": "Voice-led section where the vocal contour carries most of the attention and motion.",
    "vocal_lift": "Vocal-led section with stronger energy and emotional lift than a simple spotlight moment.",
    "momentum_lift": "Energy and motion climb together into a more assertive forward push.",
    "flowing_plateau": "Stable mid-energy passage with continuous motion but limited structural shock.",
    "groove_plateau": "Pulse-led section with sustained rhythmic momentum and repeat-driven stability.",
    "instrumental_bed": "Instrument-led passage where accompaniment or synth texture carries the section more than the voice.",
    "percussion_break": "Percussion-dominant pocket with reduced harmonic or vocal material.",
    "contrast_bridge": "Contrast-focused transition where texture or pressure shifts before the next settled state.",
    "focal_lift": "Payoff section where energy, repetition, or phrasing converge into the strongest focal state.",
    "breath_space": "Lower-density breathing room where the arrangement opens up or briefly clears out.",
    "release_tail": "Closing release state where energy tapers and the track settles out.",
}


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


def _format_section_label(
    label: str | None,
    section_id: str | None,
    confidence: float | None,
) -> str:
    label_text = str(label).replace("_", " ").title() if label else "Unlabeled"

    prefix = ""
    if section_id:
        match = re.search(r"(\d+)", str(section_id))
        if match:
            prefix = f"{match.group(1)} "

    suffix = ""
    if confidence is not None:
        try:
            suffix = f" ({round_schema_float(float(confidence)):.2f})"
        except (TypeError, ValueError):
            suffix = ""

    return f"{prefix}{label_text}{suffix}"


def _section_description(section: dict) -> str:
    key = str(section.get("section_character") or section.get("label") or "")
    return SECTION_DESCRIPTIONS.get(key, "")


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
        }
        for beat in beat_points
    ]
    section_rows = [
        {
            "section_id": section["section_id"],
            "start": round_schema_float(float(section["start"])),
            "end": round_schema_float(float(section["end"])),
            "label": _format_section_label(
                section.get("form_role") or section.get("section_character") or section.get("label"),
                section.get("section_id"),
                section.get("confidence"),
            ),
            "form_role": section.get("form_role"),
            "energy_character": section.get("energy_character") or section.get("section_character"),
            "repetition_group": section.get("repetition_group"),
            "confidence": section.get("confidence"),
            "description": _section_description(section),
            "hints": [],
        }
        for section in raw_sections
    ]

    beats_output_path = paths.beats_output_path
    sections_output_path = paths.sections_output_path
    write_json(beats_output_path, beat_rows)
    write_json(sections_output_path, section_rows)
    return {
        "beats": str(beats_output_path),
        "sections": str(sections_output_path),
    }