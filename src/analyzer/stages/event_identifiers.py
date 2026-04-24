from __future__ import annotations

from typing import Any

from analyzer.event_contracts import normalize_event_type
from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

SUPPORTED_IDENTIFIERS = ("drop",)

def _section_index(sections_payload: dict) -> dict[str, dict]:
    return {
        str(section["section_id"]): dict(section)
        for section in sections_payload.get("sections", [])
    }

def _section_for_time(time_s: float, sections_payload: dict) -> dict | None:
    for section in sections_payload.get("sections", []):
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    return None

def infer_song_identifiers(
    paths: SongPaths,
    energy_layer: dict,
    sections_payload: dict,
) -> dict[str, Any]:
    for identifier in SUPPORTED_IDENTIFIERS:
        normalize_event_type(identifier)

    identifier_events: list[dict[str, Any]] = []
    beat_energy = energy_layer.get("beat_energy", [])

    drop_count = 0
    last_drop_time = -10.0
    
    threshold_loudness = 0.15
    threshold_onset = 0.15
    threshold_energy = 0.12
    
    for i in range(1, len(beat_energy)):
        curr_beat = beat_energy[i]
        prev_beat = beat_energy[i - 1]
        
        loudness_delta = float(curr_beat.get("loudness_avg", 0.0)) - float(prev_beat.get("loudness_avg", 0.0))
        onset_density_delta = float(curr_beat.get("onset_density", 0.0)) - float(prev_beat.get("onset_density", 0.0))
        centroid_delta = float(curr_beat.get("centroid_avg", 0.0)) - float(prev_beat.get("centroid_avg", 0.0))
        energy_score_delta = float(curr_beat.get("energy_score", 0.0)) - float(prev_beat.get("energy_score", 0.0))
        
        anchor_time = float(curr_beat["time"])
        if (
            loudness_delta > threshold_loudness 
            and onset_density_delta > threshold_onset 
            and energy_score_delta > threshold_energy
            and anchor_time - last_drop_time > 8.0
        ):
            drop_count += 1
            last_drop_time = anchor_time
            section = _section_for_time(anchor_time, sections_payload)
            section_id = section["section_id"] if section else curr_beat.get("section_id")
            
            evidence = {
                "loudness_delta": round(loudness_delta, 6),
                "onset_density_delta": round(onset_density_delta, 6),
                "spectral_centroid_delta": round(centroid_delta, 6),
                "bass_energy_delta": 0.0,
            }
            
            confidence = min(1.0, 0.6 + min(loudness_delta, 0.4) + min(onset_density_delta, 0.4))
            
            notes = ["Coordinated loudness and rhythmic activation increase support a release event."]
            if section:
                charsc = section.get('section_character') or section.get('label', '')
                sid = section.get('section_id', '')
                notes.insert(0, f"Transition anchors to {charsc} ({sid}).")
            if centroid_delta > 0.0:
                notes.append("Spectral centroid rise indicates the mix opens up at the identifier anchor.")

            identifier_events.append({
                "id": f"event_drop_{drop_count:03d}",
                "identifier": "drop",
                "time_s": round(anchor_time, 6),
                "start_s": round(anchor_time, 6),
                "end_s": round(anchor_time + 4.0, 6),
                "section_id": str(section_id) if section_id else None,
                "confidence": round(confidence, 6),
                "evidence": evidence,
                "notes": notes,
                "created_by": "analyzer_energy_identifier",
            })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "energy-song-identifiers-v1",
            "dependencies": {
                "energy_layer_file": str(paths.artifact("layer_c_energy.json")),
                "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            },
        },
        "supported_identifiers": list(SUPPORTED_IDENTIFIERS),
        "events": identifier_events,
    }
    write_json(paths.artifact("energy_summary", "hints.json"), payload)
    return payload
