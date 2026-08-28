from __future__ import annotations
from typing import Any
import re
from uuid import uuid4

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths
from analyzer.stages._stem_activity import estimate_stem_activity_by_beat
from analyzer.stages.validation.sections import _validate_sections

from .utils import (
    _uses_reference_timing, _find_nearest_onset_peak, _snap_to_bar_boundary,
    _note_index, _active_chord_root, _build_bar_feature_rows,
    _build_beat_feature_rows, _build_phrase_blocks, _boundary_contrast_at_time,
    _group_phrase_blocks, _merge_group, _merge_bar_rows,
    _compute_section_repetition, _nearest_beat_index, _boundary_contrast_score,
    _refine_boundary_to_local_novelty, _window_mean, _best_internal_split_index,
    _apply_internal_section_splits, _section_character_labels,
    _find_micro_break_candidates, _apply_micro_breaks, SectionWindow
)

SECTION_RESCUE_TOLERANCE_SECONDS = 2.0
SECTION_RESCUE_MIN_SNAP_LIKE_BOUNDARIES = 2
SECTION_RESCUE_MIN_BOUNDARY_CONFIDENCE = 0.6


def _section_key(section: dict[str, Any]) -> tuple[float, float, str | None]:
    return (
        round(float(section["start"]), 6),
        round(float(section["end"]), 6),
        str(section.get("label")) if section.get("label") is not None else None,
    )


def _inferred_section_payload(paths: SongPaths, sections: list[SectionWindow], metadata_breaks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
            "engine": "deterministic.section_segmentation.v1",
            "snapping_rule": "coarse section starts snap to the nearest bar boundary; inferred timing may refine those starts to nearby beat boundaries when novelty contrast is materially stronger, while reference-promoted timing keeps section starts on canonical bar anchors",
            "label_strategy": "context-aware musical-state section_character labels from section-scale energy, motion, repetition, and contrast cues",
            "annotation_strategy": "structural change windows are primary; section_character labels are auxiliary lighting metadata",
        },
        "sections": sections,
        "micro_breaks": metadata_breaks,
    }


def _should_promote_sections(inferred_payload: dict[str, Any], validation_result: Any) -> tuple[bool, dict[str, Any]]:
    diagnostics = dict(validation_result.diagnostics or {})
    sections = [dict(section) for section in inferred_payload.get("sections", [])]
    non_intro_sections = sections[1:] if len(sections) > 1 else sections
    low_confidence_boundaries = sum(
        1 for section in non_intro_sections if float(section.get("confidence", 0.0)) < SECTION_RESCUE_MIN_BOUNDARY_CONFIDENCE
    )
    snap_like_boundary_count = int(diagnostics.get("snap_like_boundary_count", 0))
    match_ratio = float(validation_result.match_ratio) if validation_result.match_ratio is not None else 1.0
    should_promote = bool(
        validation_result.status == "failed"
        or (snap_like_boundary_count >= SECTION_RESCUE_MIN_SNAP_LIKE_BOUNDARIES and low_confidence_boundaries > 0)
    )
    promotion_gate = {
        "type": "section_boundary_reference_rescue",
        "tolerance_seconds": SECTION_RESCUE_TOLERANCE_SECONDS,
        "match_ratio": round(match_ratio, 6),
        "validation_status": validation_result.status,
        "snap_like_boundary_count": snap_like_boundary_count,
        "low_confidence_boundary_count": low_confidence_boundaries,
        "boundary_offset_direction": diagnostics.get("boundary_offset_direction"),
        "rescue_applied": should_promote,
    }
    return should_promote, promotion_gate


def _dominant_inferred_section(
    inferred_sections: list[dict[str, Any]],
    start_time: float,
    end_time: float,
) -> dict[str, Any] | None:
    best_section: dict[str, Any] | None = None
    best_overlap = -1.0
    for section in inferred_sections:
        overlap = max(
            0.0,
            min(end_time, float(section["end"])) - max(start_time, float(section["start"])),
        )
        if overlap > best_overlap:
            best_section = section
            best_overlap = overlap
    return best_section


def _build_reference_promoted_sections(
    paths: SongPaths,
    inferred_payload: dict[str, Any],
    promotion_gate: dict[str, Any],
    *,
    song_end: float,
) -> dict[str, Any]:
    reference_path = paths.reference("moises", "segments.json")
    if reference_path is None or not reference_path.exists():
        return inferred_payload

    reference_rows = [dict(row) for row in read_json(reference_path) if isinstance(row, dict)]
    reference_rows.sort(key=lambda row: float(row.get("start", 0.0)))
    inferred_sections = [dict(section) for section in inferred_payload.get("sections", [])]
    inferred_path = paths.artifact("section_segmentation", "sections.inferred.json")
    promoted_sections: list[SectionWindow] = []

    for index, row in enumerate(reference_rows):
        start_time = round(float(row.get("start", 0.0)), 6)
        explicit_end = row.get("end")
        if explicit_end is not None:
            end_time = round(float(explicit_end), 6)
        elif index + 1 < len(reference_rows):
            end_time = round(float(reference_rows[index + 1].get("start", song_end)), 6)
        else:
            end_time = round(song_end, 6)
        if end_time <= start_time:
            continue
        inferred_section = _dominant_inferred_section(inferred_sections, start_time, end_time)
        label = inferred_section.get("label") if inferred_section else None
        section_character = inferred_section.get("section_character") if inferred_section else label
        confidence = float(inferred_section.get("confidence", 0.6)) if inferred_section else 0.6
        promoted_sections.append(
            SectionWindow(
                section_id=f"section-{index + 1:03d}",
                start=start_time,
                end=end_time,
                label=label,
                section_character=section_character,
                confidence=round(max(0.55, confidence), 6),
                onset_anchored=False,
            )
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
            "reference_segments_file": str(reference_path),
            "engine": "reference.moises.segments.promotion",
            "dependencies": {
                "reference_segments": str(reference_path),
                "inferred_sections_file": str(inferred_path),
            },
            "promotion_gate": promotion_gate,
            "label_strategy": "reference boundaries with inferred section_character carry-over from the dominant overlapping inferred window",
            "annotation_strategy": "canonical boundaries may be reference-promoted while labels remain inference-driven",
        },
        "sections": promoted_sections,
        "micro_breaks": [],
        "metadata": {
            "promotion_applied": True,
            "inferred_section_count": len(inferred_sections),
            "promoted_section_count": len(promoted_sections),
        },
    }
    return payload


def segment_sections(paths: SongPaths, timing: dict, harmonic: dict, energy: dict) -> dict:
    beat_times = [float(beat["time"]) for beat in timing.get("beats", [])]
    song_end = float(timing["bars"][-1]["end_s"]) if timing.get("bars") else (beat_times[-1] if beat_times else 0.0)
    stem_activity_by_beat = {
        "vocals": estimate_stem_activity_by_beat(paths.stems_dir / "vocals.wav", beat_times, song_end),
        "drums": estimate_stem_activity_by_beat(paths.stems_dir / "drums.wav", beat_times, song_end),
        "harmonic": estimate_stem_activity_by_beat(paths.stems_dir / "harmonic.wav", beat_times, song_end),
        "bass": estimate_stem_activity_by_beat(paths.stems_dir / "bass.wav", beat_times, song_end),
    }
    bar_rows = _build_bar_feature_rows(timing, harmonic, energy, stem_activity_by_beat)
    beat_rows = _build_beat_feature_rows(harmonic, energy)
    blocks = _build_phrase_blocks(bar_rows)
    grouped_sections = [_merge_group(group) for group in _group_phrase_blocks(blocks, beat_rows)]
    grouped_sections = _apply_internal_section_splits(grouped_sections, bar_rows, beat_rows)
    labels = _section_character_labels(grouped_sections)
    repetitions = _compute_section_repetition(grouped_sections)
    reference_timing = _uses_reference_timing(timing)

    bar_starts = [float(bar["start_s"]) for bar in timing["bars"]]
    beat_times = [float(beat["time"]) for beat in timing.get("beats", [])]
    beat_interval_s = float(
        sorted(beat_times[i + 1] - beat_times[i] for i in range(len(beat_times) - 1))[len(beat_times) // 2]
    ) if len(beat_times) >= 2 else 0.5
    onset_peaks = energy.get("onset_peaks", [])

    section_starts: list[float] = []
    section_onset_anchored: list[bool] = []
    for index, section in enumerate(grouped_sections):
        coarse_start = _snap_to_bar_boundary(float(section["start_s"]), bar_starts)
        if index > 0 and not reference_timing and not bool(section.get("preserve_start", False)):
            coarse_start = _refine_boundary_to_local_novelty(coarse_start, beat_rows)
            if coarse_start <= section_starts[-1]:
                coarse_start = _snap_to_bar_boundary(float(section["start_s"]), bar_starts)

        # Story 4.2: prefer exact onset timestamp when a strong transient is within ±1 beat and ≤50ms latency
        anchored = False
        if index > 0 and onset_peaks:
            onset_time = _find_nearest_onset_peak(coarse_start, onset_peaks, beat_interval_s * 2)
            if onset_time is not None:
                coarse_start = onset_time
                anchored = True

        section_starts.append(coarse_start)
        section_onset_anchored.append(anchored)

    # Story 4.2 acceptance criterion: the first section must always start at 0.0.
    if section_starts:
        section_starts[0] = 0.0
        section_onset_anchored[0] = False

    sections = []
    for index, (section, label, repetition) in enumerate(zip(grouped_sections, labels, repetitions)):
        start = section_starts[index]
        end = float(section["end_s"])
        if index + 1 < len(grouped_sections):
            end = section_starts[index + 1]
        confidence = max(0.2, min(0.99, 0.35 + (section["energy"] * 0.25) + (repetition * 0.25) + (section["onset"] * 0.15)))
        sections.append(
            SectionWindow(
                section_id=f"section-{index + 1:03d}",
                start=round(start, 6),
                end=round(end, 6),
                label=label,
                section_character=label,
                confidence=round(float(confidence), 6),
                onset_anchored=section_onset_anchored[index],
            )
        )

    micro_breaks = _find_micro_break_candidates(bar_rows, sections)
    sections, metadata_breaks = _apply_micro_breaks(sections, micro_breaks)

    inferred_payload = _inferred_section_payload(paths, sections, metadata_breaks)
    inferred_payload = to_jsonable(inferred_payload)
    write_json(paths.artifact("section_segmentation", "sections.inferred.json"), inferred_payload)

    validation_result = _validate_sections(paths, inferred_payload, SECTION_RESCUE_TOLERANCE_SECONDS)
    should_promote, promotion_gate = _should_promote_sections(inferred_payload, validation_result)
    if should_promote:
        payload = _build_reference_promoted_sections(
            paths,
            inferred_payload,
            promotion_gate,
            song_end=song_end,
        )
    else:
        payload = inferred_payload
        payload.setdefault("generated_from", {})["promotion_gate"] = promotion_gate
        payload.setdefault("metadata", {})["promotion_applied"] = False

    payload = to_jsonable(payload)
    write_json(paths.artifact("section_segmentation", "sections.json"), payload)
    return payload
