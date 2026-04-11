from __future__ import annotations

from typing import Any

from analyzer.event_contracts import validate_song_event_payload
from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _event_id(label: str, index: int) -> str:
    return f"machine_{label}_{index:03d}"


def _event_feature_rows(event_features: dict, start_time: float, end_time: float) -> list[dict]:
    return [
        dict(row)
        for row in event_features.get("features", [])
        if float(row["start_time"]) < end_time and float(row["end_time"]) > start_time
    ]


def _repeated_phrase_counts(symbolic: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in symbolic.get("motif_summary", {}).get("repeated_phrase_groups", []):
        counts[str(group["id"])] = len(group.get("phrase_window_ids", []))
    return counts


def _section_index(sections_payload: dict) -> dict[str, dict]:
    return {str(section["section_id"]): dict(section) for section in sections_payload.get("sections", [])}


def _identifier_index(identifier_payload: dict) -> dict[str, dict]:
    return {
        str(event.get("source_event_id")): dict(event)
        for event in identifier_payload.get("events", [])
        if event.get("source_event_id")
    }


def _build_candidates(score_rows: list[tuple[str, float, str]]) -> list[dict[str, Any]]:
    ordered = sorted(score_rows, key=lambda item: item[1], reverse=True)
    return [
        {
            "type": label,
            "confidence": round(_clamp01(score), 6),
            "notes": notes,
        }
        for label, score, notes in ordered
    ]


def _copy_event(event: dict) -> dict[str, Any]:
    copied = {key: value for key, value in event.items() if key != "candidates"}
    if "source_layers" in copied:
        copied["source_layers"] = list(copied["source_layers"])
    if "evidence" in copied:
        copied["evidence"] = {
            key: (list(value) if isinstance(value, list) else dict(value) if isinstance(value, dict) else value)
            for key, value in copied["evidence"].items()
        }
    return copied


def _infer_event_intensity(event: dict, feature_rows: list[dict]) -> float:
    if "intensity" in event:
        return _clamp01(float(event["intensity"]))
    if feature_rows:
        accent = _mean([float(row.get("derived", {}).get("accent_intensity", 0.0)) for row in feature_rows])
        energy = _mean([
            float(row.get("normalized", {}).get("energy_score", row.get("rolling", {}).get("medium", {}).get("energy_mean", 0.0)))
            for row in feature_rows
        ])
        bass = _mean([float(row.get("derived", {}).get("bass_activation_score", 0.0)) for row in feature_rows])
        return _clamp01(max(accent, energy, bass, float(event.get("confidence", 0.0))))
    return _clamp01(float(event.get("confidence", 0.0)))


def _classify_drop_variant(rule_event: dict, feature_rows: list[dict], identifier: dict | None) -> tuple[str, list[dict], str]:
    energy_delta = _mean([float(row["derived"].get("energy_delta", 0.0)) for row in feature_rows])
    accent = _mean([float(row["derived"].get("accent_intensity", 0.0)) for row in feature_rows])
    bass = _mean([float(row["derived"].get("bass_activation_score", 0.0)) for row in feature_rows])
    energy_mean = _mean([float(row["rolling"]["medium"].get("energy_mean", 0.0)) for row in feature_rows])
    onset = _mean([float(row["normalized"].get("onset_density", 0.0)) for row in feature_rows])
    spectral_rise = 0.0
    if identifier is not None:
        spectral_rise = _clamp01(float(identifier.get("evidence", {}).get("spectral_centroid_delta", 0.0)) / 200.0)

    scores = [
        ("drop_explode", 0.4 * accent + 0.25 * _clamp01(energy_delta * 2.0) + 0.2 * spectral_rise + 0.15 * onset, "Explosive release with strong accent and spectral opening."),
        ("drop_groove", 0.4 * bass + 0.3 * energy_mean + 0.2 * onset + 0.1 * max(0.0, 1.0 - accent), "Sustained bass-led release with groove continuity."),
        ("drop_punch", 0.5 * accent + 0.3 * _clamp01(energy_delta * 2.0) + 0.2 * max(0.0, 1.0 - energy_mean), "Compact high-impact release with punch-forward attack."),
        ("soft_release", 0.4 * max(0.0, 0.75 - accent) + 0.35 * energy_mean + 0.25 * max(0.0, 0.55 - onset), "Release resolves tension with softer attack and less explosive accent."),
    ]
    candidates = _build_candidates(scores)
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    if float(top["confidence"]) >= 0.62 and (second is None or float(top["confidence"]) - float(second["confidence"]) >= 0.05):
        return str(top["type"]), candidates, str(top["notes"])
    return "drop", candidates, "Subtype evidence is not decisive enough; keeping parent drop label."


def _match_identifier(rule_event: dict, identifier_index: dict[str, dict]) -> dict | None:
    return identifier_index.get(str(rule_event.get("id")))


def _phrase_event(
    *,
    event_id: str,
    event_type: str,
    phrase: dict,
    feature_rows: list[dict],
    summary: str,
    notes: str,
    candidates: list[dict] | None = None,
) -> dict[str, Any]:
    vocal_mean = _mean([float(row["derived"].get("vocal_presence_score", 0.0)) for row in feature_rows])
    energy_mean = _mean([float(row["rolling"]["medium"].get("energy_mean", 0.0)) for row in feature_rows])
    event = {
        "id": event_id,
        "type": event_type,
        "start_time": round(float(phrase["start_s"]), 6),
        "end_time": round(float(phrase["end_s"]), 6),
        "confidence": round(min(1.0, 0.4 + vocal_mean * 0.35 + energy_mean * 0.2), 6),
        "intensity": round(max(vocal_mean, energy_mean), 6),
        "evidence": {
            "summary": summary,
            "source_windows": [
                {
                    "layer": "symbolic",
                    "start_time": round(float(phrase["start_s"]), 6),
                    "end_time": round(float(phrase["end_s"]), 6),
                    "ref": str(phrase["id"]),
                    "metric_names": ["phrase_window_id", "phrase_group_id"]
                },
                {
                    "layer": "event_features",
                    "start_time": round(float(feature_rows[0]["start_time"]), 6),
                    "end_time": round(float(feature_rows[-1]["end_time"]), 6),
                    "ref": f"beats:{feature_rows[0]['beat']}-{feature_rows[-1]['beat']}",
                    "metric_names": ["vocal_presence_score", "energy_mean"]
                }
            ],
            "metrics": [
                {"name": "vocal_presence_mean", "value": vocal_mean, "source_layer": "event_features"},
                {"name": "energy_mean", "value": energy_mean, "source_layer": "event_features"}
            ],
            "reasons": [summary],
            "rule_names": [f"{event_type}_phrase_classifier"]
        },
        "notes": notes,
        "section_id": phrase.get("section_id"),
        "source_layers": ["symbolic", "event_features"]
    }
    if candidates:
        event["candidates"] = candidates
    return event


def generate_machine_events(
    paths: SongPaths,
    event_features: dict,
    rule_candidates: dict,
    identifier_payload: dict,
    symbolic: dict,
    sections_payload: dict,
) -> dict[str, Any]:
    section_by_id = _section_index(sections_payload)
    identifier_by_source = _identifier_index(identifier_payload)
    phrase_repeat_counts = _repeated_phrase_counts(symbolic)
    refined_events: list[dict[str, Any]] = []

    for event_index, source_event in enumerate(rule_candidates.get("events", []), start=1):
        source_event = dict(source_event)
        event_type = str(source_event["type"])
        candidate_event = _copy_event(source_event)
        base_feature_rows = _event_feature_rows(event_features, float(source_event["start_time"]), float(source_event["end_time"]))
        candidate_event["intensity"] = round(_infer_event_intensity(candidate_event, base_feature_rows), 6)
        if event_type == "drop":
            feature_rows = base_feature_rows
            identifier = _match_identifier(source_event, identifier_by_source)
            if feature_rows:
                refined_type, candidates, note = _classify_drop_variant(source_event, feature_rows, identifier)
                candidate_event["type"] = refined_type
                candidate_event["candidates"] = candidates
                candidate_event["notes"] = f"{candidate_event['notes']} {note}".strip()
                candidate_event["confidence"] = round(min(1.0, float(candidate_event["confidence"]) + (float(candidates[0]["confidence"]) - 0.5) * 0.15), 6)
                if identifier is not None:
                    candidate_event["source_layers"] = list(dict.fromkeys([*candidate_event.get("source_layers", []), "energy_identifiers"]))
        elif event_type in {"breakdown", "pause_break"}:
            feature_rows = _event_feature_rows(event_features, float(source_event["end_time"]), float(source_event["end_time"]) + 4.0)
            followup_rise = _mean([max(0.0, float(row["derived"].get("energy_delta", 0.0))) for row in feature_rows])
            if followup_rise >= 0.18:
                candidate_event["type"] = "energy_reset"
                candidate_event["notes"] = f"{candidate_event['notes']} Follow-up energy rise indicates a reset-and-reentry mechanic.".strip()
                candidate_event["candidates"] = [
                    {"type": "energy_reset", "confidence": round(min(1.0, 0.55 + followup_rise), 6), "notes": "Energy rebuild follows the negative-space window."},
                    {"type": event_type, "confidence": float(source_event["confidence"]), "notes": "Parent transition remains a valid fallback."}
                ]
                candidate_event["confidence"] = round(min(1.0, max(float(source_event["confidence"]), 0.55 + followup_rise * 0.5)), 6)
        candidate_event["id"] = _event_id(str(candidate_event["type"]), event_index)
        refined_events.append(candidate_event)

    existing_keys = {(round(float(event["start_time"]), 6), round(float(event["end_time"]), 6), str(event["type"])) for event in refined_events}

    feature_rows = [dict(row) for row in event_features.get("features", [])]
    layer_remove_index = 1
    layer_add_index = 1
    for row in feature_rows:
        energy_delta = float(row["derived"].get("energy_delta", 0.0))
        density_delta = float(row["derived"].get("density_delta", 0.0))
        section = section_by_id.get(str(row.get("section_id"))) if row.get("section_id") else None
        if density_delta <= -0.18 and energy_delta <= -0.08:
            key = (round(float(row["start_time"]), 6), round(float(row["end_time"]), 6), "layer_remove")
            if key not in existing_keys:
                refined_events.append(
                    {
                        "id": _event_id("layer_remove", layer_remove_index),
                        "type": "layer_remove",
                        "start_time": round(float(row["start_time"]), 6),
                        "end_time": round(float(row["end_time"]), 6),
                        "confidence": round(min(1.0, 0.45 + abs(density_delta) * 0.4), 6),
                        "intensity": round(min(1.0, abs(density_delta)), 6),
                        "evidence": {
                            "summary": "Symbolic density and energy both step downward, indicating arrangement subtraction.",
                            "source_windows": [
                                {
                                    "layer": "event_features",
                                    "start_time": round(float(row["start_time"]), 6),
                                    "end_time": round(float(row["end_time"]), 6),
                                    "ref": f"beats:{row['beat']}-{row['beat']}",
                                    "metric_names": ["density_delta", "energy_delta"]
                                }
                            ],
                            "metrics": [
                                {"name": "density_delta", "value": density_delta, "source_layer": "event_features"},
                                {"name": "energy_delta", "value": energy_delta, "source_layer": "event_features"}
                            ],
                            "reasons": ["Abrupt density decrease with concurrent energy loss."],
                            "rule_names": ["layer_remove_delta_rule"]
                        },
                        "notes": "Arrangement appears to strip back at this beat.",
                        "section_id": section.get("section_id") if section else None,
                        "source_layers": ["event_features"]
                    }
                )
                existing_keys.add(key)
                layer_remove_index += 1
        if density_delta >= 0.18 and energy_delta >= 0.05:
            key = (round(float(row["start_time"]), 6), round(float(row["end_time"]), 6), "layer_add")
            if key not in existing_keys:
                refined_events.append(
                    {
                        "id": _event_id("layer_add", layer_add_index),
                        "type": "layer_add",
                        "start_time": round(float(row["start_time"]), 6),
                        "end_time": round(float(row["end_time"]), 6),
                        "confidence": round(min(1.0, 0.45 + density_delta * 0.35), 6),
                        "intensity": round(min(1.0, density_delta), 6),
                        "evidence": {
                            "summary": "Symbolic density and energy rise together, indicating arrangement addition.",
                            "source_windows": [
                                {
                                    "layer": "event_features",
                                    "start_time": round(float(row["start_time"]), 6),
                                    "end_time": round(float(row["end_time"]), 6),
                                    "ref": f"beats:{row['beat']}-{row['beat']}",
                                    "metric_names": ["density_delta", "energy_delta"]
                                }
                            ],
                            "metrics": [
                                {"name": "density_delta", "value": density_delta, "source_layer": "event_features"},
                                {"name": "energy_delta", "value": energy_delta, "source_layer": "event_features"}
                            ],
                            "reasons": ["Abrupt density increase with concurrent energy growth."],
                            "rule_names": ["layer_add_delta_rule"]
                        },
                        "notes": "Arrangement appears to gain material at this beat.",
                        "section_id": section.get("section_id") if section else None,
                        "source_layers": ["event_features"]
                    }
                )
                existing_keys.add(key)
                layer_add_index += 1

    phrase_windows = [dict(window) for window in symbolic.get("phrase_windows", [])]
    phrase_rows_by_id = {
        str(window["id"]): _event_feature_rows(event_features, float(window["start_s"]), float(window["end_s"]))
        for window in phrase_windows
    }
    hook_index = 1
    anthem_index = 1
    response_index = 1
    for phrase in phrase_windows:
        rows = phrase_rows_by_id.get(str(phrase["id"]), [])
        if not rows:
            continue
        vocal_mean = _mean([float(row["derived"].get("vocal_presence_score", 0.0)) for row in rows])
        energy_mean = _mean([float(row["rolling"]["medium"].get("energy_mean", 0.0)) for row in rows])
        repeat_count = phrase_repeat_counts.get(str(phrase.get("phrase_group_id")), 1)
        section = section_by_id.get(str(phrase.get("section_id"))) if phrase.get("section_id") else None
        if repeat_count >= 2 and vocal_mean >= 0.35:
            refined_events.append(
                _phrase_event(
                    event_id=_event_id("hook_phrase", hook_index),
                    event_type="hook_phrase",
                    phrase=phrase,
                    feature_rows=rows,
                    summary="Repeated phrase-group activity and vocal presence indicate a hook phrase.",
                    notes=f"Phrase group repeats {repeat_count} time(s), making the phrase a stable hook candidate.",
                    candidates=[
                        {"type": "anthem_call", "confidence": round(min(1.0, vocal_mean), 6), "notes": "Strong vocals could also read as a call moment."}
                    ]
                )
            )
            hook_index += 1
        section_start = float(section["start"]) if section else float(phrase["start_s"])
        if vocal_mean >= 0.5 and energy_mean >= 0.45 and (float(phrase["start_s"]) - section_start) <= 4.0:
            refined_events.append(
                _phrase_event(
                    event_id=_event_id("anthem_call", anthem_index),
                    event_type="anthem_call",
                    phrase=phrase,
                    feature_rows=rows,
                    summary="Phrase opens a section with strong vocal presence and enough supporting energy to read as an anthem call.",
                    notes="Section-entry vocal phrase promoted as a crowd-facing call moment.",
                    candidates=[
                        {"type": "hook_phrase", "confidence": round(min(1.0, vocal_mean * 0.9), 6), "notes": "Phrase may also function as a repeated hook."}
                    ]
                )
            )
            anthem_index += 1

    for left, right in zip(phrase_windows, phrase_windows[1:]):
        if left.get("section_id") != right.get("section_id"):
            continue
        left_rows = phrase_rows_by_id.get(str(left["id"]), [])
        right_rows = phrase_rows_by_id.get(str(right["id"]), [])
        if not left_rows or not right_rows:
            continue
        left_vocal = _mean([float(row["derived"].get("vocal_presence_score", 0.0)) for row in left_rows])
        right_vocal = _mean([float(row["derived"].get("vocal_presence_score", 0.0)) for row in right_rows])
        if left_vocal < 0.35 or right_vocal < 0.35:
            continue
        if str(left.get("phrase_group_id")) == str(right.get("phrase_group_id")):
            continue
        refined_events.append(
            {
                "id": _event_id("call_response", response_index),
                "type": "call_response",
                "start_time": round(float(left["start_s"]), 6),
                "end_time": round(float(right["end_s"]), 6),
                "confidence": round(min(1.0, 0.4 + ((left_vocal + right_vocal) / 2.0) * 0.35), 6),
                "intensity": round(max(left_vocal, right_vocal), 6),
                "evidence": {
                    "summary": "Adjacent vocal phrases with different phrase-group identities indicate a call-and-response exchange.",
                    "source_windows": [
                        {"layer": "symbolic", "start_time": round(float(left["start_s"]), 6), "end_time": round(float(left["end_s"]), 6), "ref": str(left["id"]), "metric_names": ["phrase_group_id"]},
                        {"layer": "symbolic", "start_time": round(float(right["start_s"]), 6), "end_time": round(float(right["end_s"]), 6), "ref": str(right["id"]), "metric_names": ["phrase_group_id"]}
                    ],
                    "metrics": [
                        {"name": "left_vocal_presence_mean", "value": left_vocal, "source_layer": "event_features"},
                        {"name": "right_vocal_presence_mean", "value": right_vocal, "source_layer": "event_features"}
                    ],
                    "reasons": ["Sequential vocal phrases remain distinct but similarly prominent."],
                    "rule_names": ["call_response_phrase_pair"]
                },
                "notes": "Adjacent phrase groups suggest an answer phrase instead of a single repeated hook.",
                "section_id": left.get("section_id"),
                "source_layers": ["symbolic", "event_features"]
            }
        )
        response_index += 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "event_features_file": str(paths.artifact("event_inference", "features.json")),
            "rule_candidates_file": str(paths.artifact("event_inference", "rule_candidates.json")),
            "identifier_hints_file": str(paths.artifact("energy_summary", "hints.json")),
            "symbolic_layer_file": str(paths.artifact("layer_b_symbolic.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "engine": "deterministic-event-classifier-v1"
        },
        "review_status": "machine",
        "notes": "Machine-refined event set with fallback candidates preserved for review.",
        "threshold_profile": "default",
        "metadata": {
            "event_count": len(refined_events),
            "source_rule_event_count": len(rule_candidates.get("events", []))
        },
        "events": refined_events
    }
    validated = validate_song_event_payload(payload)
    write_json(paths.artifact("event_inference", "events.machine.json"), validated)
    return validated