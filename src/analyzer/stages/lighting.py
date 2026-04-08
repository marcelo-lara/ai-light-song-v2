from __future__ import annotations

from collections import Counter

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


SECTION_SCENES = {
    "intro": "intro_glow",
    "verse": "verse_drive",
    "chorus": "chorus_lift",
    "bridge": "bridge_sweep",
    "outro": "outro_release",
}

SECTION_COLORS = {
    "intro": "cool",
    "verse": "neutral",
    "chorus": "warm",
    "bridge": "magenta",
    "outro": "cool",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _normalize(value: float, minimum: float, maximum: float, floor: float = 0.0, ceiling: float = 1.0) -> float:
    if maximum - minimum <= 1e-8:
        return round((floor + ceiling) / 2.0, 6)
    ratio = (value - minimum) / (maximum - minimum)
    return round(floor + ((ceiling - floor) * ratio), 6)


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _find_phrase_for_time(time_s: float, phrases: list[dict]) -> dict | None:
    for phrase in phrases:
        if float(phrase["start_s"]) <= time_s < float(phrase["end_s"]):
            return phrase
    return None


def _find_pattern_for_window(start_s: float, end_s: float, pattern_callbacks: list[dict]) -> dict | None:
    for callback in pattern_callbacks:
        if float(callback["start_s"]) < end_s and float(callback["end_s"]) > start_s:
            return callback
    return None


def _find_motif_for_window(start_s: float, end_s: float, motif_callbacks: list[dict]) -> dict | None:
    for callback in motif_callbacks:
        if float(callback["start_s"]) < end_s and float(callback["end_s"]) > start_s:
            return callback
    return None


def _cue_anchor_ids(start_s: float, end_s: float, cue_anchors: list[dict], limit: int = 6) -> list[str]:
    matching = [
        str(anchor["id"])
        for anchor in cue_anchors
        if start_s <= float(anchor["time_s"]) <= end_s
    ]
    return matching[:limit]


def _pulse_behavior(bass_motion: str | None) -> str:
    if bass_motion == "leaping":
        return "accented_pulse"
    if bass_motion == "stepwise":
        return "steady_pulse"
    if bass_motion == "pedal":
        return "pedal_glow"
    if bass_motion == "mixed":
        return "hybrid_pulse"
    return "soft_pulse"


def _accent_mode(accent_count: int) -> str:
    if accent_count >= 4:
        return "onset_sync"
    if accent_count >= 2:
        return "accent_pulse"
    if accent_count >= 1:
        return "accent_touch"
    return "none"


def _effect_complexity(phrase_count: int, motif_activity: float | None, accent_count: int) -> float:
    activity = float(motif_activity) if motif_activity is not None else 0.0
    score = min(1.0, (phrase_count * 0.12) + (activity * 0.45) + (min(accent_count, 5) * 0.07))
    return round(score, 6)


def _dominant_section_name(section_label: str | None) -> str:
    label = str(section_label or "section").lower()
    return label


def generate_lighting_events(paths: SongPaths) -> dict:
    unified = read_json(paths.artifact("music_feature_layers.json"))
    timeline = unified.get("timeline", {})
    layers = unified.get("layers", {})
    lighting_context = unified.get("lighting_context", {})

    sections = timeline.get("sections", [])
    phrases = timeline.get("phrases", [])
    accents = timeline.get("accent_windows", [])
    cue_anchors = lighting_context.get("cue_anchors", [])
    pattern_callbacks = lighting_context.get("pattern_callbacks", [])
    motif_callbacks = lighting_context.get("motif_callbacks", [])

    energy_sections = {
        row["section_id"]: row
        for row in layers.get("energy", {}).get("section_energy", [])
    }
    section_cards = {
        row["section_id"]: row
        for row in unified.get("section_cards", [])
    }
    symbolic_summary = layers.get("symbolic", {}).get("symbolic_summary", {})
    global_bass_motion = symbolic_summary.get("bass_motion")

    energy_means = [float(row.get("mean", 0.0)) for row in energy_sections.values()]
    transient_values = [float(row.get("transient_density", 0.0)) for row in energy_sections.values()]
    energy_min = min(energy_means) if energy_means else 0.0
    energy_max = max(energy_means) if energy_means else 1.0
    transient_min = min(transient_values) if transient_values else 0.0
    transient_max = max(transient_values) if transient_values else 1.0

    lighting_events: list[dict] = []

    for section in sections:
        section_id = section["section_id"]
        section_label = _dominant_section_name(section.get("label"))
        start_s = float(section["start"])
        end_s = float(section["end"])
        energy_row = energy_sections.get(section_id, {})
        section_card = section_cards.get(section_id, {})
        section_phrases = [phrase for phrase in phrases if phrase.get("section_id") == section_id]
        section_accents = [accent for accent in accents if accent.get("section_id") == section_id]
        pattern_callback = _find_pattern_for_window(start_s, end_s, pattern_callbacks)
        motif_callback = _find_motif_for_window(start_s, end_s, motif_callbacks)

        mean_energy = float(energy_row.get("mean", 0.0))
        transient_density = float(energy_row.get("transient_density", 0.0))
        intensity = _normalize(mean_energy, energy_min, energy_max, 0.25, 0.95)
        if section_label == "chorus":
            intensity = round(_clamp01(intensity + 0.05), 6)
        movement_speed = _normalize(transient_density, transient_min, transient_max, 0.2, 0.95)

        first_phrase = section_phrases[0] if section_phrases else None
        cue_ids = _cue_anchor_ids(start_s, end_s, cue_anchors)
        lighting_events.append(
            {
                "id": f"section_event_{section_id}",
                "time": round(start_s, 6),
                "duration": round(end_s - start_s, 6),
                "event_type": "section_scene",
                "scene": SECTION_SCENES.get(section_label, f"{section_label}_scene"),
                "intensity": intensity,
                "movement_speed": movement_speed,
                "color_family": SECTION_COLORS.get(section_label, "neutral"),
                "accent_mode": _accent_mode(len(section_accents)),
                "effect_complexity": _effect_complexity(
                    len(section_phrases),
                    section_card.get("motif_activity"),
                    len(section_accents),
                ),
                "pulse_behavior": _pulse_behavior(global_bass_motion),
                "variation_mode": "repeat_with_variation" if pattern_callback or motif_callback else "establish",
                "anchor_refs": {
                    "section_id": section_id,
                    "phrase_window_id": first_phrase.get("id") if first_phrase else None,
                    "motif_group_id": motif_callback.get("motif_group_id") if motif_callback else None,
                    "pattern_id": pattern_callback.get("pattern_id") if pattern_callback else None,
                    "cue_anchor_ids": cue_ids,
                },
            }
        )

    for accent in accents:
        accent_time = float(accent["time_s"])
        section = _section_for_time(accent_time, sections)
        phrase = _find_phrase_for_time(accent_time, phrases)
        pattern_callback = _find_pattern_for_window(accent_time, accent_time + 0.25, pattern_callbacks)
        motif_callback = _find_motif_for_window(accent_time, accent_time + 0.25, motif_callbacks)
        lighting_events.append(
            {
                "id": f"accent_event_{accent['id']}",
                "time": round(accent_time, 6),
                "duration": 0.3 if accent.get("kind") == "rise" else 0.18,
                "event_type": "accent",
                "scene": "accent_rise" if accent.get("kind") == "rise" else "accent_hit",
                "intensity": round(_clamp01(0.55 + (float(accent["intensity"]) * 0.45)), 6),
                "movement_speed": 0.72 if accent.get("kind") == "rise" else 0.92,
                "color_family": SECTION_COLORS.get(_dominant_section_name(accent.get("section_name")), "neutral"),
                "accent_mode": "flash",
                "effect_complexity": 0.35,
                "pulse_behavior": _pulse_behavior(global_bass_motion),
                "variation_mode": "accent",
                "anchor_refs": {
                    "section_id": section.get("section_id") if section else accent.get("section_id"),
                    "phrase_window_id": phrase.get("id") if phrase else None,
                    "motif_group_id": motif_callback.get("motif_group_id") if motif_callback else None,
                    "pattern_id": pattern_callback.get("pattern_id") if pattern_callback else None,
                    "cue_anchor_ids": _cue_anchor_ids(accent_time - 0.02, accent_time + 0.02, cue_anchors),
                },
            }
        )

    for callback in pattern_callbacks:
        section_id = callback.get("section_id")
        section = next((row for row in sections if row.get("section_id") == section_id), None)
        phrase = _find_phrase_for_time(float(callback["start_s"]), phrases)
        lighting_events.append(
            {
                "id": f"pattern_event_{callback['id']}",
                "time": round(float(callback["start_s"]), 6),
                "duration": round(float(callback["end_s"]) - float(callback["start_s"]), 6),
                "event_type": "pattern_callback",
                "scene": "pattern_recall" if callback.get("callback_action") == "establish" else "pattern_variation",
                "intensity": 0.68 if callback.get("callback_action") == "establish" else 0.74,
                "movement_speed": 0.58,
                "color_family": SECTION_COLORS.get(_dominant_section_name(section.get("label") if section else None), "neutral"),
                "accent_mode": "phrase_sync",
                "effect_complexity": 0.62,
                "pulse_behavior": _pulse_behavior(global_bass_motion),
                "variation_mode": str(callback.get("callback_action") or "repeat_with_variation"),
                "anchor_refs": {
                    "section_id": section_id,
                    "phrase_window_id": phrase.get("id") if phrase else None,
                    "motif_group_id": None,
                    "pattern_id": callback.get("pattern_id"),
                    "cue_anchor_ids": _cue_anchor_ids(float(callback["start_s"]), float(callback["end_s"]), cue_anchors),
                },
            }
        )

    for callback in motif_callbacks:
        section_id = callback.get("section_id")
        section = next((row for row in sections if row.get("section_id") == section_id), None)
        phrase = next((row for row in phrases if row.get("phrase_group_id") == callback.get("phrase_group_id")), None)
        lighting_events.append(
            {
                "id": f"motif_event_{callback['id']}",
                "time": round(float(callback["start_s"]), 6),
                "duration": round(float(callback["end_s"]) - float(callback["start_s"]), 6),
                "event_type": "motif_callback",
                "scene": "motif_echo",
                "intensity": 0.61,
                "movement_speed": 0.52,
                "color_family": SECTION_COLORS.get(_dominant_section_name(section.get("label") if section else None), "neutral"),
                "accent_mode": "callback",
                "effect_complexity": 0.66,
                "pulse_behavior": _pulse_behavior(global_bass_motion),
                "variation_mode": str(callback.get("callback_action") or "echo"),
                "anchor_refs": {
                    "section_id": section_id,
                    "phrase_window_id": phrase.get("id") if phrase else None,
                    "motif_group_id": callback.get("motif_group_id"),
                    "pattern_id": None,
                    "cue_anchor_ids": _cue_anchor_ids(float(callback["start_s"]), float(callback["end_s"]), cue_anchors),
                },
            }
        )

    lighting_events.sort(key=lambda event: (float(event["time"]), str(event["id"])))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "music_feature_layers_file": str(paths.artifact("music_feature_layers.json")),
            "engine": "rule-based-lighting-mapping",
        },
        "cue_anchors": cue_anchors,
        "lighting_events": lighting_events,
        "mapping_rules": [
            "Section energy drives base intensity.",
            "Transient density drives movement speed.",
            "Section label selects scene family and color family.",
            "Accent windows create short flash or rise events.",
            "Motif and pattern callbacks create repeatable variation events.",
        ],
        "metadata": {
            "event_count": len(lighting_events),
            "dominant_bass_motion": global_bass_motion,
            "dominant_motif_id": layers.get("symbolic", {}).get("motif_summary", {}).get("dominant_motif_id"),
        },
    }
    write_json(paths.artifact("lighting_events.json"), payload)
    return payload