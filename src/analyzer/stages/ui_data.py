from __future__ import annotations

from bisect import bisect_left
import re

from analyzer.io import read_json, write_json
from analyzer.models import round_schema_float
from analyzer.paths import SongPaths


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

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


def _pitch_to_note_name(pitch: int) -> str:
    return NOTE_NAMES[int(pitch) % 12]


def _nearest_beat_index(time_s: float, beat_times: list[float]) -> int | None:
    if not beat_times:
        return None
    insert_at = bisect_left(beat_times, float(time_s))
    if insert_at <= 0:
        return 0
    if insert_at >= len(beat_times):
        return len(beat_times) - 1
    previous_index = insert_at - 1
    next_index = insert_at
    previous_delta = abs(beat_times[previous_index] - float(time_s))
    next_delta = abs(beat_times[next_index] - float(time_s))
    return previous_index if previous_delta <= next_delta else next_index


def _beat_aligned_bass_notes(paths: SongPaths, beat_times: list[float]) -> list[str | None]:
    bass_payload = read_json(paths.artifact("symbolic_transcription", "basic_pitch", "bass.json"))
    bass_notes = sorted(
        bass_payload.get("notes", []),
        key=lambda note: (float(note["time"]), int(note["pitch"]), -float(note["confidence"])),
    )

    bass_by_beat: list[str | None] = [None for _ in beat_times]
    selected_pitch_by_beat: list[int | None] = [None for _ in beat_times]
    for note in bass_notes:
        beat_index = _nearest_beat_index(float(note["time"]), beat_times)
        if beat_index is None:
            continue
        pitch = int(note["pitch"])
        selected_pitch = selected_pitch_by_beat[beat_index]
        if selected_pitch is None or pitch < selected_pitch:
            selected_pitch_by_beat[beat_index] = pitch
            bass_by_beat[beat_index] = _pitch_to_note_name(pitch)
    return bass_by_beat


def build_ui_data(paths: SongPaths) -> dict[str, str]:
    beats_payload = read_json(paths.artifact("essentia", "beats.json"))
    harmonic_payload = read_json(paths.artifact("layer_a_harmonic.json"))
    sections_payload = read_json(paths.artifact("section_segmentation", "sections.json"))

    chord_events = harmonic_payload.get("chords", [])
    beat_points = beats_payload.get("beats", [])
    beat_times = [float(beat["time"]) for beat in beat_points]
    bass_by_beat = _beat_aligned_bass_notes(paths, beat_times)
    beat_rows = [
        {
            "time": round_schema_float(float(beat["time"])),
            "beat": int(beat["beat_in_bar"]),
            "bar": int(beat["bar"]),
            "bass": bass_by_beat[index],
            "chord": _resolve_chord_for_time(float(beat["time"]), chord_events),
            "type": str(beat["type"]),
        }
        for index, beat in enumerate(beat_points)
    ]
    section_rows = [
        {
            "start": round_schema_float(float(section["start"])),
            "end": round_schema_float(float(section["end"])),
            "label": _format_section_label(
                section.get("section_character") or section.get("label"),
                section.get("section_id"),
                section.get("confidence"),
            ),
            "description": _section_description(section),
            "hints": [],
        }
        for section in sections_payload.get("sections", [])
    ]

    beats_output_path = paths.beats_output_path
    sections_output_path = paths.sections_output_path
    write_json(beats_output_path, beat_rows)
    write_json(sections_output_path, section_rows)
    return {
        "beats": str(beats_output_path),
        "sections": str(sections_output_path),
    }