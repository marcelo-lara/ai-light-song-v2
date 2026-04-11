from __future__ import annotations

import math

import numpy as np

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION, SectionWindow, to_jsonable
from analyzer.paths import SongPaths

BLOCK_SIZE_BARS = 8
MERGE_SIMILARITY_THRESHOLD = 0.9
MERGE_ENERGY_DELTA_THRESHOLD = 0.06
ENTRY_ENERGY_JUMP_THRESHOLD = 0.08
LOCAL_BOUNDARY_SEARCH_BEATS = 4
LOCAL_BOUNDARY_CONTEXT_BEATS = 4
LOCAL_BOUNDARY_DISTANCE_PENALTY = 0.12
LOCAL_BOUNDARY_MIN_IMPROVEMENT = 0.03
INTRO_BOUNDARY_PRESERVE_THRESHOLD = 1.5
SPARSE_BREAK_MOTION_SLACK = 0.01
EARLY_SPARSE_BREAK_ENERGY_SLACK = 0.01
EARLY_SPARSE_BREAK_MOTION_OFFSET = 0.02


def _snap_to_bar_boundary(candidate_time: float, bar_starts: list[float]) -> float:
    best = bar_starts[0]
    best_distance = abs(candidate_time - best)
    for boundary in bar_starts[1:]:
        distance = abs(candidate_time - boundary)
        if distance < best_distance or (math.isclose(distance, best_distance) and boundary > best):
            best = boundary
            best_distance = distance
    return best


def _note_index() -> dict[str, int]:
    return {
        "C": 0,
        "C#": 1,
        "D": 2,
        "D#": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "G": 7,
        "G#": 8,
        "A": 9,
        "A#": 10,
        "B": 11,
    }


def _active_chord_root(chord_events: list[dict], time_s: float) -> str | None:
    for event in chord_events:
        start_s = float(event["time"])
        end_s = float(event["end_s"])
        if start_s <= time_s < end_s:
            return str(event["chord"]).rstrip("m")
    if chord_events:
        return str(chord_events[-1]["chord"]).rstrip("m")
    return None


def _build_bar_feature_rows(timing: dict, harmonic: dict, energy: dict) -> list[dict[str, object]]:
    beat_features = energy["beat_features"]
    note_index = _note_index()
    rows: list[dict[str, object]] = []
    for bar in timing["bars"]:
        start_s = float(bar["start_s"])
        end_s = float(bar["end_s"])
        beats_in_bar = [row for row in beat_features if start_s <= float(row["time"]) < end_s]
        if not beats_in_bar:
            continue

        chord_histogram = np.zeros(12, dtype=float)
        for event in harmonic["chords"]:
            overlap = min(end_s, float(event["end_s"])) - max(start_s, float(event["time"]))
            if overlap <= 0:
                continue
            root = str(event["chord"]).rstrip("m")
            if root in note_index:
                chord_histogram[note_index[root]] += overlap

        chord_norm = np.linalg.norm(chord_histogram)
        if chord_norm > 0:
            chord_histogram = chord_histogram / chord_norm

        energy_mean = float(np.mean([row["loudness_avg"] for row in beats_in_bar]))
        onset_mean = float(np.mean([row["onset_density"] for row in beats_in_bar]))
        flux_mean = float(np.mean([row["flux_avg"] for row in beats_in_bar]))
        rows.append(
            {
                "bar": int(bar["bar"]),
                "start_s": start_s,
                "end_s": end_s,
                "energy": energy_mean,
                "onset": onset_mean,
                "flux": flux_mean,
                "vector": np.concatenate(
                    [np.array([energy_mean, onset_mean, flux_mean], dtype=float), chord_histogram]
                ),
            }
        )
    return rows


def _build_beat_feature_rows(harmonic: dict, energy: dict) -> list[dict[str, object]]:
    note_index = _note_index()
    rows: list[dict[str, object]] = []
    beat_features = sorted(energy["beat_features"], key=lambda row: float(row["time"]))
    chord_events = sorted(harmonic["chords"], key=lambda event: float(event["time"]))
    for beat in beat_features:
        time_s = float(beat["time"])
        chord_histogram = np.zeros(12, dtype=float)
        root = _active_chord_root(chord_events, time_s)
        if root in note_index:
            chord_histogram[note_index[root]] = 1.0
        rows.append(
            {
                "time": time_s,
                "energy": float(beat["loudness_avg"]),
                "onset": float(beat["onset_density"]),
                "flux": float(beat["flux_avg"]),
                "vector": np.concatenate(
                    [
                        np.array(
                            [
                                float(beat["loudness_avg"]),
                                float(beat["onset_density"]),
                                float(beat["flux_avg"]),
                            ],
                            dtype=float,
                        ),
                        chord_histogram,
                    ]
                ),
            }
        )
    return rows


def _build_phrase_blocks(bar_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    for index in range(0, len(bar_rows), BLOCK_SIZE_BARS):
        chunk = bar_rows[index:index + BLOCK_SIZE_BARS]
        if not chunk:
            continue
        vector = np.mean(np.vstack([row["vector"] for row in chunk]), axis=0)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        blocks.append(
            {
                "bar_start": int(chunk[0]["bar"]),
                "bar_end": int(chunk[-1]["bar"]),
                "start_s": float(chunk[0]["start_s"]),
                "end_s": float(chunk[-1]["end_s"]),
                "bar_count": len(chunk),
                "energy": float(np.mean([row["energy"] for row in chunk])),
                "onset": float(np.mean([row["onset"] for row in chunk])),
                "flux": float(np.mean([row["flux"] for row in chunk])),
                "vector": vector,
            }
        )

    if len(blocks) >= 2 and blocks[-1]["bar_count"] < BLOCK_SIZE_BARS:
        previous = blocks[-2]
        trailing = blocks[-1]
        merged_vector = previous["vector"] + trailing["vector"]
        norm = np.linalg.norm(merged_vector)
        previous["bar_end"] = trailing["bar_end"]
        previous["end_s"] = trailing["end_s"]
        previous["bar_count"] += trailing["bar_count"]
        previous["energy"] = float(np.mean([previous["energy"], trailing["energy"]]))
        previous["onset"] = float(np.mean([previous["onset"], trailing["onset"]]))
        previous["flux"] = float(np.mean([previous["flux"], trailing["flux"]]))
        previous["vector"] = merged_vector / norm if norm > 0 else merged_vector
        blocks.pop()

    return blocks


def _boundary_contrast_at_time(candidate_time: float, beat_rows: list[dict[str, object]]) -> float | None:
    boundary_index = _nearest_beat_index(candidate_time, beat_rows)
    if boundary_index is None:
        return None
    score = _boundary_contrast_score(beat_rows, boundary_index)
    if math.isinf(score):
        return None
    return score


def _group_phrase_blocks(blocks: list[dict[str, object]], beat_rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    if not blocks:
        return []

    groups: list[list[dict[str, object]]] = []
    index = 0
    preserve_intro_split = False
    if len(blocks) >= 2:
        first_similarity = float(blocks[0]["vector"] @ blocks[1]["vector"])
        first_energy = (blocks[0]["energy"] + blocks[1]["energy"]) / 2.0
        later_energies = [block["energy"] for block in blocks[2:]]
        later_median = float(np.median(later_energies)) if later_energies else first_energy
        intro_boundary_contrast = _boundary_contrast_at_time(float(blocks[1]["start_s"]), beat_rows)
        preserve_intro_split = (
            intro_boundary_contrast is not None
            and intro_boundary_contrast >= INTRO_BOUNDARY_PRESERVE_THRESHOLD
        )
        if first_similarity >= MERGE_SIMILARITY_THRESHOLD and first_energy < later_median:
            if not preserve_intro_split:
                groups.append([blocks[0], blocks[1]])
                index = 2

    while index < len(blocks):
        current = blocks[index]
        if index == len(blocks) - 1:
            groups.append([current])
            break

        if index == 0 and preserve_intro_split:
            groups.append([current])
            index += 1
            continue

        next_block = blocks[index + 1]
        previous_energy = groups[-1][-1]["energy"] if groups else current["energy"]
        is_entry_jump = (current["energy"] - previous_energy) > ENTRY_ENERGY_JUMP_THRESHOLD
        pair_similarity = float(current["vector"] @ next_block["vector"])
        pair_energy_delta = abs(current["energy"] - next_block["energy"])
        if not is_entry_jump and pair_similarity >= MERGE_SIMILARITY_THRESHOLD and pair_energy_delta <= MERGE_ENERGY_DELTA_THRESHOLD:
            groups.append([current, next_block])
            index += 2
        else:
            groups.append([current])
            index += 1

    return groups


def _merge_group(group: list[dict[str, object]]) -> dict[str, object]:
    vector = np.mean(np.vstack([block["vector"] for block in group]), axis=0)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return {
        "bar_start": int(group[0]["bar_start"]),
        "bar_end": int(group[-1]["bar_end"]),
        "start_s": float(group[0]["start_s"]),
        "end_s": float(group[-1]["end_s"]),
        "bar_count": int(sum(block["bar_count"] for block in group)),
        "energy": float(np.mean([block["energy"] for block in group])),
        "onset": float(np.mean([block["onset"] for block in group])),
        "flux": float(np.mean([block["flux"] for block in group])),
        "vector": vector,
    }


def _compute_section_repetition(sections: list[dict[str, object]]) -> list[float]:
    repetitions = []
    for index, section in enumerate(sections):
        similarities = [
            float(section["vector"] @ other["vector"])
            for other_index, other in enumerate(sections)
            if other_index != index
        ]
        repetitions.append(max(similarities, default=0.0))
    return repetitions


def _nearest_beat_index(candidate_time: float, beat_rows: list[dict[str, object]]) -> int | None:
    if not beat_rows:
        return None
    best_index = 0
    best_distance = abs(float(beat_rows[0]["time"]) - candidate_time)
    for index, beat in enumerate(beat_rows[1:], start=1):
        distance = abs(float(beat["time"]) - candidate_time)
        if distance < best_distance or (math.isclose(distance, best_distance) and float(beat["time"]) > float(beat_rows[best_index]["time"])):
            best_index = index
            best_distance = distance
    return best_index


def _boundary_contrast_score(beat_rows: list[dict[str, object]], boundary_index: int) -> float:
    left_start = boundary_index - LOCAL_BOUNDARY_CONTEXT_BEATS
    right_end = boundary_index + LOCAL_BOUNDARY_CONTEXT_BEATS
    if left_start < 0 or right_end > len(beat_rows):
        return float("-inf")

    left_window = beat_rows[left_start:boundary_index]
    right_window = beat_rows[boundary_index:right_end]
    left_vector = np.mean(np.vstack([row["vector"] for row in left_window]), axis=0)
    right_vector = np.mean(np.vstack([row["vector"] for row in right_window]), axis=0)
    left_norm = float(np.linalg.norm(left_vector))
    right_norm = float(np.linalg.norm(right_vector))
    cosine_similarity = 1.0
    if left_norm > 0 and right_norm > 0:
        cosine_similarity = float((left_vector @ right_vector) / (left_norm * right_norm))

    energy_delta = abs(float(np.mean([row["energy"] for row in right_window])) - float(np.mean([row["energy"] for row in left_window])))
    onset_delta = abs(float(np.mean([row["onset"] for row in right_window])) - float(np.mean([row["onset"] for row in left_window])))
    flux_delta = abs(float(np.mean([row["flux"] for row in right_window])) - float(np.mean([row["flux"] for row in left_window])))
    vector_delta = float(np.linalg.norm(right_vector - left_vector))
    return vector_delta + ((1.0 - cosine_similarity) * 0.75) + (energy_delta * 0.6) + (onset_delta * 0.35) + (flux_delta * 0.25)


def _refine_boundary_to_local_novelty(candidate_time: float, beat_rows: list[dict[str, object]]) -> float:
    if len(beat_rows) < LOCAL_BOUNDARY_CONTEXT_BEATS * 2:
        return candidate_time

    coarse_index = _nearest_beat_index(candidate_time, beat_rows)
    if coarse_index is None:
        return candidate_time

    coarse_score = _boundary_contrast_score(beat_rows, coarse_index)
    best_index = coarse_index
    best_score = coarse_score
    best_distance = 0
    search_start = max(LOCAL_BOUNDARY_CONTEXT_BEATS, coarse_index - LOCAL_BOUNDARY_SEARCH_BEATS)
    search_end = min(len(beat_rows) - LOCAL_BOUNDARY_CONTEXT_BEATS, coarse_index + LOCAL_BOUNDARY_SEARCH_BEATS + 1)
    for boundary_index in range(search_start, search_end):
        distance = abs(boundary_index - coarse_index)
        score = _boundary_contrast_score(beat_rows, boundary_index) - (distance * LOCAL_BOUNDARY_DISTANCE_PENALTY)
        if score > best_score + 1e-9:
            best_index = boundary_index
            best_score = score
            best_distance = distance
            continue
        if math.isclose(score, best_score) and (distance < best_distance or (distance == best_distance and float(beat_rows[boundary_index]["time"]) > float(beat_rows[best_index]["time"]))):
            best_index = boundary_index
            best_distance = distance

    if best_index != coarse_index and best_score >= coarse_score + LOCAL_BOUNDARY_MIN_IMPROVEMENT:
        return float(beat_rows[best_index]["time"])
    return candidate_time


def _section_character_labels(sections: list[dict[str, object]]) -> list[str]:
    if not sections:
        return []

    energies = np.array([section["energy"] for section in sections], dtype=float)
    motions = np.array([(float(section["onset"]) + float(section["flux"])) / 2.0 for section in sections], dtype=float)
    repetitions = np.array(_compute_section_repetition(sections), dtype=float)
    energy_low = float(np.quantile(energies, 0.35))
    energy_high = float(np.quantile(energies, 0.7))
    energy_peak = float(np.quantile(energies, 0.85))
    motion_low = float(np.quantile(motions, 0.35))
    motion_high = float(np.quantile(motions, 0.7))
    repetition_median = float(np.median(repetitions))

    labels: list[str] = []
    for index in range(len(sections)):
        energy_value = float(energies[index])
        motion_value = float(motions[index])
        repetition_value = float(repetitions[index])
        previous_energy = float(energies[index - 1]) if index > 0 else energy_value
        energy_delta = energy_value - previous_energy

        if index == 0:
            labels.append("ambient_opening")
            continue
        if index == len(sections) - 1:
            labels.append("release_tail")
            continue
        if energy_value >= energy_peak and (repetition_value >= repetition_median or motion_value >= motion_high):
            labels.append("peak_lift")
            continue
        if energy_delta >= 0.04 and motion_value >= motion_high:
            labels.append("rising_drive")
            continue
        if energy_value <= energy_low and motion_value <= (motion_low + SPARSE_BREAK_MOTION_SLACK):
            labels.append("sparse_break")
            continue
        if index == 1 and energy_value <= (energy_low + EARLY_SPARSE_BREAK_ENERGY_SLACK) and motion_value <= (motion_high - EARLY_SPARSE_BREAK_MOTION_OFFSET):
            labels.append("sparse_break")
            continue
        if repetition_value < repetition_median and (motion_value >= motion_high or abs(energy_delta) >= 0.05):
            labels.append("tense_transition")
            continue
        if motion_value >= motion_high or energy_value >= energy_high:
            labels.append("driving_pulse")
            continue
        labels.append("steady_flow")
    return labels


def segment_sections(paths: SongPaths, timing: dict, harmonic: dict, energy: dict) -> dict:
    bar_rows = _build_bar_feature_rows(timing, harmonic, energy)
    beat_rows = _build_beat_feature_rows(harmonic, energy)
    blocks = _build_phrase_blocks(bar_rows)
    grouped_sections = [_merge_group(group) for group in _group_phrase_blocks(blocks, beat_rows)]
    labels = _section_character_labels(grouped_sections)
    repetitions = _compute_section_repetition(grouped_sections)

    bar_starts = [float(bar["start_s"]) for bar in timing["bars"]]
    section_starts = []
    for index, section in enumerate(grouped_sections):
        coarse_start = _snap_to_bar_boundary(float(section["start_s"]), bar_starts)
        if index > 0:
            coarse_start = _refine_boundary_to_local_novelty(coarse_start, beat_rows)
            if coarse_start <= section_starts[-1]:
                coarse_start = _snap_to_bar_boundary(float(section["start_s"]), bar_starts)
        section_starts.append(coarse_start)

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
            )
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
            "snapping_rule": "coarse section starts snap to the nearest bar boundary, then nearby beat boundaries within the local novelty window may refine the final cut when contrast evidence is stronger",
            "label_strategy": "lighting-oriented section_character labels from section-scale energy, motion, repetition, and contrast cues",
            "annotation_strategy": "structural change windows are primary; section_character labels are auxiliary lighting metadata",
        },
        "sections": sections,
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("section_segmentation", "sections.json"), payload)
    return payload
