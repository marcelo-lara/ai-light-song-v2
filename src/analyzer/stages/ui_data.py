from __future__ import annotations

from bisect import bisect_left

from analyzer.io import read_json, write_json
from analyzer.models import round_schema_float
from analyzer.paths import SongPaths


NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


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


def _format_section_label(label: str | None) -> str:
    if not label:
        return "Unlabeled"
    return str(label).replace("_", " ").title()


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
            "label": _format_section_label(section.get("label")),
            "description": "",
            "hints": [],
        }
        for section in sections_payload.get("sections", [])
    ]

    beats_output_path = paths.song_output_dir / "beats.json"
    sections_output_path = paths.song_output_dir / "sections.json"
    write_json(beats_output_path, beat_rows)
    write_json(sections_output_path, section_rows)
    return {
        "beats": str(beats_output_path),
        "sections": str(sections_output_path),
    }