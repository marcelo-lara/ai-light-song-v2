from typing import Any
from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

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
