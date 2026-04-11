from __future__ import annotations

from typing import Any

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


ROLLING_WINDOWS = {
    "short": 4,
    "medium": 8,
    "long": 16,
}


def _window_end_s(timing: dict, beat_index: int) -> float:
    beats = timing.get("beats", [])
    bars = timing.get("bars", [])
    if beat_index + 1 < len(beats):
        return float(beats[beat_index + 1]["time"])
    if bars:
        return float(bars[-1]["end_s"])
    return float(beats[beat_index]["time"])


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _phrase_for_time(time_s: float, phrases: list[dict]) -> dict | None:
    for phrase in phrases:
        if float(phrase["start_s"]) <= time_s < float(phrase["end_s"]):
            return phrase
    if phrases and time_s >= float(phrases[-1]["start_s"]):
        return phrases[-1]
    return None


def _chord_for_time(time_s: float, chords: list[dict]) -> dict | None:
    for chord in chords:
        if float(chord["time"]) <= time_s < float(chord["end_s"]):
            return chord
    if chords and time_s >= float(chords[-1]["time"]):
        return chords[-1]
    return None


def _overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def _window_note_overlap_score(notes: list[dict], start_s: float, end_s: float) -> float:
    duration = max(end_s - start_s, 1e-6)
    overlap_sum = 0.0
    for note in notes:
        overlap_sum += _overlap(start_s, end_s, float(note["time"]), float(note["end_s"]))
    return min(overlap_sum / duration, 1.0)


def _value_bounds(rows: list[dict], key: str) -> tuple[float, float]:
    values = [float(row[key]) for row in rows]
    if not values:
        return 0.0, 0.0
    return min(values), max(values)


def _normalize(value: float, bounds: tuple[float, float]) -> float:
    minimum, maximum = bounds
    if maximum <= minimum:
        return 0.0
    return round((value - minimum) / (maximum - minimum), 6)


def _accent_lookup(accent_candidates: list[dict], start_s: float, end_s: float) -> tuple[str | None, float]:
    for accent in accent_candidates:
        accent_time = float(accent["time"])
        if start_s <= accent_time < end_s:
            return str(accent["id"]), float(accent.get("intensity", 0.0))
    return None, 0.0


def _build_timeline_index(
    *,
    paths: SongPaths,
    timing: dict,
    sections: list[dict],
    phrases: list[dict],
    chords: list[dict],
    accent_candidates: list[dict],
) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "symbolic_layer_file": str(paths.artifact("layer_b_symbolic.json")),
            "energy_layer_file": str(paths.artifact("layer_c_energy.json")),
            "features_file": str(paths.artifact("event_inference", "features.json")),
        },
        "beats": [
            {
                "beat": int(beat["index"]),
                "bar": int(beat["bar"]),
                "beat_in_bar": int(beat["beat_in_bar"]),
                "time": round(float(beat["time"]), 6),
            }
            for beat in timing.get("beats", [])
        ],
        "sections": [
            {
                "section_id": section["section_id"],
                "section_name": section.get("section_character") or section.get("label"),
                "start_time": round(float(section["start"]), 6),
                "end_time": round(float(section["end"]), 6),
                "confidence": round(float(section["confidence"]), 6),
            }
            for section in sections
        ],
        "phrases": [
            {
                "phrase_window_id": phrase["id"],
                "phrase_group_id": phrase.get("phrase_group_id"),
                "section_id": phrase.get("section_id"),
                "start_time": round(float(phrase["start_s"]), 6),
                "end_time": round(float(phrase["end_s"]), 6),
            }
            for phrase in phrases
        ],
        "chords": [
            {
                "chord": chord["chord"],
                "start_time": round(float(chord["time"]), 6),
                "end_time": round(float(chord["end_s"]), 6),
                "confidence": round(float(chord["confidence"]), 6),
            }
            for chord in chords
        ],
        "accents": [
            {
                "accent_id": accent["id"],
                "time": round(float(accent["time"]), 6),
                "kind": accent["kind"],
                "intensity": round(float(accent["intensity"]), 6),
            }
            for accent in accent_candidates
        ],
    }
    write_json(paths.artifact("event_inference", "timeline_index.json"), payload)
    return payload


def build_event_feature_layer(
    paths: SongPaths,
    timing: dict,
    harmonic: dict,
    symbolic: dict,
    energy_features: dict,
    energy_layer: dict,
    sections_payload: dict,
    genre_result: dict | None = None,
) -> dict[str, Any]:
    beats = timing.get("beats", [])
    sections = sections_payload.get("sections", [])
    chords = harmonic.get("chords", [])
    phrases = symbolic.get("phrase_windows", [])
    note_events = symbolic.get("note_events", [])
    vocal_notes = [note for note in note_events if str(note.get("source_stem")) == "vocals"]
    bass_notes = [note for note in note_events if str(note.get("source_stem")) == "bass"]

    raw_energy_by_beat = {
        int(row["beat"]): dict(row)
        for row in energy_features.get("beat_features", [])
    }
    derived_energy_by_beat = {
        int(row["beat"]): dict(row)
        for row in energy_layer.get("beat_energy", [])
    }
    symbolic_density_by_beat = {
        int(row["beat"]): dict(row)
        for row in symbolic.get("density_per_beat", [])
    }
    accent_candidates = [dict(row) for row in energy_layer.get("accent_candidates", [])]

    raw_rows: list[dict[str, Any]] = []
    silence_gap_seconds = 0.0
    previous_chord_label: str | None = None
    for index, beat in enumerate(beats):
        beat_number = int(beat["index"])
        start_s = float(beat["time"])
        end_s = _window_end_s(timing, index)
        midpoint = (start_s + end_s) / 2.0

        raw_energy = raw_energy_by_beat.get(beat_number, {})
        derived_energy = derived_energy_by_beat.get(beat_number, {})
        density_row = symbolic_density_by_beat.get(beat_number, {})
        section = _section_for_time(midpoint, sections)
        phrase = _phrase_for_time(midpoint, phrases)
        chord = _chord_for_time(start_s, chords)
        accent_id, accent_intensity = _accent_lookup(accent_candidates, start_s, end_s)

        note_count = int(density_row.get("note_count", 0))
        beat_duration = max(end_s - start_s, 1e-6)
        if note_count == 0:
            silence_gap_seconds = round(silence_gap_seconds + beat_duration, 6)
        else:
            silence_gap_seconds = 0.0

        chord_label = str(chord.get("chord", "N")) if chord else "N"
        chord_confidence = float(chord.get("confidence", 0.0)) if chord else 0.0
        chord_change = 1.0 if previous_chord_label not in (None, chord_label) else 0.0
        previous_chord_label = chord_label

        raw_rows.append(
            {
                "beat": beat_number,
                "bar": int(beat["bar"]),
                "beat_in_bar": int(beat["beat_in_bar"]),
                "start_time": round(start_s, 6),
                "end_time": round(end_s, 6),
                "section_id": section.get("section_id") if section else None,
                "section_name": (section.get("section_character") or section.get("label")) if section else None,
                "phrase_window_id": phrase.get("id") if phrase else None,
                "phrase_group_id": phrase.get("phrase_group_id") if phrase else None,
                "chord": chord_label,
                "chord_confidence": round(chord_confidence, 6),
                "chord_change": chord_change,
                "loudness_avg": float(raw_energy.get("loudness_avg", 0.0)),
                "onset_density": float(raw_energy.get("onset_density", 0.0)),
                "spectral_flux": float(raw_energy.get("flux_avg", 0.0)),
                "spectral_centroid": float(raw_energy.get("centroid_avg", 0.0)),
                "energy_score": float(derived_energy.get("energy_score", 0.0)),
                "symbolic_density": float(density_row.get("density", 0.0)),
                "symbolic_note_count": note_count,
                "vocal_presence": round(_window_note_overlap_score(vocal_notes, start_s, end_s), 6),
                "bass_activation": round(_window_note_overlap_score(bass_notes, start_s, end_s), 6),
                "accent_id": accent_id,
                "accent_intensity": round(accent_intensity, 6),
                "silence_gap_seconds": silence_gap_seconds,
            }
        )

    normalization_bounds = {
        key: _value_bounds(raw_rows, key)
        for key in (
            "loudness_avg",
            "onset_density",
            "spectral_flux",
            "spectral_centroid",
            "energy_score",
            "symbolic_density",
            "vocal_presence",
            "bass_activation",
            "accent_intensity",
            "chord_confidence",
        )
    }

    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows):
        normalized = {
            key: _normalize(float(row[key]), bounds)
            for key, bounds in normalization_bounds.items()
        }
        previous = normalized_rows[index - 1] if index > 0 else None
        derived = {
            "energy_delta": round(normalized["energy_score"] - float(previous["normalized"]["energy_score"]), 6) if previous else 0.0,
            "density_delta": round(normalized["symbolic_density"] - float(previous["normalized"]["symbolic_density"]), 6) if previous else 0.0,
            "silence_gap_seconds": round(float(row["silence_gap_seconds"]), 6),
            "vocal_presence_score": normalized["vocal_presence"],
            "bass_activation_score": normalized["bass_activation"],
            "harmonic_tension_proxy": round(min(1.0, max(0.0, ((1.0 - normalized["chord_confidence"]) + float(row["chord_change"])) / 2.0)), 6),
            "accent_intensity": normalized["accent_intensity"],
        }
        feature_row = {
            "beat": row["beat"],
            "bar": row["bar"],
            "beat_in_bar": row["beat_in_bar"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "section_id": row["section_id"],
            "section_name": row["section_name"],
            "phrase_window_id": row["phrase_window_id"],
            "phrase_group_id": row["phrase_group_id"],
            "chord": row["chord"],
            "normalized": normalized,
            "derived": derived,
            "source_refs": {
                "energy_feature_beat": row["beat"],
                "symbolic_density_beat": row["beat"],
                "accent_id": row["accent_id"],
            },
        }
        normalized_rows.append(feature_row)

    for index, row in enumerate(normalized_rows):
        row["rolling"] = {
            name: {
                "energy_mean": _rolling_mean(normalized_rows, index, "normalized.energy_score", window_size),
                "density_mean": _rolling_mean(normalized_rows, index, "normalized.symbolic_density", window_size),
                "vocal_presence_mean": _rolling_mean(normalized_rows, index, "derived.vocal_presence_score", window_size),
                "bass_activation_mean": _rolling_mean(normalized_rows, index, "derived.bass_activation_score", window_size),
                "harmonic_tension_mean": _rolling_mean(normalized_rows, index, "derived.harmonic_tension_proxy", window_size),
            }
            for name, window_size in ROLLING_WINDOWS.items()
        }

    duration_s = float(timing.get("bars", [{}])[-1].get("end_s", beats[-1]["time"] if beats else 0.0)) if beats or timing.get("bars") else 0.0
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "symbolic_layer_file": str(paths.artifact("layer_b_symbolic.json")),
            "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
            "energy_layer_file": str(paths.artifact("layer_c_energy.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "genre_file": str(paths.artifact("genre.json")) if genre_result is not None else None,
            "engine": "rule-based-event-feature-alignment",
            "normalization_rules": {
                "numeric_fields": {
                    key: {
                        "method": "per-song min-max",
                        "minimum": round(bounds[0], 6),
                        "maximum": round(bounds[1], 6),
                    }
                    for key, bounds in normalization_bounds.items()
                },
                "silence_gap": "accumulate consecutive beat durations where symbolic_note_count equals zero",
                "rolling_windows_beats": dict(ROLLING_WINDOWS),
                "harmonic_tension_proxy": "average of inverse normalized chord confidence and chord change flag",
            },
        },
        "metadata": {
            "duration_s": round(duration_s, 6),
            "beat_count": len(beats),
            "bar_count": len(timing.get("bars", [])),
            "section_count": len(sections),
            "phrase_count": len(phrases),
            "genres": list(genre_result.get("genres", [])) if genre_result else [],
        },
        "feature_catalog": {
            "normalized": [
                "loudness_avg",
                "onset_density",
                "spectral_flux",
                "spectral_centroid",
                "energy_score",
                "symbolic_density",
                "vocal_presence",
                "bass_activation",
                "accent_intensity",
                "chord_confidence",
            ],
            "derived": [
                "energy_delta",
                "density_delta",
                "silence_gap_seconds",
                "vocal_presence_score",
                "bass_activation_score",
                "harmonic_tension_proxy",
                "accent_intensity",
            ],
        },
        "features": normalized_rows,
    }

    for row in payload["features"]:
        if float(row["start_time"]) < 0.0 or float(row["end_time"]) > duration_s + 1e-6:
            raise ValueError("Event feature windows must stay within song duration")

    write_json(paths.artifact("event_inference", "features.json"), payload)
    _build_timeline_index(
        paths=paths,
        timing=timing,
        sections=sections,
        phrases=phrases,
        chords=chords,
        accent_candidates=accent_candidates,
    )
    return payload


def _rolling_mean(rows: list[dict[str, Any]], end_index: int, dotted_key: str, window_size: int) -> float:
    start_index = max(0, end_index - window_size + 1)
    window = rows[start_index : end_index + 1]
    if not window:
        return 0.0
    key_parts = dotted_key.split(".")
    total = 0.0
    for row in window:
        value: Any = row
        for key in key_parts:
            value = value[key]
        total += float(value)
    return round(total / len(window), 6)