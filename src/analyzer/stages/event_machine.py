from __future__ import annotations

from typing import Any

from analyzer.event_contracts import validate_song_event_payload
from analyzer.io import read_json
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


def _section_feature_rows(event_features: dict, section: dict) -> list[dict]:
    return _event_feature_rows(event_features, float(section["start"]), float(section["end"]))


def _load_human_hints(paths: SongPaths) -> list[dict[str, Any]]:
    hint_path = paths.reference("human", "human_hints.json")
    if hint_path is None or not hint_path.exists():
        return []
    payload = read_json(hint_path)
    return [dict(row) for row in payload.get("human_hints", [])]


def _load_lyric_lines(paths: SongPaths) -> list[dict[str, Any]]:
    lyric_path = paths.reference("moises", "lyrics.json")
    if lyric_path is None or not lyric_path.exists():
        return []
    payload = read_json(lyric_path)
    if not isinstance(payload, list):
        return []

    lines: dict[int, dict[str, Any]] = {}
    for token in payload:
        if not isinstance(token, dict):
            continue
        line_id_raw = token.get("line_id")
        try:
            line_id = int(line_id_raw)
        except (TypeError, ValueError):
            continue
        text = str(token.get("text", "")).strip()
        if not text or text in {"<SOL>", "<EOL>"}:
            continue
        start = float(token.get("start", 0.0))
        end = float(token.get("end", start))
        if end < start:
            end = start
        line = lines.setdefault(
            line_id,
            {"line_id": line_id, "start": start, "end": end, "tokens": [], "confidences": []},
        )
        line["start"] = min(float(line["start"]), start)
        line["end"] = max(float(line["end"]), end)
        line["tokens"].append(text)
        confidence = token.get("confidence")
        try:
            if confidence is not None:
                line["confidences"].append(float(confidence))
        except (TypeError, ValueError):
            pass

    lyric_lines: list[dict[str, Any]] = []
    for line_id in sorted(lines):
        line = lines[line_id]
        if not line["tokens"]:
            continue
        confidences = [float(value) for value in line["confidences"]]
        lyric_lines.append(
            {
                "line_id": line_id,
                "start": round(float(line["start"]), 6),
                "end": round(float(line["end"]), 6),
                "text": " ".join(str(token) for token in line["tokens"]),
                "confidence": _mean(confidences),
                "token_count": len(line["tokens"]),
            }
        )
    return lyric_lines


def _hint_text(hint: dict[str, Any]) -> str:
    return f"{hint.get('title', '')} {hint.get('summary', '')}".casefold()


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
            "confidence": round(_clamp01(_clamp01(score)), 6),
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
    energy_mean = _mean([float(row["rolling"]["local"].get("energy_mean", 0.0)) for row in feature_rows])
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


def _classify_plateau_variant(rule_event: dict, feature_rows: list[dict], section: dict | None) -> tuple[str, list[dict], str]:
    duration = max(0.0, float(rule_event["end_time"]) - float(rule_event["start_time"]))
    bass_mean = _mean([float(row["derived"].get("bass_activation_score", 0.0)) for row in feature_rows])
    vocal_mean = _mean([float(row["derived"].get("vocal_presence_score", 0.0)) for row in feature_rows])
    energy_mean = _mean([
        float(row["normalized"].get("energy_score", row["rolling"]["local"].get("energy_mean", 0.0)))
        for row in feature_rows
    ])
    onset_mean = _mean([float(row["normalized"].get("onset_density", 0.0)) for row in feature_rows])
    section_character = str((section or {}).get("section_character") or (section or {}).get("label") or "")

    scores = [
        (
            "groove_loop",
            0.3 * bass_mean + 0.25 * energy_mean + 0.2 * onset_mean + 0.15 * min(1.0, duration / 16.0) + 0.1 * (1.0 if "groove" in section_character else 0.0),
            "Stable bass-led pulse and sustained motion support a groove-loop interpretation.",
        ),
        (
            "atmospheric_plateau",
            0.32 * max(0.0, 0.6 - onset_mean) + 0.22 * max(0.0, 0.55 - bass_mean) + 0.18 * max(0.0, 0.5 - energy_mean) + 0.18 * min(1.0, duration / 16.0) + 0.1 * (1.0 if "ambient" in section_character or "breath" in section_character else 0.0),
            "Lower-volatility texture and sustained space support an atmospheric plateau.",
        ),
        (
            "no_drop_plateau",
            0.3 + 0.2 * min(1.0, duration / 12.0) + 0.15 * energy_mean,
            "Build evidence remains present, but sustained-state evidence is not decisive enough for a narrower subtype.",
        ),
    ]
    candidates = _build_candidates(scores)
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    if str(top["type"]) != "no_drop_plateau" and float(top["confidence"]) >= 0.55 and (second is None or float(top["confidence"]) - float(second["confidence"]) >= 0.04):
        return str(top["type"]), candidates, str(top["notes"])
    return "no_drop_plateau", candidates, "Sustained-state subtype evidence is not decisive enough; keeping the parent plateau label."


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
    energy_mean = _mean([float(row["rolling"]["local"].get("energy_mean", 0.0)) for row in feature_rows])
    event = {
        "id": event_id,
        "type": event_type,
        "created_by": "analyzer_phrase_classifier",
        "start_time": round(float(phrase["start_s"]), 6),
        "end_time": round(float(phrase["end_s"]), 6),
        "confidence": round(_clamp01(min(1.0, 0.4 + vocal_mean * 0.35 + energy_mean * 0.2)), 6),
        "intensity": round(_clamp01(max(vocal_mean, energy_mean)), 6),
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


def _section_context_event(
    *,
    event_id: str,
    event_type: str,
    section: dict,
    feature_rows: list[dict],
    summary: str,
    notes: str,
) -> dict[str, Any]:
    vocal_focus = _mean([float(row["derived"].get("vocal_focus_score", 0.0)) for row in feature_rows])
    percussion_focus = _mean([float(row["derived"].get("percussion_focus_score", 0.0)) for row in feature_rows])
    instrumental_focus = _mean([float(row["derived"].get("instrumental_focus_score", 0.0)) for row in feature_rows])
    intensity = max(vocal_focus, percussion_focus, instrumental_focus, _mean([float(row["normalized"].get("energy_score", 0.0)) for row in feature_rows]))
    return {
        "id": event_id,
        "type": event_type,
        "created_by": "analyzer_context_classifier",
        "start_time": round(float(section["start"]), 6),
        "end_time": round(float(section["end"]), 6),
        "confidence": round(_clamp01(min(1.0, 0.45 + intensity * 0.4)), 6),
        "intensity": round(_clamp01(intensity), 6),
        "evidence": {
            "summary": summary,
            "source_windows": [
                {
                    "layer": "event_features",
                    "start_time": round(float(feature_rows[0]["start_time"]), 6),
                    "end_time": round(float(feature_rows[-1]["end_time"]), 6),
                    "ref": f"beats:{feature_rows[0]['beat']}-{feature_rows[-1]['beat']}",
                    "metric_names": ["vocal_focus_score", "percussion_focus_score", "instrumental_focus_score"],
                }
            ],
            "metrics": [
                {"name": "vocal_focus_mean", "value": vocal_focus, "source_layer": "event_features"},
                {"name": "percussion_focus_mean", "value": percussion_focus, "source_layer": "event_features"},
                {"name": "instrumental_focus_mean", "value": instrumental_focus, "source_layer": "event_features"},
            ],
            "reasons": [summary],
            "rule_names": [f"{event_type}_section_context_rule"],
        },
        "notes": notes,
        "section_id": section.get("section_id"),
        "source_layers": ["event_features", "sections"],
    }


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
    lyric_lines = _load_lyric_lines(paths)
    refined_events: list[dict[str, Any]] = []

    for event_index, source_event in enumerate(rule_candidates.get("events", []), start=1):
        source_event = dict(source_event)
        event_type = str(source_event["type"])
        candidate_event = _copy_event(source_event)
        candidate_event["created_by"] = "analyzer_event_classifier"
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
        elif event_type == "no_drop_plateau":
            section = section_by_id.get(str(source_event.get("section_id"))) if source_event.get("section_id") else None
            if base_feature_rows:
                refined_type, candidates, note = _classify_plateau_variant(source_event, base_feature_rows, section)
                candidate_event["type"] = refined_type
                candidate_event["candidates"] = candidates
                candidate_event["notes"] = f"{candidate_event['notes']} {note}".strip()
                candidate_event["confidence"] = round(min(1.0, max(float(candidate_event["confidence"]), float(candidates[0]["confidence"]) * 0.9)), 6)
        elif event_type in {"breakdown", "pause_break"}:
            feature_rows = _event_feature_rows(event_features, float(source_event["end_time"]), float(source_event["end_time"]) + 4.0)
            followup_rise = _mean([max(0.0, float(row["derived"].get("energy_delta", 0.0))) for row in feature_rows])
            if followup_rise >= 0.18:
                candidate_event["type"] = "energy_reset"
                candidate_event["notes"] = f"{candidate_event['notes']} Follow-up energy rise indicates a reset-and-reentry mechanic.".strip()
                candidate_event["candidates"] = [
                    {"type": "energy_reset", "confidence": round(_clamp01(min(1.0, 0.55 + followup_rise)), 6), "notes": "Energy rebuild follows the negative-space window."},
                    {"type": event_type, "confidence": float(source_event["confidence"]), "notes": "Parent transition remains a valid fallback."}
                ]
                candidate_event["confidence"] = round(min(1.0, max(float(source_event["confidence"]), 0.55 + followup_rise * 0.5)), 6)
        candidate_event["id"] = _event_id(str(candidate_event["type"]), event_index)
        refined_events.append(candidate_event)

    existing_keys = {(round(float(event["start_time"]), 6), round(float(event["end_time"]), 6), str(event["type"])) for event in refined_events}

    feature_rows = [dict(row) for row in event_features.get("features", [])]
    
    def _is_peak(idx: int, vals: list[float], r: int = 2, is_min: bool = False) -> bool:
        val = vals[idx]
        start = max(0, idx - r)
        end = min(len(vals), idx + r + 1)
        for i in range(start, end):
            if i == idx: continue
            if is_min and vals[i] < val: return False
            if not is_min and vals[i] > val: return False
        return True

    densities = [float(row["derived"].get("density_delta", 0.0)) for row in feature_rows]
    layer_remove_index = 1
    layer_add_index = 1
    
    for i, row in enumerate(feature_rows):
        energy_delta = float(row["derived"].get("energy_delta", 0.0))
        density_delta = densities[i]
        section = section_by_id.get(str(row.get("section_id"))) if row.get("section_id") else None
        
        # Local Minimum (Layer Remove)
        if density_delta <= -0.18 and energy_delta <= -0.08 and _is_peak(i, densities, r=4, is_min=True):
            key = (round(float(row["start_time"]), 6), round(float(row["end_time"]), 6), "layer_remove")
            if key not in existing_keys:
                refined_events.append(
                    {
                        "id": _event_id("layer_remove", layer_remove_index),
                        "type": "layer_remove",
                        "created_by": "analyzer_event_classifier",
                        "start_time": round(float(row["start_time"]), 6),
                        "end_time": round(float(row["end_time"]), 6),
                        "confidence": round(_clamp01(min(1.0, 0.45 + abs(density_delta) * 0.4)), 6),
                        "intensity": round(_clamp01(min(1.0, abs(density_delta))), 6),
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

        # Local Maximum (Layer Add)
        if density_delta >= 0.18 and energy_delta >= 0.05 and _is_peak(i, densities, r=4, is_min=False):
            key = (round(float(row["start_time"]), 6), round(float(row["end_time"]), 6), "layer_add")
            if key not in existing_keys:
                refined_events.append(
                    {
                        "id": _event_id("layer_add", layer_add_index),
                        "type": "layer_add",
                        "created_by": "analyzer_event_classifier",
                        "start_time": round(float(row["start_time"]), 6),
                        "end_time": round(float(row["end_time"]), 6),
                        "confidence": round(_clamp01(min(1.0, 0.45 + density_delta * 0.35)), 6),
                        "intensity": round(_clamp01(min(1.0, density_delta)), 6),
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
        energy_mean = _mean([float(row["rolling"]["local"].get("energy_mean", 0.0)) for row in rows])
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
                        {"type": "anthem_call", "confidence": round(_clamp01(min(1.0, vocal_mean)), 6), "notes": "Strong vocals could also read as a call moment."}
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
                        {"type": "hook_phrase", "confidence": round(_clamp01(min(1.0, vocal_mean * 0.9)), 6), "notes": "Phrase may also function as a repeated hook."}
                    ]
                )
            )
            anthem_index += 1

    context_index = 1
    for section in sections_payload.get("sections", []):
        rows = _section_feature_rows(event_features, section)
        if not rows:
            continue
        key_section = str(section.get("section_id"))
        vocal_focus = _mean([float(row["derived"].get("vocal_focus_score", 0.0)) for row in rows])
        percussion_focus = _mean([float(row["derived"].get("percussion_focus_score", 0.0)) for row in rows])
        instrumental_focus = _mean([float(row["derived"].get("instrumental_focus_score", 0.0)) for row in rows])
        vocals_stem = _mean([float(row["derived"].get("vocals_stem_score", 0.0)) for row in rows])
        drums_stem = _mean([float(row["derived"].get("drums_stem_score", 0.0)) for row in rows])
        harmonic_stem = _mean([float(row["derived"].get("harmonic_stem_score", 0.0)) for row in rows])
        duration = max(0.0, float(section["end"]) - float(section["start"]))

        if vocal_focus >= 0.5 and drums_stem <= 0.35 and duration >= 1.5:
            key = (round(float(section["start"]), 6), round(float(section["end"]), 6), "vocal_spotlight")
            if key not in existing_keys:
                refined_events.append(
                    _section_context_event(
                        event_id=_event_id("vocal_spotlight", context_index),
                        event_type="vocal_spotlight",
                        section=section,
                        feature_rows=rows,
                        summary="Stem activity and symbolic evidence show the vocal line dominating the section more than drums or accompaniment.",
                        notes="Voice-led section promoted to a vocal spotlight for downstream prompting and cue planning.",
                    )
                )
                existing_keys.add(key)
                context_index += 1
        if percussion_focus >= 0.38 and vocals_stem <= 0.25 and harmonic_stem <= 0.4 and duration <= 8.0:
            key = (round(float(section["start"]), 6), round(float(section["end"]), 6), "percussion_break")
            if key not in existing_keys:
                refined_events.append(
                    _section_context_event(
                        event_id=_event_id("percussion_break", context_index),
                        event_type="percussion_break",
                        section=section,
                        feature_rows=rows,
                        summary="Drum stem activity dominates while vocal and harmonic stems stay reduced, indicating a percussion-led pocket.",
                        notes="Percussion carries the motion more than harmony or voice in this window.",
                    )
                )
                existing_keys.add(key)
                context_index += 1
        if instrumental_focus >= 0.4 and vocals_stem <= 0.25 and duration >= 6.0:
            key = (round(float(section["start"]), 6), round(float(section["end"]), 6), "instrumental_bed")
            if key not in existing_keys:
                refined_events.append(
                    _section_context_event(
                        event_id=_event_id("instrumental_bed", context_index),
                        event_type="instrumental_bed",
                        section=section,
                        feature_rows=rows,
                        summary="Instrumental stems carry the section while the vocal stem stays secondary, indicating an accompaniment-led bed.",
                        notes="Instrumental support is the main driver of this section rather than a lead-vocal phrase.",
                    )
                )
                existing_keys.add(key)
                context_index += 1

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
                "created_by": "analyzer_phrase_classifier",
                "start_time": round(float(left["start_s"]), 6),
                "end_time": round(float(right["end_s"]), 6),
                "confidence": round(_clamp01(min(1.0, 0.4 + ((left_vocal + right_vocal) / 2.0) * 0.35)), 6),
                "intensity": round(_clamp01(max(left_vocal, right_vocal)), 6),
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

    vocal_tail_index = 1
    for phrase in phrase_windows:
        rows = phrase_rows_by_id.get(str(phrase["id"]), [])
        if not rows:
            continue
        phrase_end = float(phrase["end_s"])
        followup_rows = _event_feature_rows(event_features, phrase_end, phrase_end + 2.5)
        if not followup_rows:
            continue
        vocal_focus = _mean([float(row["derived"].get("vocal_focus_score", 0.0)) for row in rows])
        followup_vocals = _mean([float(row["derived"].get("vocals_stem_score", 0.0)) for row in followup_rows])
        followup_harmonic = _mean([float(row["derived"].get("harmonic_stem_score", 0.0)) for row in followup_rows])
        followup_drums = _mean([float(row["derived"].get("drums_stem_score", 0.0)) for row in followup_rows])
        if vocal_focus < 0.45:
            continue
        if (vocal_focus - followup_vocals) < 0.28:
            continue
        if max(followup_harmonic, followup_drums) < 0.18:
            continue
        start_time = phrase_end
        end_time = float(followup_rows[-1]["end_time"])
        key = (round(start_time, 6), round(end_time, 6), "vocal_tail")
        if key in existing_keys:
            continue
        refined_events.append(
            {
                "id": _event_id("vocal_tail", vocal_tail_index),
                "type": "vocal_tail",
                "created_by": "analyzer_context_classifier",
                "start_time": round(start_time, 6),
                "end_time": round(end_time, 6),
                "confidence": round(_clamp01(min(1.0, 0.45 + (vocal_focus - followup_vocals) * 0.6)), 6),
                "intensity": round(_clamp01(max(vocal_focus - followup_vocals, 0.0)), 6),
                "evidence": {
                    "summary": "Vocal energy falls away after the phrase while accompaniment remains active, indicating a vocal tail or handoff.",
                    "source_windows": [
                        {"layer": "symbolic", "start_time": round(float(phrase["start_s"]), 6), "end_time": round(float(phrase["end_s"]), 6), "ref": str(phrase["id"]), "metric_names": ["phrase_group_id"]},
                        {"layer": "event_features", "start_time": round(float(followup_rows[0]["start_time"]), 6), "end_time": round(float(followup_rows[-1]["end_time"]), 6), "ref": f"beats:{followup_rows[0]['beat']}-{followup_rows[-1]['beat']}", "metric_names": ["vocals_stem_score", "harmonic_stem_score", "drums_stem_score"]},
                    ],
                    "metrics": [
                        {"name": "phrase_vocal_focus_mean", "value": vocal_focus, "source_layer": "event_features"},
                        {"name": "followup_vocals_mean", "value": followup_vocals, "source_layer": "event_features"},
                        {"name": "followup_harmonic_mean", "value": followup_harmonic, "source_layer": "event_features"},
                        {"name": "followup_drums_mean", "value": followup_drums, "source_layer": "event_features"},
                    ],
                    "reasons": ["Vocal phrase decays while accompaniment persists."],
                    "rule_names": ["vocal_tail_transition_rule"],
                },
                "notes": "Phrase decays into the underlying bed instead of ending with a hard stop.",
                "section_id": phrase.get("section_id"),
                "source_layers": ["symbolic", "event_features"],
            }
        )
        existing_keys.add(key)
        vocal_tail_index += 1

    lyric_event_index = 1
    for lyric_line in lyric_lines:
        rows = _event_feature_rows(event_features, float(lyric_line["start"]), float(lyric_line["end"]))
        if not rows:
            continue
        section_id = rows[0].get("section_id")
        vocals_mean = _mean([float(row["derived"].get("vocals_stem_score", 0.0)) for row in rows])
        vocal_focus = _mean([float(row["derived"].get("vocal_focus_score", 0.0)) for row in rows])
        drums_mean = _mean([float(row["derived"].get("drums_stem_score", 0.0)) for row in rows])
        instrumental_focus = _mean([float(row["derived"].get("instrumental_focus_score", 0.0)) for row in rows])
        lyric_confidence = float(lyric_line.get("confidence", 0.0))
        line_text = str(lyric_line.get("text", ""))

        spotlight_key = (round(float(lyric_line["start"]), 6), round(float(lyric_line["end"]), 6), "vocal_spotlight")
        if spotlight_key not in existing_keys and vocals_mean >= 0.32 and vocal_focus >= 0.32 and (vocals_mean >= drums_mean or lyric_confidence >= 0.7):
            refined_events.append(
                {
                    "id": _event_id("vocal_spotlight", lyric_event_index),
                    "type": "vocal_spotlight",
                    "created_by": "analyzer_lyric_guided_classifier",
                    "start_time": round(float(lyric_line["start"]), 6),
                    "end_time": round(float(lyric_line["end"]), 6),
                    "confidence": round(_clamp01(min(1.0, 0.42 + vocal_focus * 0.35 + vocals_mean * 0.2 + min(0.12, lyric_confidence * 0.12))), 6),
                    "intensity": round(_clamp01(max(vocals_mean, vocal_focus)), 6),
                    "evidence": {
                        "summary": "Lyric line timing aligns with vocal-dominant stem activity, indicating a vocal-led phrase window.",
                        "source_windows": [
                            {
                                "layer": "event_features",
                                "start_time": round(float(rows[0]["start_time"]), 6),
                                "end_time": round(float(rows[-1]["end_time"]), 6),
                                "ref": f"beats:{rows[0]['beat']}-{rows[-1]['beat']}",
                                "metric_names": ["vocals_stem_score", "vocal_focus_score", "drums_stem_score"],
                            }
                        ],
                        "metrics": [
                            {"name": "lyric_line_confidence", "value": lyric_confidence},
                            {"name": "vocals_stem_mean", "value": vocals_mean, "source_layer": "event_features"},
                            {"name": "vocal_focus_mean", "value": vocal_focus, "source_layer": "event_features"},
                            {"name": "drums_stem_mean", "value": drums_mean, "source_layer": "event_features"},
                        ],
                        "reasons": [f"Lyric line {lyric_line['line_id']} overlaps a clear vocal-led window."],
                        "rule_names": ["lyric_guided_vocal_spotlight_rule"],
                        "metadata": {"lyric_line_id": lyric_line["line_id"], "lyric_text": line_text},
                    },
                    "notes": "Timed lyric line reinforces that this window should read as a vocal spotlight rather than only a section-level vocal texture.",
                    "section_id": section_id,
                    "source_layers": ["event_features", "sections"],
                }
            )
            existing_keys.add(spotlight_key)
            lyric_event_index += 1

        followup_rows = _event_feature_rows(event_features, float(lyric_line["end"]), float(lyric_line["end"]) + 2.5)
        if not followup_rows:
            continue
        followup_vocals = _mean([float(row["derived"].get("vocals_stem_score", 0.0)) for row in followup_rows])
        followup_harmonic = _mean([float(row["derived"].get("harmonic_stem_score", 0.0)) for row in followup_rows])
        followup_drums = _mean([float(row["derived"].get("drums_stem_score", 0.0)) for row in followup_rows])
        tail_key = (round(float(lyric_line["end"]), 6), round(float(followup_rows[-1]["end_time"]), 6), "vocal_tail")
        if tail_key not in existing_keys and vocal_focus >= 0.34 and (vocals_mean - followup_vocals) >= 0.18 and max(followup_harmonic, followup_drums, instrumental_focus) >= 0.12:
            refined_events.append(
                {
                    "id": _event_id("vocal_tail", lyric_event_index),
                    "type": "vocal_tail",
                    "created_by": "analyzer_lyric_guided_classifier",
                    "start_time": round(float(lyric_line["end"]), 6),
                    "end_time": round(float(followup_rows[-1]["end_time"]), 6),
                    "confidence": round(_clamp01(min(1.0, 0.42 + (vocals_mean - followup_vocals) * 0.55 + min(0.1, lyric_confidence * 0.1))), 6),
                    "intensity": round(_clamp01(max(vocals_mean - followup_vocals, 0.0)), 6),
                    "evidence": {
                        "summary": "Lyric line ends before vocal stem energy drops into an active accompaniment bed, indicating a vocal tail.",
                        "source_windows": [
                            {
                                "layer": "event_features",
                                "start_time": round(float(rows[0]["start_time"]), 6),
                                "end_time": round(float(followup_rows[-1]["end_time"]), 6),
                                "ref": f"beats:{rows[0]['beat']}-{followup_rows[-1]['beat']}",
                                "metric_names": ["vocals_stem_score", "harmonic_stem_score", "drums_stem_score"],
                            }
                        ],
                        "metrics": [
                            {"name": "lyric_line_confidence", "value": lyric_confidence},
                            {"name": "line_vocals_mean", "value": vocals_mean, "source_layer": "event_features"},
                            {"name": "followup_vocals_mean", "value": followup_vocals, "source_layer": "event_features"},
                            {"name": "followup_harmonic_mean", "value": followup_harmonic, "source_layer": "event_features"},
                            {"name": "followup_drums_mean", "value": followup_drums, "source_layer": "event_features"},
                        ],
                        "reasons": [f"Lyric line {lyric_line['line_id']} ends as the vocal stem decays and the backing bed persists."],
                        "rule_names": ["lyric_guided_vocal_tail_rule"],
                        "metadata": {"lyric_line_id": lyric_line["line_id"], "lyric_text": line_text},
                    },
                    "notes": "Timed lyric ending provides a stronger phrase boundary for a vocal tail than stem energy alone.",
                    "section_id": section_id,
                    "source_layers": ["event_features", "sections"],
                }
            )
            existing_keys.add(tail_key)
            lyric_event_index += 1

    hint_events_index = 1
    for hint in _load_human_hints(paths):
        hint_start = float(hint.get("start_time", 0.0))
        hint_end = float(hint.get("end_time", hint_start))
        if hint_end <= hint_start:
            continue
        rows = _event_feature_rows(event_features, hint_start, hint_end)
        if not rows:
            continue
        text = _hint_text(hint)
        section_id = rows[0].get("section_id")

        drums_mean = _mean([float(row["derived"].get("drums_stem_score", 0.0)) for row in rows])
        vocals_mean = _mean([float(row["derived"].get("vocals_stem_score", 0.0)) for row in rows])
        harmonic_mean = _mean([float(row["derived"].get("harmonic_stem_score", 0.0)) for row in rows])
        percussion_focus = _mean([float(row["derived"].get("percussion_focus_score", 0.0)) for row in rows])
        instrumental_focus = _mean([float(row["derived"].get("instrumental_focus_score", 0.0)) for row in rows])

        if any(keyword in text for keyword in ("snare", "ride", "drum", "percussion")):
            key = (round(hint_start, 6), round(hint_end, 6), "percussion_break")
            if key not in existing_keys and drums_mean >= 0.28 and percussion_focus >= 0.08 and vocals_mean <= 0.3:
                refined_events.append(
                    {
                        "id": _event_id("percussion_break", hint_events_index),
                        "type": "percussion_break",
                        "created_by": "analyzer_hint_guided_classifier",
                        "start_time": round(hint_start, 6),
                        "end_time": round(hint_end, 6),
                        "confidence": round(_clamp01(min(1.0, 0.45 + drums_mean * 0.25 + percussion_focus * 0.6)), 6),
                        "intensity": round(_clamp01(max(drums_mean, percussion_focus)), 6),
                        "evidence": {
                            "summary": "Hint-guided percussion pocket confirmed by drum-dominant stem activity and reduced vocal presence.",
                            "source_windows": [
                                {"layer": "event_features", "start_time": round(float(rows[0]["start_time"]), 6), "end_time": round(float(rows[-1]["end_time"]), 6), "ref": f"beats:{rows[0]['beat']}-{rows[-1]['beat']}", "metric_names": ["drums_stem_score", "percussion_focus_score", "vocals_stem_score"]}
                            ],
                            "metrics": [
                                {"name": "drums_stem_mean", "value": drums_mean, "source_layer": "event_features"},
                                {"name": "percussion_focus_mean", "value": percussion_focus, "source_layer": "event_features"},
                                {"name": "hint_window_duration", "value": hint_end - hint_start},
                            ],
                            "reasons": [f"Human hint {hint.get('id')} suggested a percussion-only pocket and the stem evidence is compatible."],
                            "rule_names": ["hint_guided_percussion_break_rule"],
                            "metadata": {"hint_id": hint.get("id"), "hint_title": hint.get("title")},
                        },
                        "notes": "Human hint and stem evidence both point to a drum-led break rather than a full-band event.",
                        "section_id": section_id,
                        "source_layers": ["event_features", "sections"],
                    }
                )
                existing_keys.add(key)
                hint_events_index += 1

        if any(keyword in text for keyword in ("ends slowly", "ends", "tail", "fade", "fades out")):
            previous_rows = _event_feature_rows(event_features, max(0.0, hint_start - 2.0), hint_start)
            previous_vocal_focus = _mean([float(row["derived"].get("vocal_focus_score", 0.0)) for row in previous_rows]) if previous_rows else 0.0
            key = (round(hint_start, 6), round(hint_end, 6), "vocal_tail")
            if key not in existing_keys and previous_vocal_focus >= 0.35 and (previous_vocal_focus - vocals_mean) >= 0.12 and max(harmonic_mean, instrumental_focus, drums_mean) >= 0.12:
                refined_events.append(
                    {
                        "id": _event_id("vocal_tail", hint_events_index),
                        "type": "vocal_tail",
                        "created_by": "analyzer_hint_guided_classifier",
                        "start_time": round(hint_start, 6),
                        "end_time": round(hint_end, 6),
                        "confidence": round(_clamp01(min(1.0, 0.45 + (previous_vocal_focus - vocals_mean) * 0.8)), 6),
                        "intensity": round(_clamp01(max(previous_vocal_focus - vocals_mean, 0.0)), 6),
                        "evidence": {
                            "summary": "Hint-guided vocal decay confirmed by falling vocal stem energy while accompaniment remains active.",
                            "source_windows": [
                                {"layer": "event_features", "start_time": round(hint_start, 6), "end_time": round(hint_end, 6), "ref": f"hint:{hint.get('id')}", "metric_names": ["vocals_stem_score", "harmonic_stem_score", "drums_stem_score"]}
                            ],
                            "metrics": [
                                {"name": "previous_vocal_focus_mean", "value": previous_vocal_focus, "source_layer": "event_features"},
                                {"name": "hint_window_vocals_mean", "value": vocals_mean, "source_layer": "event_features"},
                                {"name": "hint_window_harmonic_mean", "value": harmonic_mean, "source_layer": "event_features"},
                                {"name": "hint_window_drums_mean", "value": drums_mean, "source_layer": "event_features"},
                            ],
                            "reasons": [f"Human hint {hint.get('id')} suggested a vocal ending or fade and the stem evidence shows a decaying handoff."],
                            "rule_names": ["hint_guided_vocal_tail_rule"],
                            "metadata": {"hint_id": hint.get("id"), "hint_title": hint.get("title")},
                        },
                        "notes": "Human hint and stem evidence both point to a trailing vocal handoff rather than a hard phrase stop.",
                        "section_id": section_id,
                        "source_layers": ["event_features", "sections"],
                    }
                )
                existing_keys.add(key)
                hint_events_index += 1

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