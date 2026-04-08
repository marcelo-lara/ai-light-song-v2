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


def _group_phrase_blocks(blocks: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    if not blocks:
        return []

    groups: list[list[dict[str, object]]] = []
    index = 0
    if len(blocks) >= 2:
        first_similarity = float(blocks[0]["vector"] @ blocks[1]["vector"])
        first_energy = (blocks[0]["energy"] + blocks[1]["energy"]) / 2.0
        later_energies = [block["energy"] for block in blocks[2:]]
        later_median = float(np.median(later_energies)) if later_energies else first_energy
        if first_similarity >= MERGE_SIMILARITY_THRESHOLD and first_energy < later_median:
            groups.append([blocks[0], blocks[1]])
            index = 2

    while index < len(blocks):
        current = blocks[index]
        if index == len(blocks) - 1:
            groups.append([current])
            break

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


def _label_sections(sections: list[dict[str, object]]) -> list[str]:
    if not sections:
        return []

    energies = np.array([section["energy"] for section in sections], dtype=float)
    repetitions = np.array(_compute_section_repetition(sections), dtype=float)
    labels = ["verse"] * len(sections)
    labels[0] = "intro"
    labels[-1] = "outro"

    if len(sections) > 2:
        interior_indexes = list(range(1, len(sections) - 1))
        chorus_index = max(interior_indexes, key=lambda index: (energies[index] * 0.7) + (repetitions[index] * 0.3))
        labels[chorus_index] = "chorus"
        chorus_energy = energies[chorus_index]
        median_repetition = float(np.median(repetitions[interior_indexes]))
        median_energy = float(np.median(energies[interior_indexes]))
        for index in interior_indexes:
            if index == chorus_index:
                continue
            is_bridge = (
                repetitions[index] >= median_repetition
                and energies[index] < chorus_energy - 0.03
                and (index > chorus_index or energies[index] < median_energy)
            )
            labels[index] = "bridge" if is_bridge else "verse"

    if len(sections) >= 2 and energies[0] > float(np.median(energies[1:])):
        labels[0] = "verse"
    if len(sections) >= 2 and energies[-1] > float(np.median(energies[:-1])):
        labels[-1] = "bridge"
    return labels


def segment_sections(paths: SongPaths, timing: dict, harmonic: dict, energy: dict) -> dict:
    bar_rows = _build_bar_feature_rows(timing, harmonic, energy)
    blocks = _build_phrase_blocks(bar_rows)
    grouped_sections = [_merge_group(group) for group in _group_phrase_blocks(blocks)]
    labels = _label_sections(grouped_sections)
    repetitions = _compute_section_repetition(grouped_sections)

    bar_starts = [float(bar["start_s"]) for bar in timing["bars"]]
    sections = []
    for index, (section, label, repetition) in enumerate(zip(grouped_sections, labels, repetitions)):
        start = _snap_to_bar_boundary(float(section["start_s"]), bar_starts)
        end = float(section["end_s"])
        if index + 1 < len(grouped_sections):
            end = _snap_to_bar_boundary(float(grouped_sections[index + 1]["start_s"]), bar_starts)
        confidence = max(0.2, min(0.99, 0.35 + (section["energy"] * 0.25) + (repetition * 0.25) + (section["onset"] * 0.15)))
        sections.append(
            SectionWindow(
                section_id=f"section-{index + 1:03d}",
                start=round(start, 6),
                end=round(end, 6),
                label=label,
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
            "snapping_rule": "nearest bar boundary, prefer later boundary on ties",
            "label_strategy": "optional heuristic labels from 8-bar block grouping with section-scale energy and repetition cues",
            "annotation_strategy": "structural change windows are primary; labels are auxiliary metadata",
        },
        "sections": sections,
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("section_segmentation", "sections.json"), payload)
    return payload
