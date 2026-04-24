from __future__ import annotations

from typing import Any

from analyzer.event_contracts import normalize_event_type
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

SUPPORTED_IDENTIFIERS = ("drop",)


def _section_for_time(time_s: float, sections_payload: dict) -> dict | None:
    for section in sections_payload.get("sections", []):
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    return None


def _load_optional(path: SongPaths, *parts: str) -> dict[str, Any]:
    artifact_path = path.artifact(*parts)
    if not artifact_path.exists():
        return {}
    payload = read_json(artifact_path)
    return payload if isinstance(payload, dict) else {}


def _fft_transients(fft_payload: dict[str, Any]) -> list[dict[str, float]]:
    frames = [dict(row) for row in fft_payload.get("frames", [])]
    bands = [dict(row) for row in fft_payload.get("bands", [])]
    if len(frames) < 3 or not bands:
        return []

    bass_index = next((idx for idx, band in enumerate(bands) if str(band.get("id")) == "bass"), None)
    if bass_index is None:
        return []

    levels = [float(frame.get("levels", [0.0])[bass_index]) for frame in frames]
    threshold = sorted(levels)[int(max(0, round(len(levels) * 0.85) - 1))] if levels else 0.0

    transients: list[dict[str, float]] = []
    for idx in range(1, len(frames) - 1):
        current = levels[idx]
        if current < threshold:
            continue
        if current >= levels[idx - 1] and current > levels[idx + 1]:
            transients.append({
                "time_s": float(frames[idx].get("time", 0.0)),
                "strength": current,
            })
    return transients


def _nearest_transient_delta_ms(anchor_time: float, transients: list[dict[str, float]]) -> float | None:
    if not transients:
        return None
    nearest = min(transients, key=lambda row: abs(float(row["time_s"]) - anchor_time))
    return (float(nearest["time_s"]) - anchor_time) * 1000.0


def _alignment_score(delta_ms: float | None) -> float:
    if delta_ms is None:
        return 0.0
    distance = abs(delta_ms)
    if distance >= 50.0:
        return 0.0
    return max(0.0, 1.0 - (distance / 50.0))


def _nearest_feature_row(features: list[dict[str, Any]], anchor_time: float) -> dict[str, Any] | None:
    if not features:
        return None
    return min(features, key=lambda row: abs(float(row.get("start_time", 0.0)) - anchor_time))


def infer_song_identifiers(
    paths: SongPaths,
    energy_layer: dict,
    sections_payload: dict,
) -> dict[str, Any]:
    for identifier in SUPPORTED_IDENTIFIERS:
        normalize_event_type(identifier)

    fft_payload = _load_optional(paths, "essentia", "fft_bands.json")
    event_features_payload = _load_optional(paths, "event_inference", "features.json")
    event_rows = [dict(row) for row in event_features_payload.get("features", [])]
    transients = _fft_transients(fft_payload)

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

            feature_row = _nearest_feature_row(event_rows, anchor_time)
            bass_att = float(feature_row.get("derived", {}).get("bass_att", 0.0)) if feature_row else 0.0
            bass_att_lma = float(feature_row.get("derived", {}).get("bass_att_lma", bass_att)) if feature_row else bass_att
            flux = float(feature_row.get("normalized", {}).get("spectral_flux", 0.0)) if feature_row else 0.0
            flux_lma = float(feature_row.get("derived", {}).get("spectral_flux_lma", flux)) if feature_row else flux

            bass_ratio = bass_att / max(bass_att_lma, 1e-6)
            flux_ratio = flux / max(flux_lma, 1e-6)
            mismatch_flag = bass_ratio < 1.0 and flux_ratio < 1.0

            delta_ms = _nearest_transient_delta_ms(anchor_time, transients)
            alignment_score = _alignment_score(delta_ms)

            confidence = min(1.0, 0.6 + min(loudness_delta, 0.4) + min(onset_density_delta, 0.4))
            if mismatch_flag:
                confidence *= 0.8
            confidence = min(1.0, confidence + (alignment_score * 0.15))

            notes = ["Coordinated loudness and rhythmic activation increase support a release event."]
            if section:
                charsc = section.get("section_character") or section.get("label", "")
                sid = section.get("section_id", "")
                notes.insert(0, f"Transition anchors to {charsc} ({sid}).")
            if centroid_delta > 0.0:
                notes.append("Spectral centroid rise indicates the mix opens up at the identifier anchor.")
            if mismatch_flag:
                notes.append("Audit flag: impact-like transition lacks local moving-average support in bass_att and spectral_flux.")

            identifier_events.append(
                {
                    "id": f"event_drop_{drop_count:03d}",
                    "identifier": "drop",
                    "time_s": round(anchor_time, 6),
                    "start_s": round(anchor_time, 6),
                    "end_s": round(anchor_time + 4.0, 6),
                    "section_id": str(section_id) if section_id else None,
                    "confidence": round(confidence, 6),
                    "audit": {
                        "alignment_score": round(alignment_score, 6),
                        "nearest_transient_delta_ms": round(float(delta_ms), 6) if delta_ms is not None else None,
                        "is_transient_locked": bool(alignment_score >= 0.5),
                        "transient_sources": ["fft_bands", "bass_att"],
                        "mismatch_flag": mismatch_flag,
                        "support": {
                            "bass_att": round(bass_att, 6),
                            "bass_att_lma": round(bass_att_lma, 6),
                            "spectral_flux": round(flux, 6),
                            "spectral_flux_lma": round(flux_lma, 6),
                            "bass_ratio": round(bass_ratio, 6),
                            "flux_ratio": round(flux_ratio, 6),
                        },
                    },
                    "evidence": evidence,
                    "notes": notes,
                    "created_by": "analyzer_energy_identifier",
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
                "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
                "fft_bands_file": str(paths.artifact("essentia", "fft_bands.json")),
                "event_features_file": str(paths.artifact("event_inference", "features.json")),
            },
        },
        "supported_identifiers": list(SUPPORTED_IDENTIFIERS),
        "events": identifier_events,
    }
    write_json(paths.artifact("energy_summary", "hints.json"), payload)
    return payload
