from __future__ import annotations

import math

import numpy as np

from analyzer.io import write_json
from analyzer.stages._stem_activity import estimate_stem_activity_by_beat
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
INTERNAL_SPLIT_CONTEXT_BARS = 2
INTERNAL_SPLIT_MIN_SIDE_BARS = 2
INTERNAL_SPLIT_MIN_CONTRAST = 0.9
INTERNAL_SPLIT_MIN_SECTION_ADVANTAGE = 0.28
INTERNAL_SPLIT_MIN_ENERGY_JUMP = 0.12
INTERNAL_SPLIT_MIN_ONSET_JUMP = 0.12
INTERNAL_SPLIT_MIN_DRUM_JUMP = 0.18
INTERNAL_SPLIT_MIN_SUSTAINED_BAR_DELTA = 0.08
SPARSE_BREAK_MOTION_SLACK = 0.01
EARLY_SPARSE_BREAK_ENERGY_SLACK = 0.01
EARLY_SPARSE_BREAK_MOTION_OFFSET = 0.02
ONSET_ANCHOR_MIN_STRENGTH = 0.35


def _uses_reference_timing(timing: dict) -> bool:
    generated_from = timing.get("generated_from", {})
    if not isinstance(generated_from, dict):
        return False
    engine = str(generated_from.get("engine") or "")
    dependencies = generated_from.get("dependencies", {})
    return engine == "reference.moises.chords" or (
        isinstance(dependencies, dict) and "reference_chords" in dependencies
    )


def _find_nearest_onset_peak(
    candidate_time: float,
    onset_peaks: list[dict],
    beat_interval_s: float,
) -> float | None:
    """Return the time of a nearby high-strength onset peak if within ±1 beat and strong enough."""
    best_time: float | None = None
    best_distance = float("inf")
    for peak in onset_peaks:
        peak_time = float(peak["time_s"])
        strength = float(peak["strength"])
        distance = abs(peak_time - candidate_time)
        if distance <= beat_interval_s and strength >= ONSET_ANCHOR_MIN_STRENGTH:
            if distance < best_distance:
                best_time = peak_time
                best_distance = distance
    return best_time


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


def _build_bar_feature_rows(
    timing: dict,
    harmonic: dict,
    energy: dict,
    stem_activity_by_beat: dict[str, list[float]] | None = None,
) -> list[dict[str, object]]:
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
        start_beat_index = max(0, int(beats_in_bar[0]["beat"]) - 1)
        end_beat_index = min(len(energy["beat_features"]), int(beats_in_bar[-1]["beat"]))
        vocals_mean = float(np.mean((stem_activity_by_beat or {}).get("vocals", [0.0])[start_beat_index:end_beat_index] or [0.0]))
        drums_mean = float(np.mean((stem_activity_by_beat or {}).get("drums", [0.0])[start_beat_index:end_beat_index] or [0.0]))
        harmonic_mean = float(np.mean((stem_activity_by_beat or {}).get("harmonic", [0.0])[start_beat_index:end_beat_index] or [0.0]))
        bass_mean = float(np.mean((stem_activity_by_beat or {}).get("bass", [0.0])[start_beat_index:end_beat_index] or [0.0]))
        rows.append(
            {
                "bar": int(bar["bar"]),
                "start_s": start_s,
                "end_s": end_s,
                "energy": energy_mean,
                "onset": onset_mean,
                "flux": flux_mean,
                "vocals": vocals_mean,
                "drums": drums_mean,
                "harmonic": harmonic_mean,
                "bass": bass_mean,
                "vector": np.concatenate(
                    [np.array([energy_mean, onset_mean, flux_mean, vocals_mean, drums_mean, harmonic_mean, bass_mean], dtype=float), chord_histogram]
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
                "vocals": float(np.mean([row["vocals"] for row in chunk])),
                "drums": float(np.mean([row["drums"] for row in chunk])),
                "harmonic": float(np.mean([row["harmonic"] for row in chunk])),
                "bass": float(np.mean([row["bass"] for row in chunk])),
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
        previous["vocals"] = float(np.mean([previous["vocals"], trailing["vocals"]]))
        previous["drums"] = float(np.mean([previous["drums"], trailing["drums"]]))
        previous["harmonic"] = float(np.mean([previous["harmonic"], trailing["harmonic"]]))
        previous["bass"] = float(np.mean([previous["bass"], trailing["bass"]]))
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
        "vocals": float(np.mean([block["vocals"] for block in group])),
        "drums": float(np.mean([block["drums"] for block in group])),
        "harmonic": float(np.mean([block["harmonic"] for block in group])),
        "bass": float(np.mean([block["bass"] for block in group])),
        "vector": vector,
        "preserve_start": bool(any(block.get("preserve_start") for block in group)),
    }


def _merge_bar_rows(rows: list[dict[str, object]], *, preserve_start: bool = False) -> dict[str, object]:
    vector = np.mean(np.vstack([row["vector"] for row in rows]), axis=0)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return {
        "bar_start": int(rows[0]["bar"]),
        "bar_end": int(rows[-1]["bar"]),
        "start_s": float(rows[0]["start_s"]),
        "end_s": float(rows[-1]["end_s"]),
        "bar_count": len(rows),
        "energy": float(np.mean([row["energy"] for row in rows])),
        "onset": float(np.mean([row["onset"] for row in rows])),
        "flux": float(np.mean([row["flux"] for row in rows])),
        "vocals": float(np.mean([row["vocals"] for row in rows])),
        "drums": float(np.mean([row["drums"] for row in rows])),
        "harmonic": float(np.mean([row["harmonic"] for row in rows])),
        "bass": float(np.mean([row["bass"] for row in rows])),
        "vector": vector,
        "preserve_start": preserve_start,
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


def _window_mean(rows: list[dict[str, object]], key: str) -> float:
    return float(np.mean([float(row[key]) for row in rows])) if rows else 0.0


def _best_internal_split_index(section: dict[str, object], bar_rows: list[dict[str, object]], beat_rows: list[dict[str, object]]) -> int | None:
    section_rows = [
        row
        for row in bar_rows
        if int(section["bar_start"]) <= int(row["bar"]) <= int(section["bar_end"])
    ]
    if len(section_rows) < INTERNAL_SPLIT_MIN_SIDE_BARS * 2:
        return None

    contrast_scores: list[tuple[int, float]] = []
    for split_index in range(INTERNAL_SPLIT_MIN_SIDE_BARS, len(section_rows) - INTERNAL_SPLIT_MIN_SIDE_BARS + 1):
        candidate_time = float(section_rows[split_index]["start_s"])
        contrast = _boundary_contrast_at_time(candidate_time, beat_rows)
        if contrast is not None:
            contrast_scores.append((split_index, contrast))

    if not contrast_scores:
        return None

    section_mean_contrast = float(np.mean([score for _, score in contrast_scores]))
    best_index: int | None = None
    best_score = float("-inf")
    best_time = float("-inf")

    for split_index, contrast in contrast_scores:
        left_context = section_rows[split_index - INTERNAL_SPLIT_CONTEXT_BARS:split_index]
        right_context = section_rows[split_index:split_index + INTERNAL_SPLIT_CONTEXT_BARS]
        if len(left_context) < INTERNAL_SPLIT_CONTEXT_BARS or len(right_context) < INTERNAL_SPLIT_CONTEXT_BARS:
            continue

        left_energy = _window_mean(left_context, "energy")
        right_energy = _window_mean(right_context, "energy")
        left_onset = _window_mean(left_context, "onset")
        right_onset = _window_mean(right_context, "onset")
        left_drums = _window_mean(left_context, "drums")
        right_drums = _window_mean(right_context, "drums")
        sustained_energy = min(float(row["energy"]) for row in right_context) >= (left_energy + INTERNAL_SPLIT_MIN_SUSTAINED_BAR_DELTA)
        sustained_onset = min(float(row["onset"]) for row in right_context) >= (left_onset + INTERNAL_SPLIT_MIN_SUSTAINED_BAR_DELTA)

        if contrast < INTERNAL_SPLIT_MIN_CONTRAST:
            continue
        if contrast < section_mean_contrast + INTERNAL_SPLIT_MIN_SECTION_ADVANTAGE:
            continue
        if (right_energy - left_energy) < INTERNAL_SPLIT_MIN_ENERGY_JUMP:
            continue
        if (right_onset - left_onset) < INTERNAL_SPLIT_MIN_ONSET_JUMP:
            continue
        if (right_drums - left_drums) < INTERNAL_SPLIT_MIN_DRUM_JUMP:
            continue
        if not sustained_energy or not sustained_onset:
            continue

        candidate_time = float(section_rows[split_index]["start_s"])
        if contrast > best_score + 1e-9 or (math.isclose(contrast, best_score) and candidate_time > best_time):
            best_index = split_index
            best_score = contrast
            best_time = candidate_time

    return best_index


def _apply_internal_section_splits(grouped_sections: list[dict[str, object]], bar_rows: list[dict[str, object]], beat_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    split_sections: list[dict[str, object]] = []
    for section in grouped_sections:
        split_index = _best_internal_split_index(section, bar_rows, beat_rows)
        if split_index is None:
            split_sections.append(section)
            continue

        section_rows = [
            row
            for row in bar_rows
            if int(section["bar_start"]) <= int(row["bar"]) <= int(section["bar_end"])
        ]
        split_sections.append(_merge_bar_rows(section_rows[:split_index], preserve_start=bool(section.get("preserve_start", False))))
        split_sections.append(_merge_bar_rows(section_rows[split_index:], preserve_start=True))
    return split_sections


def _section_character_labels(sections: list[dict[str, object]]) -> list[str]:
    if not sections:
        return []

    energies = np.array([section["energy"] for section in sections], dtype=float)
    motions = np.array([(float(section["onset"]) + float(section["flux"])) / 2.0 for section in sections], dtype=float)
    repetitions = np.array(_compute_section_repetition(sections), dtype=float)
    vocals = np.array([float(section.get("vocals", 0.0)) for section in sections], dtype=float)
    drums = np.array([float(section.get("drums", 0.0)) for section in sections], dtype=float)
    harmonic = np.array([float(section.get("harmonic", 0.0)) for section in sections], dtype=float)
    bass = np.array([float(section.get("bass", 0.0)) for section in sections], dtype=float)
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
        vocal_value = float(vocals[index])
        drum_value = float(drums[index])
        harmonic_value = float(harmonic[index])
        bass_value = float(bass[index])
        previous_energy = float(energies[index - 1]) if index > 0 else energy_value
        energy_delta = energy_value - previous_energy
        next_energy = float(energies[index + 1]) if index + 1 < len(sections) else energy_value
        next_motion = float(motions[index + 1]) if index + 1 < len(sections) else motion_value
        next_drums = float(drums[index + 1]) if index + 1 < len(sections) else drum_value

        if index == 0:
            if vocal_value >= 0.45 and drum_value <= 0.2:
                labels.append("vocal_spotlight")
            else:
                labels.append("ambient_opening")
            continue
        if index == len(sections) - 1:
            labels.append("release_tail")
            continue
        if (
            repetition_value < repetition_median
            and (next_energy - energy_value) >= 0.12
            and next_motion >= motion_high
            and next_drums >= 0.45
        ):
            labels.append("contrast_bridge")
            continue
        if vocal_value >= max(drum_value + 0.2, harmonic_value * 0.8) and drum_value <= (motion_low + 0.05):
            if energy_value >= energy_high:
                labels.append("vocal_lift")
            else:
                labels.append("vocal_spotlight")
            continue
        if (harmonic_value + bass_value) >= 0.7 and vocal_value <= 0.25 and drum_value <= 0.45:
            labels.append("instrumental_bed")
            continue
        if (harmonic_value >= 0.45 and drum_value <= 0.3 and energy_delta >= 0.04 and vocal_value <= 0.25):
            labels.append("arpeggiated_lift")
            continue
        if (
            energy_delta >= ENTRY_ENERGY_JUMP_THRESHOLD
            and motion_value >= motion_high
            and drum_value >= 0.45
            and (vocal_value >= 0.1 or bass_value >= 0.35 or harmonic_value >= 0.12)
        ):
            labels.append("momentum_lift")
            continue
        if drum_value >= 0.55 and harmonic_value <= 0.35 and vocal_value <= 0.25:
            labels.append("percussion_break")
            continue
        if energy_value >= energy_peak and (repetition_value >= repetition_median or motion_value >= motion_high):
            labels.append("focal_lift")
            continue
        if energy_delta >= 0.04 and motion_value >= motion_high:
            labels.append("momentum_lift")
            continue
        if energy_value <= energy_low and motion_value <= (motion_low + SPARSE_BREAK_MOTION_SLACK):
            labels.append("breath_space")
            continue
        if index == 1 and energy_value <= (energy_low + EARLY_SPARSE_BREAK_ENERGY_SLACK) and motion_value <= (motion_high - EARLY_SPARSE_BREAK_MOTION_OFFSET):
            labels.append("breath_space")
            continue
        if repetition_value < repetition_median and (motion_value >= motion_high or abs(energy_delta) >= 0.05):
            labels.append("contrast_bridge")
            continue
        if motion_value >= motion_high or energy_value >= energy_high:
            labels.append("groove_plateau")
            continue
        labels.append("flowing_plateau")
    return labels


def _find_micro_break_candidates(bar_rows: list[dict], sections: list[SectionWindow]) -> list[dict]:
    """Identify 1-4 bar energy/percussion pockets within sections that are not already a boundary.

    Returns a list of micro-break dicts with: start_s, end_s, bar_count, break_type ('pause_break'|'percussion_break'|'breath_space').
    """
    section_boundaries = {round(float(s.start), 3) for s in sections}
    candidates = []
    n = len(bar_rows)
    index = 0
    while index < n:
        row = bar_rows[index]
        # Look for low-energy / percussion-dominant windows that are not already section boundaries
        energy = float(row.get("energy", 1.0))
        drums = float(row.get("drums", 0.0))
        vocals = float(row.get("vocals", 0.0))
        onset = float(row.get("onset", 1.0))
        start_s = float(row.get("start_s", 0.0))

        # A "pocket" bar is one with low energy OR dominant drums with no vocals
        is_pocket = (energy <= 0.25) or (drums >= 0.55 and vocals <= 0.2 and onset <= 0.5)
        if not is_pocket:
            index += 1
            continue

        # Scan forward to find the end of the pocket window
        pocket_end = index
        while pocket_end < n:
            r = bar_rows[pocket_end]
            e = float(r.get("energy", 1.0))
            d = float(r.get("drums", 0.0))
            v = float(r.get("vocals", 0.0))
            o = float(r.get("onset", 1.0))
            still_pocket = (e <= 0.30) or (d >= 0.55 and v <= 0.2 and o <= 0.55)
            if still_pocket:
                pocket_end += 1
            else:
                break

        bar_count = pocket_end - index
        if 1 <= bar_count <= 4:
            end_s = float(bar_rows[pocket_end - 1].get("end_s", bar_rows[pocket_end - 1].get("start_s", start_s)))
            # Skip if this pocket is already exactly aligned with a section boundary
            if round(start_s, 3) not in section_boundaries:
                avg_drums = float(np.mean([float(bar_rows[i].get("drums", 0.0)) for i in range(index, pocket_end)]))
                avg_energy = float(np.mean([float(bar_rows[i].get("energy", 0.0)) for i in range(index, pocket_end)]))
                if bar_count <= 2:
                    break_type = "pause_break"
                elif avg_drums >= 0.55 and avg_energy >= 0.25:
                    break_type = "percussion_break"
                else:
                    break_type = "breath_space"
                candidates.append({
                    "start_s": round(start_s, 6),
                    "end_s": round(end_s, 6),
                    "bar_count": bar_count,
                    "break_type": break_type,
                })

        index = max(pocket_end, index + 1)
    return candidates


def _apply_micro_breaks(
    sections: list[SectionWindow],
    micro_breaks: list[dict],
) -> tuple[list[SectionWindow], list[dict]]:
    """Split any 3-4-bar breaks out as standalone sections.  1-2-bar breaks are returned as metadata only."""
    split_sections: list[SectionWindow] = list(sections)
    metadata_breaks: list[dict] = []
    new_insertions: list[SectionWindow] = []

    for mb in micro_breaks:
        bar_count = int(mb["bar_count"])
        if bar_count <= 2:
            # Short pockets: annotate as metadata
            metadata_breaks.append(mb)
            continue

        # 3-4 bar pockets: split out as a section if fully inside an existing section
        mb_start = float(mb["start_s"])
        mb_end = float(mb["end_s"])
        for sec_index, sec in enumerate(split_sections):
            if sec is None:
                continue
            if sec.start < mb_start and mb_end < sec.end:
                label = str(mb["break_type"])
                confidence = round(max(0.4, sec.confidence * 0.8), 6)
                # left fragment
                new_insertions.append(SectionWindow(
                    section_id=sec.section_id,
                    start=sec.start,
                    end=round(mb_start, 6),
                    label=sec.label,
                    section_character=sec.section_character,
                    confidence=sec.confidence,
                    onset_anchored=sec.onset_anchored,
                ))
                # break pocket
                new_insertions.append(SectionWindow(
                    section_id=f"{sec.section_id}_break",
                    start=round(mb_start, 6),
                    end=round(mb_end, 6),
                    label=label,
                    section_character=label,
                    confidence=confidence,
                    onset_anchored=False,
                ))
                # right fragment
                new_insertions.append(SectionWindow(
                    section_id=f"{sec.section_id}_post",
                    start=round(mb_end, 6),
                    end=sec.end,
                    label=sec.label,
                    section_character=sec.section_character,
                    confidence=sec.confidence,
                    onset_anchored=sec.onset_anchored,
                ))
                split_sections[sec_index] = None  # type: ignore[assignment]
                break
        else:
            metadata_breaks.append(mb)

    # Rebuild section list: replace None with new_insertions, preserve order
    result: list[SectionWindow] = []
    insertion_map: dict[int, list[SectionWindow]] = {}
    for i, sec in enumerate(split_sections):
        if sec is None:
            pass
        else:
            result.append(sec)

    # Rebuild more carefully: find None positions and splice in new_insertions in order
    result = []
    ni_iter = iter(new_insertions)
    for sec in split_sections:
        if sec is None:
            try:
                result.append(next(ni_iter))  # left
                result.append(next(ni_iter))  # break
                result.append(next(ni_iter))  # right
            except StopIteration:
                pass
        else:
            result.append(sec)

    # Re-number section IDs
    final: list[SectionWindow] = []
    for idx, sec in enumerate(result):
        final.append(SectionWindow(
            section_id=f"section-{idx + 1:03d}",
            start=sec.start,
            end=sec.end,
            label=sec.label,
            section_character=sec.section_character,
            confidence=sec.confidence,
            onset_anchored=sec.onset_anchored,
        ))

    return final, metadata_breaks


