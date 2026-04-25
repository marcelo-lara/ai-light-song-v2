from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION, round_schema_float
from analyzer.paths import SongPaths


PRIMARY_PROFILES = (
    "aggressive",
    "anthemic",
    "uplifting",
    "percussive",
    "hypnotic",
    "ambient",
    "dreamy",
    "tense",
    "release",
)

DEFAULT_PRESET_LIBRARY: tuple[dict[str, Any], ...] = (
    {"preset_id": "preset_impact_01", "tags": ["aggressive", "anthemic", "hard_cut_friendly", "strobe_safe"]},
    {"preset_id": "preset_impact_02", "tags": ["aggressive", "percussive", "strobe_safe"]},
    {"preset_id": "preset_drive_01", "tags": ["percussive", "hypnotic", "strobe_safe"]},
    {"preset_id": "preset_drive_02", "tags": ["uplifting", "percussive", "strobe_safe"]},
    {"preset_id": "preset_lift_01", "tags": ["anthemic", "uplifting", "hard_cut_friendly", "strobe_safe"]},
    {"preset_id": "preset_lift_02", "tags": ["uplifting", "release", "strobe_safe"]},
    {"preset_id": "preset_hypno_01", "tags": ["hypnotic", "percussive", "strobe_safe"]},
    {"preset_id": "preset_hypno_02", "tags": ["hypnotic", "tense", "strobe_safe"]},
    {"preset_id": "preset_air_01", "tags": ["ambient", "dreamy", "strobe_safe"]},
    {"preset_id": "preset_air_02", "tags": ["ambient", "release", "strobe_safe"]},
    {"preset_id": "preset_tension_01", "tags": ["tense", "hard_cut_friendly", "strobe_safe"]},
    {"preset_id": "preset_tension_02", "tags": ["tense", "percussive", "strobe_safe"]},
)

SECTION_PAYOFF_WEIGHTS: dict[str, float] = {
    "focal_lift": 1.0,
    "peak_lift": 1.0,
    "momentum_lift": 0.9,
    "groove_plateau": 0.78,
    "flowing_plateau": 0.7,
    "percussion_break": 0.84,
    "contrast_bridge": 0.58,
    "vocal_lift": 0.6,
    "vocal_spotlight": 0.45,
    "instrumental_bed": 0.38,
    "breath_space": 0.2,
    "release_tail": 0.16,
    "ambient_opening": 0.18,
}

SECTION_RELEASE_WEIGHTS: dict[str, float] = {
    "breath_space": 0.95,
    "release_tail": 1.0,
    "ambient_opening": 0.78,
    "vocal_spotlight": 0.58,
    "contrast_bridge": 0.32,
}

SECTION_TENSION_WEIGHTS: dict[str, float] = {
    "contrast_bridge": 0.92,
    "percussion_break": 0.82,
    "momentum_lift": 0.7,
    "focal_lift": 0.62,
    "groove_plateau": 0.48,
}


@dataclass(slots=True)
class SectionMetrics:
    section_id: str
    section_character: str
    start_s: float
    end_s: float
    energy_score: float
    fft_activity_score: float
    brightness_score: float
    transient_score: float
    section_payoff_score: float
    release_score: float
    tension_score: float
    accent_density_score: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(round((len(sorted_values) - 1) * _clamp01(q)))
    return float(sorted_values[index])


def _normalized(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp01((value - low) / (high - low))


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def _load_preset_library(paths: SongPaths) -> tuple[list[dict[str, Any]], str]:
    library_path = paths.artifacts_root.parent / "fixtures" / "beatdrop_preset_library.json"
    if not library_path.exists():
        return [dict(row) for row in DEFAULT_PRESET_LIBRARY], "built-in-default"

    payload = read_json(library_path)
    presets = payload.get("presets", []) if isinstance(payload, dict) else []
    parsed: list[dict[str, Any]] = []
    for index, preset in enumerate(presets):
        preset_id = str(preset.get("preset_id") or preset.get("id") or f"preset_{index + 1:03d}")
        tags = [str(tag) for tag in preset.get("tags", []) if str(tag).strip()]
        if not tags:
            continue
        parsed.append({"preset_id": preset_id, "tags": tags})

    if not parsed:
        return [dict(row) for row in DEFAULT_PRESET_LIBRARY], "built-in-default"
    return parsed, str(library_path)


def _load_fft_rows(fft_payload: dict[str, Any]) -> list[dict[str, float]]:
    bands = fft_payload.get("bands", [])
    frames = fft_payload.get("frames", [])
    high_band_ids = {"upper_mid", "presence", "brilliance"}

    high_indices = [index for index, band in enumerate(bands) if str(band.get("id")) in high_band_ids]
    rows: list[dict[str, float]] = []
    totals: list[float] = []
    for frame in frames:
        levels = [float(level) for level in frame.get("levels", [])]
        total = sum(levels)
        high_total = sum(levels[idx] for idx in high_indices if idx < len(levels))
        fallback_brightness = 0.0 if total <= 1e-9 else high_total / total
        brightness_ratio = float(frame.get("brightness_ratio", fallback_brightness))
        transient_strength = frame.get("transient_strength")
        dropout_strength = frame.get("dropout_strength")
        frame_time = float(frame.get("time", 0.0))
        rows.append(
            {
                "time": frame_time,
                "total": total,
                "brightness_ratio": _clamp01(brightness_ratio),
                "transient_strength": _clamp01(float(transient_strength)) if transient_strength is not None else -1.0,
                "dropout_strength": _clamp01(float(dropout_strength)) if dropout_strength is not None else -1.0,
            }
        )
        totals.append(total)

    # Backward-compatible fallback for older fft_bands artifacts that do not include
    # transient/dropout fields.
    if rows and any(row["transient_strength"] < 0.0 or row["dropout_strength"] < 0.0 for row in rows):
        deltas = [0.0]
        for index in range(1, len(totals)):
            deltas.append(totals[index] - totals[index - 1])
        max_rise = max((delta for delta in deltas if delta > 0.0), default=0.0)
        max_fall = max((-delta for delta in deltas if delta < 0.0), default=0.0)
        for index, row in enumerate(rows):
            rise = max(0.0, deltas[index])
            fall = max(0.0, -deltas[index])
            if row["transient_strength"] < 0.0:
                row["transient_strength"] = 0.0 if max_rise <= 1e-9 else _clamp01(rise / max_rise)
            if row["dropout_strength"] < 0.0:
                row["dropout_strength"] = 0.0 if max_fall <= 1e-9 else _clamp01(fall / max_fall)

    return rows


def _nearest_anchor_ref(boundary_s: float, section_id: str, anchors: list[dict[str, Any]]) -> tuple[str | None, float | None]:
    closest_anchor_id: str | None = None
    closest_delta: float | None = None

    for anchor in anchors:
        anchor_time = float(anchor.get("time_s", 0.0))
        anchor_section = str(anchor.get("section_id", ""))
        anchor_type = str(anchor.get("anchor_type", ""))
        delta = abs(anchor_time - boundary_s)
        if anchor_section == section_id and anchor_type == "section_start" and delta <= 0.12:
            return str(anchor.get("id")), delta
        if closest_delta is None or delta < closest_delta:
            closest_anchor_id = str(anchor.get("id"))
            closest_delta = delta

    if closest_delta is None or closest_delta > 0.2:
        return None, None
    return closest_anchor_id, closest_delta


def _accent_count_in_window(lighting_events: list[dict[str, Any]], start_s: float, end_s: float) -> int:
    return sum(
        1
        for event in lighting_events
        if str(event.get("event_type")) == "accent" and start_s <= float(event.get("time", 0.0)) < end_s
    )


def _boundary_event_bonus(boundary_s: float, timeline_events: list[dict[str, Any]]) -> float:
    strong_types = {"drop", "impact_hit", "breakdown", "energy_reset", "drop_explode", "drop_punch"}
    for event in timeline_events:
        event_type = str(event.get("type", ""))
        event_time = float(event.get("start_time", event.get("time_s", 0.0)))
        if abs(event_time - boundary_s) <= 0.18 and event_type in strong_types:
            return 0.2
    return 0.0


def _profile_scores(metrics: SectionMetrics) -> dict[str, float]:
    stability = _clamp01(1.0 - abs(metrics.energy_score - metrics.fft_activity_score))
    motion = _clamp01((metrics.transient_score * 0.65) + (metrics.accent_density_score * 0.35))

    scores = {
        "aggressive": _clamp01((metrics.energy_score * 0.42) + (metrics.fft_activity_score * 0.32) + (metrics.section_payoff_score * 0.26)),
        "anthemic": _clamp01((metrics.section_payoff_score * 0.52) + (metrics.energy_score * 0.3) + (metrics.brightness_score * 0.18)),
        "uplifting": _clamp01((metrics.energy_score * 0.38) + (metrics.brightness_score * 0.34) + (metrics.release_score * 0.28)),
        "percussive": _clamp01((motion * 0.58) + (metrics.fft_activity_score * 0.24) + (metrics.section_payoff_score * 0.18)),
        "hypnotic": _clamp01((stability * 0.45) + (motion * 0.35) + (metrics.energy_score * 0.2)),
        "ambient": _clamp01((metrics.release_score * 0.55) + ((1.0 - metrics.energy_score) * 0.3) + ((1.0 - motion) * 0.15)),
        "dreamy": _clamp01((metrics.release_score * 0.4) + (metrics.brightness_score * 0.35) + ((1.0 - metrics.fft_activity_score) * 0.25)),
        "tense": _clamp01((metrics.tension_score * 0.52) + (motion * 0.28) + ((1.0 - metrics.release_score) * 0.2)),
        "release": _clamp01((metrics.release_score * 0.62) + ((1.0 - metrics.tension_score) * 0.2) + ((1.0 - metrics.energy_score) * 0.18)),
        "hard_cut_friendly": _clamp01((metrics.section_payoff_score * 0.45) + (metrics.transient_score * 0.4) + (metrics.fft_activity_score * 0.15)),
        "strobe_safe": 1.0,
    }
    return scores


def generate_beatdrop_visual_plan(
    paths: SongPaths,
    *,
    fft_payload: dict[str, Any] | None = None,
    sections_payload: dict[str, Any] | None = None,
    energy_payload: dict[str, Any] | None = None,
    lighting_payload: dict[str, Any] | None = None,
    feature_layers_payload: dict[str, Any] | None = None,
    timeline_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fft_payload = fft_payload or read_json(paths.artifact("essentia", "fft_bands.json"))
    sections_payload = sections_payload or read_json(paths.artifact("section_segmentation", "sections.json"))
    energy_payload = energy_payload or read_json(paths.artifact("layer_c_energy.json"))
    lighting_payload = lighting_payload or read_json(paths.artifact("lighting_events.json"))
    feature_layers_payload = feature_layers_payload or read_json(paths.artifact("music_feature_layers.json"))

    timeline_events: list[dict[str, Any]] = []
    if timeline_payload is None and paths.timeline_output_path.exists():
        timeline_payload = read_json(paths.timeline_output_path)
    if timeline_payload is not None:
        timeline_events = [dict(row) for row in timeline_payload.get("events", [])]

    preset_library, preset_library_source = _load_preset_library(paths)
    sections = [dict(row) for row in sections_payload.get("sections", [])]
    section_energy_rows = [dict(row) for row in energy_payload.get("section_energy", [])]
    lighting_events = [dict(row) for row in lighting_payload.get("lighting_events", [])]
    anchors = [dict(row) for row in feature_layers_payload.get("lighting_context", {}).get("cue_anchors", [])]

    energy_by_section = {str(row.get("section_id")): row for row in section_energy_rows}
    fft_rows = _load_fft_rows(fft_payload)
    transient_values = [row["transient_strength"] for row in fft_rows]
    dropout_values = [row["dropout_strength"] for row in fft_rows]
    transient_threshold = _quantile(transient_values, 0.85)
    dropout_threshold = _quantile(dropout_values, 0.85)
    transient_times = [row["time"] for row in fft_rows if row["transient_strength"] >= transient_threshold and row["transient_strength"] > 0.0]
    dropout_times = [row["time"] for row in fft_rows if row["dropout_strength"] >= dropout_threshold and row["dropout_strength"] > 0.0]

    section_fft_total_values: list[float] = []
    section_brightness_values: list[float] = []
    section_transient_values: list[float] = []
    section_accent_counts: list[int] = []
    section_raw_metrics: list[dict[str, float]] = []

    for section in sections:
        start_s = float(section.get("start", 0.0))
        end_s = float(section.get("end", start_s))
        section_frames = [row for row in fft_rows if start_s <= row["time"] < end_s]
        section_fft_total = _safe_mean([row["total"] for row in section_frames])
        section_brightness = _safe_mean([row["brightness_ratio"] for row in section_frames])
        section_transient_density = _safe_mean([max(row["transient_strength"], row["dropout_strength"]) for row in section_frames])
        accent_count = _accent_count_in_window(lighting_events, start_s, end_s)

        section_fft_total_values.append(section_fft_total)
        section_brightness_values.append(section_brightness)
        section_transient_values.append(section_transient_density)
        section_accent_counts.append(accent_count)
        section_raw_metrics.append(
            {
                "fft_total": section_fft_total,
                "brightness": section_brightness,
                "transient_density": section_transient_density,
                "accent_count": float(accent_count),
            }
        )

    energy_values = [float(row.get("mean", 0.0)) for row in section_energy_rows] or [0.0]
    energy_min, energy_max = min(energy_values), max(energy_values)
    fft_min, fft_max = min(section_fft_total_values or [0.0]), max(section_fft_total_values or [1.0])
    bright_min, bright_max = min(section_brightness_values or [0.0]), max(section_brightness_values or [1.0])
    transient_min, transient_max = min(section_transient_values or [0.0]), max(section_transient_values or [1.0])
    accent_min, accent_max = min(section_accent_counts or [0]), max(section_accent_counts or [1])

    preset_windows: list[dict[str, Any]] = []
    section_repeat_counts: dict[str, int] = {}

    for index, section in enumerate(sections):
        section_id = str(section.get("section_id") or f"section_{index + 1:03d}")
        section_character = str(section.get("section_character") or section.get("label") or "section")
        start_s = float(section.get("start", 0.0))
        end_s = float(section.get("end", start_s))

        section_energy = energy_by_section.get(section_id, {})
        energy_score = _normalized(float(section_energy.get("mean", 0.0)), energy_min, energy_max)

        raw_metrics = section_raw_metrics[index] if index < len(section_raw_metrics) else {
            "fft_total": 0.0,
            "brightness": 0.0,
            "transient_density": 0.0,
            "accent_count": 0.0,
        }
        fft_activity_score = _normalized(raw_metrics["fft_total"], fft_min, fft_max)
        brightness_score = _normalized(raw_metrics["brightness"], bright_min, bright_max)
        transient_score = _normalized(raw_metrics["transient_density"], transient_min, transient_max)
        accent_density_score = _normalized(raw_metrics["accent_count"], float(accent_min), float(accent_max))

        section_payoff_score = float(SECTION_PAYOFF_WEIGHTS.get(section_character, 0.45))
        release_score = float(SECTION_RELEASE_WEIGHTS.get(section_character, 0.35))
        tension_score = float(SECTION_TENSION_WEIGHTS.get(section_character, 0.4))

        metrics = SectionMetrics(
            section_id=section_id,
            section_character=section_character,
            start_s=start_s,
            end_s=end_s,
            energy_score=energy_score,
            fft_activity_score=fft_activity_score,
            brightness_score=brightness_score,
            transient_score=transient_score,
            section_payoff_score=section_payoff_score,
            release_score=release_score,
            tension_score=tension_score,
            accent_density_score=accent_density_score,
        )

        profile_scores = _profile_scores(metrics)
        recommended_profile = max(PRIMARY_PROFILES, key=lambda key: (profile_scores.get(key, 0.0), key))

        window_id = f"preset_window_{index + 1:03d}"
        repeat_index = section_repeat_counts.get(section_character, 0)
        section_repeat_counts[section_character] = repeat_index + 1

        candidate_rows: list[dict[str, Any]] = []
        hard_cut_hint = profile_scores["hard_cut_friendly"] >= 0.62
        for preset in preset_library:
            tags = [str(tag) for tag in preset.get("tags", [])]
            if "strobe_safe" not in tags:
                continue
            candidate_score = 0.0
            for tag in tags:
                candidate_score += profile_scores.get(tag, 0.0)
            if recommended_profile in tags:
                candidate_score += 0.2
            if hard_cut_hint and "hard_cut_friendly" in tags:
                candidate_score += 0.12
            candidate_rows.append(
                {
                    "preset_id": str(preset.get("preset_id")),
                    "score": round_schema_float(_clamp01(candidate_score / max(len(tags), 1)), 3),
                    "tags": tags,
                }
            )

        candidate_rows.sort(key=lambda row: (-float(row["score"]), str(row["preset_id"])))
        if not candidate_rows:
            candidate_rows = [{"preset_id": "preset_fallback_safe", "score": 0.5, "tags": [recommended_profile, "strobe_safe"]}]

        top_candidates = candidate_rows[:3]
        if len(top_candidates) > 1:
            rotate = repeat_index % len(top_candidates)
            top_candidates = top_candidates[rotate:] + top_candidates[:rotate]

        preset_windows.append(
            {
                "id": window_id,
                "start_s": round_schema_float(start_s, 3),
                "end_s": round_schema_float(end_s, 3),
                "section_id": section_id,
                "section_character": section_character,
                "recommended_profile": recommended_profile,
                "candidate_presets": top_candidates,
                "reason": {
                    "energy_score": round_schema_float(metrics.energy_score, 3),
                    "fft_activity_score": round_schema_float(metrics.fft_activity_score, 3),
                    "section_payoff_score": round_schema_float(metrics.section_payoff_score, 3),
                },
            }
        )

    transitions: list[dict[str, Any]] = []
    for index in range(1, len(preset_windows)):
        previous_window = preset_windows[index - 1]
        current_window = preset_windows[index]
        boundary_s = float(current_window["start_s"])

        anchor_ref, anchor_delta = _nearest_anchor_ref(boundary_s, str(current_window["section_id"]), anchors)
        transient_confirmed = any(abs(time_s - boundary_s) <= 0.12 for time_s in transient_times)
        dropout_confirmed = any(abs(time_s - boundary_s) <= 0.12 for time_s in dropout_times)
        event_bonus = _boundary_event_bonus(boundary_s, timeline_events)

        hard_cut_ready = bool(anchor_ref) and (transient_confirmed or dropout_confirmed)
        transition_mode = "hard_cut" if hard_cut_ready else "soft_blend"

        payoff = float(current_window["reason"]["section_payoff_score"])
        fft_strength = float(current_window["reason"]["fft_activity_score"])
        anchor_score = 0.0 if anchor_delta is None else _clamp01(1.0 - (anchor_delta / 0.2))
        transient_score = 1.0 if (transient_confirmed or dropout_confirmed) else 0.0
        confidence = _clamp01((payoff * 0.35) + (fft_strength * 0.25) + (anchor_score * 0.2) + (transient_score * 0.2) + event_bonus)

        transitions.append(
            {
                "id": f"transition_{index + 1:03d}",
                "time_s": round_schema_float(boundary_s, 3),
                "from_preset_window_id": previous_window["id"],
                "to_preset_window_id": current_window["id"],
                "transition_mode": transition_mode,
                "predicted_boundary": True,
                "transient_confirmed": bool(transient_confirmed or dropout_confirmed),
                "anchor_ref": anchor_ref,
                "confidence": round_schema_float(confidence, 3),
            }
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "fft_bands_file": str(paths.artifact("essentia", "fft_bands.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "lighting_events_file": str(paths.artifact("lighting_events.json")),
            "music_feature_layers_file": str(paths.artifact("music_feature_layers.json")),
            "event_timeline_file": str(paths.timeline_output_path) if paths.timeline_output_path.exists() else None,
            "preset_library_source": preset_library_source,
        },
        "global_rules": {
            "selection_mode": "feature_driven",
            "hard_cut_mode": "predictive_offline",
            "strobe_safe": True,
        },
        "preset_windows": preset_windows,
        "transitions": transitions,
    }

    write_json(paths.beatdrop_visual_plan_output_path, payload)

    markdown_lines = [
        f"# BeatDrop Visual Plan: {paths.song_name}",
        "",
        "## Preset Windows",
        "",
    ]
    for window in preset_windows:
        top_preset = window.get("candidate_presets", [{}])[0]
        markdown_lines.append(
            (
                f"- {window['id']} {window['start_s']:.2f}s-{window['end_s']:.2f}s "
                f"section={window['section_id']} profile={window['recommended_profile']} "
                f"top_preset={top_preset.get('preset_id', 'n/a')}"
            )
        )
        markdown_lines.append(
            (
                f"  reason: energy={window['reason']['energy_score']:.2f}, "
                f"fft={window['reason']['fft_activity_score']:.2f}, "
                f"payoff={window['reason']['section_payoff_score']:.2f}"
            )
        )

    markdown_lines.extend(["", "## Transitions", ""])
    for transition in transitions:
        markdown_lines.append(
            (
                f"- {transition['id']} @{transition['time_s']:.2f}s "
                f"mode={transition['transition_mode']} "
                f"predicted_boundary={transition['predicted_boundary']} "
                f"transient_confirmed={transition['transient_confirmed']} "
                f"anchor_ref={transition.get('anchor_ref')} confidence={transition['confidence']:.2f}"
            )
        )

    paths.beatdrop_visual_plan_md_output_path.write_text("\n".join(markdown_lines).rstrip() + "\n", encoding="utf-8")
    return payload
