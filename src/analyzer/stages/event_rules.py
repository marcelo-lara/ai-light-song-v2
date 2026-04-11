from __future__ import annotations

from collections import defaultdict
from typing import Any

from analyzer.event_contracts import validate_song_event_payload
from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


DEFAULT_THRESHOLD_PROFILE = {
    "name": "default",
    "transition": {
        "build_energy_delta": 0.08,
        "build_tension_mean": 0.25,
        "build_energy_mean": 0.45,
        "breakdown_energy_delta": -0.2,
        "breakdown_density_delta": -0.15,
        "drop_energy_delta": 0.22,
        "drop_onset_min": 0.55,
        "drop_bass_min": 0.3,
        "drop_accent_min": 0.3,
        "fake_drop_tension_mean": 0.45,
        "impact_intensity_min": 0.75,
        "pause_gap_seconds": 0.75,
        "pause_energy_max": 0.35
    },
    "state": {
        "groove_energy_min": 0.45,
        "groove_bass_min": 0.35,
        "groove_volatility_max": 0.25,
        "atmo_energy_max": 0.35,
        "atmo_onset_max": 0.3,
        "atmo_volatility_max": 0.2,
        "tension_mean_min": 0.45,
        "no_drop_energy_min": 0.35,
        "no_drop_energy_max": 0.6
    }
}


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _event_window_refs(rows: list[dict], section: dict | None = None) -> list[dict]:
    if not rows:
        return []
    references = [
        {
            "layer": "event_features",
            "start_time": round(float(rows[0]["start_time"]), 6),
            "end_time": round(float(rows[-1]["end_time"]), 6),
            "ref": f"beats:{rows[0]['beat']}-{rows[-1]['beat']}",
            "metric_names": [
                "energy_score",
                "symbolic_density",
                "harmonic_tension_proxy",
            ],
        }
    ]
    if section is not None:
        references.append(
            {
                "layer": "sections",
                "start_time": round(float(section["start"]), 6),
                "end_time": round(float(section["end"]), 6),
                "ref": str(section["section_id"]),
                "metric_names": ["section_character", "confidence"],
            }
        )
    return references


def _build_event(
    *,
    event_id: str,
    event_type: str,
    rows: list[dict],
    section: dict | None,
    confidence: float,
    intensity: float,
    summary: str,
    rule_names: list[str],
    metrics: list[dict],
    notes: str,
    candidates: list[dict] | None = None,
) -> dict[str, Any]:
    event = {
        "id": event_id,
        "type": event_type,
        "start_time": round(float(rows[0]["start_time"]), 6),
        "end_time": round(float(rows[-1]["end_time"]), 6),
        "confidence": round(confidence, 6),
        "intensity": round(intensity, 6),
        "evidence": {
            "summary": summary,
            "source_windows": _event_window_refs(rows, section),
            "metrics": metrics,
            "reasons": [summary],
            "rule_names": rule_names,
        },
        "notes": notes,
        "source_layers": ["event_features", "sections"],
    }
    if section is not None:
        event["section_id"] = section.get("section_id")
        event["section_name"] = section.get("section_character") or section.get("label")
    if candidates:
        event["candidates"] = candidates
    return event


def _merge_anchor_rows(anchor_rows: list[dict]) -> list[list[dict]]:
    if not anchor_rows:
        return []
    merged: list[list[dict]] = [[anchor_rows[0]]]
    for row in anchor_rows[1:]:
        previous = merged[-1][-1]
        contiguous = int(row["beat"]) == int(previous["beat"]) + 1
        same_section = row.get("section_id") == previous.get("section_id")
        if contiguous and same_section:
            merged[-1].append(row)
        else:
            merged.append([row])
    return merged


def _state_section_rows(features: list[dict], section_id: str) -> list[dict]:
    return [row for row in features if row.get("section_id") == section_id]


def generate_rule_candidates(
    paths: SongPaths,
    event_features: dict,
    sections_payload: dict,
    genre_result: dict | None = None,
) -> dict[str, Any]:
    thresholds = DEFAULT_THRESHOLD_PROFILE
    features = [dict(row) for row in event_features.get("features", [])]
    sections = [dict(row) for row in sections_payload.get("sections", [])]
    event_counter: defaultdict[str, int] = defaultdict(int)
    events: list[dict[str, Any]] = []

    def next_event_id(event_type: str) -> str:
        event_counter[event_type] += 1
        return f"rule_{event_type}_{event_counter[event_type]:03d}"

    build_anchors = [
        row
        for row in features
        if float(row["derived"]["energy_delta"]) >= thresholds["transition"]["build_energy_delta"]
        and float(row["rolling"]["short"]["harmonic_tension_mean"]) >= thresholds["transition"]["build_tension_mean"]
        and float(row["rolling"]["short"]["energy_mean"]) >= thresholds["transition"]["build_energy_mean"]
    ]
    for rows in _merge_anchor_rows(build_anchors):
        section = _section_for_time(float(rows[0]["start_time"]), sections)
        energy_mean = _mean([float(row["rolling"]["short"]["energy_mean"]) for row in rows])
        tension_mean = _mean([float(row["rolling"]["short"]["harmonic_tension_mean"]) for row in rows])
        events.append(
            _build_event(
                event_id=next_event_id("build"),
                event_type="build",
                rows=rows,
                section=section,
                confidence=min(1.0, 0.45 + energy_mean * 0.25 + tension_mean * 0.3),
                intensity=min(1.0, energy_mean),
                summary="Rising short-window energy and harmonic tension indicate an obvious build phase.",
                rule_names=["build_energy_rise"],
                metrics=[
                    {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["transition"]["build_energy_mean"], "comparator": ">=", "source_layer": "event_features"},
                    {"name": "harmonic_tension_mean", "value": tension_mean, "threshold": thresholds["transition"]["build_tension_mean"], "comparator": ">=", "source_layer": "event_features"},
                ],
                notes="Merged consecutive build anchors to preserve the multi-beat rise window.",
                candidates=[{"type": "tension_hold", "confidence": max(0.0, tension_mean - 0.1), "notes": "High tension may also read as a held-state."}],
            )
        )

    breakdown_anchors = [
        row
        for row in features
        if float(row["derived"]["energy_delta"]) <= thresholds["transition"]["breakdown_energy_delta"]
        and float(row["derived"]["density_delta"]) <= thresholds["transition"]["breakdown_density_delta"]
    ]
    for rows in _merge_anchor_rows(breakdown_anchors):
        section = _section_for_time(float(rows[0]["start_time"]), sections)
        energy_drop = abs(_mean([float(row["derived"]["energy_delta"]) for row in rows]))
        density_drop = abs(_mean([float(row["derived"]["density_delta"]) for row in rows]))
        events.append(
            _build_event(
                event_id=next_event_id("breakdown"),
                event_type="breakdown",
                rows=rows,
                section=section,
                confidence=min(1.0, 0.45 + energy_drop * 0.3 + density_drop * 0.2),
                intensity=min(1.0, energy_drop),
                summary="Energy and symbolic density both drop sharply across this window.",
                rule_names=["breakdown_dual_drop"],
                metrics=[
                    {"name": "energy_delta", "value": -energy_drop, "threshold": thresholds["transition"]["breakdown_energy_delta"], "comparator": "<=", "source_layer": "event_features"},
                    {"name": "density_delta", "value": -density_drop, "threshold": thresholds["transition"]["breakdown_density_delta"], "comparator": "<=", "source_layer": "event_features"},
                ],
                notes="Breakdown candidates are merged across adjacent negative-delta beats.",
            )
        )

    drop_events: list[dict[str, Any]] = []
    for row in features:
        if not (
            float(row["derived"]["energy_delta"]) >= thresholds["transition"]["drop_energy_delta"]
            and float(row["normalized"]["onset_density"]) >= thresholds["transition"]["drop_onset_min"]
            and float(row["derived"]["bass_activation_score"]) >= thresholds["transition"]["drop_bass_min"]
            and float(row["derived"]["accent_intensity"]) >= thresholds["transition"]["drop_accent_min"]
        ):
            continue
        section = _section_for_time(float(row["start_time"]), sections)
        energy_delta = float(row["derived"]["energy_delta"])
        onset_level = float(row["normalized"]["onset_density"])
        bass_level = float(row["derived"]["bass_activation_score"])
        confidence = min(1.0, 0.45 + energy_delta * 0.2 + onset_level * 0.15 + bass_level * 0.2)
        event = _build_event(
            event_id=next_event_id("drop"),
            event_type="drop",
            rows=[row],
            section=section,
            confidence=confidence,
            intensity=max(float(row["normalized"]["energy_score"]), float(row["derived"]["accent_intensity"])),
            summary="Synchronized rise in energy, onset activity, bass activation, and accent intensity indicates a baseline drop.",
            rule_names=["drop_energy_release"],
            metrics=[
                {"name": "energy_delta", "value": energy_delta, "threshold": thresholds["transition"]["drop_energy_delta"], "comparator": ">=", "source_layer": "event_features"},
                {"name": "onset_density", "value": onset_level, "threshold": thresholds["transition"]["drop_onset_min"], "comparator": ">=", "source_layer": "event_features"},
                {"name": "bass_activation", "value": bass_level, "threshold": thresholds["transition"]["drop_bass_min"], "comparator": ">=", "source_layer": "event_features"},
                {"name": "accent_intensity", "value": float(row["derived"]["accent_intensity"]), "threshold": thresholds["transition"]["drop_accent_min"], "comparator": ">=", "source_layer": "event_features"},
            ],
            notes="Baseline drop candidate without subtype refinement.",
            candidates=[{"type": "impact_hit", "confidence": min(1.0, float(row["derived"]["accent_intensity"]) + 0.1), "notes": "Short accent overlap suggests an impact reading too."}],
        )
        drop_events.append(event)
        events.append(event)

    for row in features:
        if float(row["derived"]["accent_intensity"]) < thresholds["transition"]["impact_intensity_min"]:
            continue
        section = _section_for_time(float(row["start_time"]), sections)
        intensity = float(row["derived"]["accent_intensity"])
        events.append(
            _build_event(
                event_id=next_event_id("impact_hit"),
                event_type="impact_hit",
                rows=[row],
                section=section,
                confidence=min(1.0, 0.4 + intensity * 0.5),
                intensity=intensity,
                summary="Accent intensity crosses the impact threshold on this beat.",
                rule_names=["impact_accent_peak"],
                metrics=[
                    {"name": "accent_intensity", "value": intensity, "threshold": thresholds["transition"]["impact_intensity_min"], "comparator": ">=", "source_layer": "event_features"},
                ],
                notes="Impact hits remain single-beat candidates.",
            )
        )

    pause_rows = [
        row
        for row in features
        if float(row["derived"]["silence_gap_seconds"]) >= thresholds["transition"]["pause_gap_seconds"]
        and float(row["normalized"]["energy_score"]) <= thresholds["transition"]["pause_energy_max"]
    ]
    for row in pause_rows:
        section = _section_for_time(float(row["start_time"]), sections)
        gap = float(row["derived"]["silence_gap_seconds"])
        events.append(
            _build_event(
                event_id=next_event_id("pause_break"),
                event_type="pause_break",
                rows=[row],
                section=section,
                confidence=min(1.0, 0.45 + gap * 0.2),
                intensity=max(0.0, 1.0 - float(row["normalized"]["energy_score"])),
                summary="Silence gap duration and low energy indicate a pause or stop-time break.",
                rule_names=["pause_gap_low_energy"],
                metrics=[
                    {"name": "silence_gap_seconds", "value": gap, "threshold": thresholds["transition"]["pause_gap_seconds"], "comparator": ">=", "source_layer": "event_features"},
                    {"name": "energy_score", "value": float(row["normalized"]["energy_score"]), "threshold": thresholds["transition"]["pause_energy_max"], "comparator": "<=", "source_layer": "event_features"},
                ],
                notes="Pause candidates are kept even when they may precede a later release.",
                candidates=[{"type": "fake_drop", "confidence": min(0.95, float(row["rolling"]["short"]["harmonic_tension_mean"])), "notes": "Held tension may resolve to a fake drop instead of a true pause."}],
            )
        )

    for row in pause_rows:
        next_drop = any(round(float(candidate["start_time"]), 6) > round(float(row["end_time"]), 6) and round(float(candidate["start_time"]), 6) <= round(float(row["end_time"] + 2.0), 6) for candidate in drop_events)
        if next_drop or float(row["rolling"]["short"]["harmonic_tension_mean"]) < thresholds["transition"]["fake_drop_tension_mean"]:
            continue
        section = _section_for_time(float(row["start_time"]), sections)
        events.append(
            _build_event(
                event_id=next_event_id("fake_drop"),
                event_type="fake_drop",
                rows=[row],
                section=section,
                confidence=min(1.0, 0.35 + float(row["rolling"]["short"]["harmonic_tension_mean"]) * 0.4),
                intensity=float(row["rolling"]["short"]["harmonic_tension_mean"]),
                summary="A pause-like break holds tension but is not followed by a qualifying drop window.",
                rule_names=["fake_drop_unresolved_pause"],
                metrics=[
                    {"name": "harmonic_tension_mean", "value": float(row["rolling"]["short"]["harmonic_tension_mean"]), "threshold": thresholds["transition"]["fake_drop_tension_mean"], "comparator": ">=", "source_layer": "event_features"},
                ],
                notes="Fake-drop candidates remain separate from pause_break for review.",
                candidates=[{"type": "pause_break", "confidence": 0.5, "notes": "Window also satisfies the baseline pause rule."}],
            )
        )

    build_sections = {event.get("section_id") for event in events if event["type"] == "build"}
    drop_sections = {event.get("section_id") for event in drop_events}
    for section in sections:
        section_rows = _state_section_rows(features, str(section["section_id"]))
        if not section_rows:
            continue
        energy_values = [float(row["normalized"]["energy_score"]) for row in section_rows]
        onset_values = [float(row["normalized"]["onset_density"]) for row in section_rows]
        bass_values = [float(row["derived"]["bass_activation_score"]) for row in section_rows]
        tension_values = [float(row["derived"]["harmonic_tension_proxy"]) for row in section_rows]
        energy_mean = _mean(energy_values)
        onset_mean = _mean(onset_values)
        bass_mean = _mean(bass_values)
        tension_mean = _mean(tension_values)
        energy_volatility = round(max(energy_values) - min(energy_values), 6)
        section_rows_window = [section_rows[0], section_rows[-1]] if len(section_rows) > 1 else section_rows

        if energy_mean >= thresholds["state"]["groove_energy_min"] and bass_mean >= thresholds["state"]["groove_bass_min"] and energy_volatility <= thresholds["state"]["groove_volatility_max"]:
            events.append(
                _build_event(
                    event_id=next_event_id("groove_loop"),
                    event_type="groove_loop",
                    rows=section_rows_window,
                    section=section,
                    confidence=min(1.0, 0.45 + energy_mean * 0.2 + bass_mean * 0.2),
                    intensity=energy_mean,
                    summary="Stable section energy and bass activation indicate a sustained groove-loop state.",
                    rule_names=["groove_loop_section_state"],
                    metrics=[
                        {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["state"]["groove_energy_min"], "comparator": ">=", "source_layer": "event_features"},
                        {"name": "bass_mean", "value": bass_mean, "threshold": thresholds["state"]["groove_bass_min"], "comparator": ">=", "source_layer": "event_features"},
                        {"name": "energy_volatility", "value": energy_volatility, "threshold": thresholds["state"]["groove_volatility_max"], "comparator": "<=", "source_layer": "event_features"},
                    ],
                    notes="Section-level sustained-state candidate.",
                )
            )

        if energy_mean <= thresholds["state"]["atmo_energy_max"] and onset_mean <= thresholds["state"]["atmo_onset_max"] and energy_volatility <= thresholds["state"]["atmo_volatility_max"]:
            events.append(
                _build_event(
                    event_id=next_event_id("atmospheric_plateau"),
                    event_type="atmospheric_plateau",
                    rows=section_rows_window,
                    section=section,
                    confidence=min(1.0, 0.45 + (1.0 - energy_mean) * 0.2 + (1.0 - onset_mean) * 0.2),
                    intensity=max(0.0, 1.0 - energy_mean),
                    summary="Low-energy low-motion section profile indicates an atmospheric plateau.",
                    rule_names=["atmospheric_plateau_section_state"],
                    metrics=[
                        {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["state"]["atmo_energy_max"], "comparator": "<=", "source_layer": "event_features"},
                        {"name": "onset_mean", "value": onset_mean, "threshold": thresholds["state"]["atmo_onset_max"], "comparator": "<=", "source_layer": "event_features"},
                    ],
                    notes="Section-level held-state candidate.",
                )
            )

        if tension_mean >= thresholds["state"]["tension_mean_min"] and str(section["section_id"]) not in drop_sections:
            events.append(
                _build_event(
                    event_id=next_event_id("tension_hold"),
                    event_type="tension_hold",
                    rows=section_rows_window,
                    section=section,
                    confidence=min(1.0, 0.4 + tension_mean * 0.35),
                    intensity=tension_mean,
                    summary="Sustained harmonic tension stays elevated across the section without a qualifying release.",
                    rule_names=["tension_hold_section_state"],
                    metrics=[
                        {"name": "tension_mean", "value": tension_mean, "threshold": thresholds["state"]["tension_mean_min"], "comparator": ">=", "source_layer": "event_features"},
                    ],
                    notes="Held-state candidate preserved even when overlapping build windows exist.",
                )
            )

        if str(section["section_id"]) in build_sections and str(section["section_id"]) not in drop_sections and thresholds["state"]["no_drop_energy_min"] <= energy_mean <= thresholds["state"]["no_drop_energy_max"]:
            events.append(
                _build_event(
                    event_id=next_event_id("no_drop_plateau"),
                    event_type="no_drop_plateau",
                    rows=section_rows_window,
                    section=section,
                    confidence=min(1.0, 0.4 + tension_mean * 0.25 + energy_mean * 0.15),
                    intensity=energy_mean,
                    summary="Build evidence is present, but the section settles into a plateau without a qualifying drop.",
                    rule_names=["no_drop_plateau_unresolved_build"],
                    metrics=[
                        {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["state"]["no_drop_energy_min"], "comparator": ">=", "source_layer": "event_features"},
                        {"name": "tension_mean", "value": tension_mean, "threshold": thresholds["state"]["tension_mean_min"], "comparator": ">=", "source_layer": "event_features"},
                    ],
                    notes="Unresolved-release candidate preserved for later identifier review.",
                )
            )

    events = sorted(events, key=lambda row: (float(row["start_time"]), float(row["end_time"]), str(row["type"])))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "event_features_file": str(paths.artifact("event_inference", "features.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "genre_file": str(paths.artifact("genre.json")) if genre_result is not None else None,
            "engine": "rule-based-event-detection",
            "threshold_profile": thresholds,
        },
        "review_status": "rule_candidates",
        "notes": "Deterministic baseline candidates with explicit evidence and preserved ambiguities.",
        "metadata": {
            "event_count": len(events),
            "genres": list(genre_result.get("genres", [])) if genre_result else [],
        },
        "events": events,
    }
    validated = validate_song_event_payload(payload)
    write_json(paths.artifact("event_inference", "rule_candidates.json"), validated)
    return validated