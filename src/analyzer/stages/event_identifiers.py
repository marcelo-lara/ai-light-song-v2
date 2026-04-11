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


def _event_feature_index(event_features: dict) -> dict[int, dict]:
    return {
        int(row["beat"]): dict(row)
        for row in event_features.get("features", [])
    }


def _energy_feature_index(energy_features: dict) -> dict[int, dict]:
    return {
        int(row["beat"]): dict(row)
        for row in energy_features.get("beat_features", [])
    }


def _energy_layer_index(energy_layer: dict) -> dict[int, dict]:
    return {
        int(row["beat"]): dict(row)
        for row in energy_layer.get("beat_energy", [])
    }


def _drop_event_notes(rule_event: dict, section: dict | None, evidence: dict[str, float]) -> list[str]:
    notes: list[str] = []
    if section is not None:
        notes.append(
            f"Transition anchors to {section.get('section_character') or section.get('label')} ({section['section_id']})."
        )
    if evidence["loudness_delta"] > 0.0 and evidence["onset_density_delta"] > 0.0:
        notes.append("Coordinated loudness and rhythmic activation increase support a release event.")
    if evidence["bass_energy_delta"] >= 0.3:
        notes.append("Bass activation crosses the minimum release threshold.")
    if evidence["spectral_centroid_delta"] > 0.0:
        notes.append("Spectral centroid rise indicates the mix opens up at the identifier anchor.")
    return notes


def infer_song_identifiers(
    paths: SongPaths,
    event_features: dict,
    energy_features: dict,
    energy_layer: dict,
    rule_candidates: dict,
    sections_payload: dict,
) -> dict[str, Any]:
    for identifier in SUPPORTED_IDENTIFIERS:
        normalize_event_type(identifier)

    section_by_id = _section_index(sections_payload)
    feature_by_beat = _event_feature_index(event_features)
    raw_energy_by_beat = _energy_feature_index(energy_features)
    derived_energy_by_beat = _energy_layer_index(energy_layer)

    identifier_events: list[dict[str, Any]] = []
    drop_candidates = [
        dict(event)
        for event in rule_candidates.get("events", [])
        if str(event.get("type")) == "drop"
    ]

    for index, candidate in enumerate(drop_candidates, start=1):
        beat = None
        source_windows = candidate.get("evidence", {}).get("source_windows", [])
        for window in source_windows:
            if str(window.get("layer")) != "event_features":
                continue
            ref = str(window.get("ref", ""))
            if not ref.startswith("beats:"):
                continue
            beat_label = ref.split(":", 1)[1].split("-", 1)[0]
            if beat_label.isdigit():
                beat = int(beat_label)
                break
        if beat is None:
            continue

        feature_row = feature_by_beat.get(beat)
        raw_energy_row = raw_energy_by_beat.get(beat)
        previous_raw_energy_row = raw_energy_by_beat.get(max(1, beat - 1)) if beat > 1 else raw_energy_by_beat.get(beat)
        derived_energy_row = derived_energy_by_beat.get(beat)
        if feature_row is None or raw_energy_row is None or previous_raw_energy_row is None or derived_energy_row is None:
            continue

        section_id = candidate.get("section_id")
        section = section_by_id.get(str(section_id)) if section_id is not None else None
        anchor_time = float(candidate["start_time"])
        section_start = float(section["start"]) if section is not None else anchor_time
        section_end = float(section["end"]) if section is not None else float(candidate["end_time"])
        event_end = max(float(candidate["end_time"]), anchor_time)

        evidence = {
            "loudness_delta": round(
                float(raw_energy_row.get("loudness_avg", 0.0)) - float(previous_raw_energy_row.get("loudness_avg", 0.0)),
                6,
            ),
            "onset_density_delta": round(
                float(raw_energy_row.get("onset_density", 0.0)) - float(previous_raw_energy_row.get("onset_density", 0.0)),
                6,
            ),
            "bass_energy_delta": round(float(feature_row["derived"].get("bass_activation_score", 0.0)), 6),
            "spectral_centroid_delta": round(
                float(raw_energy_row.get("centroid_avg", 0.0)) - float(previous_raw_energy_row.get("centroid_avg", 0.0)),
                6,
            ),
            "energy_score_delta": round(float(feature_row["derived"].get("energy_delta", 0.0)), 6),
            "accent_intensity": round(float(feature_row["derived"].get("accent_intensity", 0.0)), 6),
        }

        confidence = min(
            1.0,
            max(
                float(candidate.get("confidence", 0.0)),
                0.45
                + max(0.0, evidence["energy_score_delta"]) * 0.2
                + max(0.0, evidence["bass_energy_delta"]) * 0.2
                + max(0.0, evidence["accent_intensity"]) * 0.15,
            ),
        )

        identifier_events.append(
            {
                "id": f"event_drop_{index:03d}",
                "identifier": "drop",
                "time_s": round(anchor_time, 6),
                "start_s": round(min(anchor_time, section_start), 6),
                "end_s": round(max(event_end, min(section_end, anchor_time + (event_end - anchor_time))), 6),
                "section_id": str(section_id) if section_id is not None else None,
                "confidence": round(confidence, 6),
                "evidence": evidence,
                "notes": _drop_event_notes(candidate, section, evidence),
                "source_event_id": str(candidate["id"]),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "energy-song-identifiers-v1",
            "dependencies": {
                "energy_layer_file": str(paths.artifact("layer_c_energy.json")),
                "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
                "event_features_file": str(paths.artifact("event_inference", "features.json")),
                "rule_candidates_file": str(paths.artifact("event_inference", "rule_candidates.json")),
                "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            },
        },
        "supported_identifiers": list(SUPPORTED_IDENTIFIERS),
        "events": identifier_events,
    }
    write_json(paths.artifact("energy_summary", "hints.json"), payload)
    return payload