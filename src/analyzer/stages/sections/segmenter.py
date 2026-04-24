from __future__ import annotations
from typing import Any
import re
from uuid import uuid4

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths
from analyzer.stages._stem_activity import estimate_stem_activity_by_beat

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

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
            "snapping_rule": "coarse section starts snap to the nearest bar boundary; inferred timing may refine those starts to nearby beat boundaries when novelty contrast is materially stronger, while reference-promoted timing keeps section starts on canonical bar anchors",
            "label_strategy": "context-aware musical-state section_character labels from section-scale energy, motion, repetition, and contrast cues",
            "annotation_strategy": "structural change windows are primary; section_character labels are auxiliary lighting metadata",
        },
        "sections": sections,
        "micro_breaks": metadata_breaks,
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("section_segmentation", "sections.json"), payload)
    return payload
