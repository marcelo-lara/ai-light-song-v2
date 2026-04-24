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


