"""v1.1 Phase 2 — two-axis section labelling.

* `infer_form_family` (item 1a/2.1): a song-level `dance_form` / `song_form` /
  `hybrid` / `unknown` label from **audio evidence only**. The inferred genre
  label is explicitly not an input (its confidence is near-constant across the
  corpus and its errors are whole-song). A human-confirmed `form_family` in
  `song_facts.json` breaks ties only when the measured evidence is weak.
* `assign_form_roles` (item 2.2): a per-section `form_role` from a controlled
  vocabulary, assigned by deterministic rules and gated by `form_family`.
  `unknown` is a first-class output.
* `compute_repetition_groups` (item 2.3): `repetition_group` / `variant_of` /
  `similarity` from combined harmonic+timbral self-similarity, never the label.
"""

from __future__ import annotations

from statistics import mean, pstdev

import numpy as np

from .utils import LOCAL_BOUNDARY_CONTEXT_BEATS, _compute_section_repetition, _nearest_beat_index

# beat_rows["vector"] layout: [loudness, onset, flux, *chord_histogram(12)]
_CHANNELS = {
    "energy": slice(0, 1),
    "timbral": slice(1, 3),
    "harmonic": slice(3, 15),
}

# Full fused vocabulary. Which values are admissible is gated per song by
# form_family (see FORM_FAMILY_ROLES).
FORM_ROLE_VOCAB = (
    "intro", "verse", "pre_chorus", "chorus", "hook", "bridge", "breakdown",
    "build", "drop", "post_drop", "instrumental", "outro", "unknown",
)

FORM_FAMILY_ROLES: dict[str, set[str]] = {
    "dance_form": {"intro", "build", "drop", "post_drop", "breakdown", "instrumental", "outro", "unknown"},
    "song_form": {"intro", "verse", "pre_chorus", "chorus", "hook", "bridge", "instrumental", "outro", "unknown"},
    "hybrid": set(FORM_ROLE_VOCAB),
    "unknown": {"intro", "instrumental", "outro", "unknown"},
}

# Below this inferred confidence a human-confirmed form_family breaks the tie.
FORM_FAMILY_TIE_CONFIDENCE = 0.55


def _channel_boundary_strength(beat_rows: list[dict], boundary_index: int, channel: slice) -> float:
    """Cosine distance between the mean feature vector on each side of the
    boundary, restricted to one feature channel. 0 = identical, 1 = orthogonal."""
    left = beat_rows[max(0, boundary_index - LOCAL_BOUNDARY_CONTEXT_BEATS):boundary_index]
    right = beat_rows[boundary_index:boundary_index + LOCAL_BOUNDARY_CONTEXT_BEATS]
    if not left or not right:
        return 0.0
    left_vec = np.mean(np.vstack([np.asarray(row["vector"])[channel] for row in left]), axis=0)
    right_vec = np.mean(np.vstack([np.asarray(row["vector"])[channel] for row in right]), axis=0)
    left_norm = float(np.linalg.norm(left_vec))
    right_norm = float(np.linalg.norm(right_vec))
    if left_norm < 1e-9 or right_norm < 1e-9:
        # A channel that goes silent on one side is itself a strong boundary.
        return 1.0 if (left_norm < 1e-9) != (right_norm < 1e-9) else 0.0
    cosine = float((left_vec @ right_vec) / (left_norm * right_norm))
    return max(0.0, min(1.0, 1.0 - cosine))


def boundary_confidence(
    beat_rows: list[dict],
    bar_starts: list[float],
    boundary_time: float,
    *,
    onset_anchored: bool,
    form_role_margin: float | None,
    beat_interval_s: float,
) -> dict:
    """v1.1 item 3.1 — confidence in a section boundary and its label, composed
    ONLY of boundary/label evidence. Loudness, repetition count and onset
    *level* are deliberately excluded; the value is free to span [0, 1].
    """
    boundary_index = _nearest_beat_index(boundary_time, beat_rows)
    if boundary_index is None:
        return {"value": 0.25, "terms": {"reason": "no beat grid"}}

    strengths = {name: _channel_boundary_strength(beat_rows, boundary_index, sl) for name, sl in _CHANNELS.items()}
    mean_strength = float(np.mean(list(strengths.values())))
    # Detector agreement: high when the three channels report a similar strength.
    spread = float(np.std(list(strengths.values())))
    agreement = mean_strength * max(0.0, 1.0 - spread / 0.35)

    # Novelty-peak sharpness: is the boundary a local maximum of total contrast?
    def _total(idx: int) -> float:
        return sum(_channel_boundary_strength(beat_rows, idx, sl) for sl in _CHANNELS.values())
    here = _total(boundary_index)
    neighbours = [_total(boundary_index + offset) for offset in (-2, -1, 1, 2)
                  if 0 <= boundary_index + offset < len(beat_rows)]
    best_neighbour = max(neighbours) if neighbours else 0.0
    sharpness = max(0.0, min(1.0, (here - best_neighbour) / max(here, 1e-6) + 0.5)) if here > 0 else 0.0

    # Transient alignment.
    transient = 1.0 if onset_anchored else 0.35

    # Bar-grid alignment.
    nearest_bar_gap = min((abs(boundary_time - bar) for bar in bar_starts), default=beat_interval_s)
    bar_grid = max(0.0, 1.0 - nearest_bar_gap / max(beat_interval_s, 1e-6))

    # form_role margin (label certainty).
    role_margin = max(0.0, min(1.0, (form_role_margin or 0.0) / 0.4))

    # All sub-terms are in [0, 1]; weights sum to 1.0 so the value can reach
    # either end of the range.
    value = (
        0.34 * min(1.0, mean_strength / 0.4)
        + 0.24 * min(1.0, agreement / 0.4)
        + 0.16 * sharpness
        + 0.13 * transient
        + 0.08 * bar_grid
        + 0.05 * role_margin
    )
    value = max(0.0, min(1.0, value))
    return {
        "value": round(value, 6),
        "terms": {
            "channel_strengths": {k: round(v, 6) for k, v in strengths.items()},
            "mean_strength": round(mean_strength, 6),
            "detector_agreement": round(agreement, 6),
            "novelty_sharpness": round(sharpness, 6),
            "transient_aligned": onset_anchored,
            "bar_grid_alignment": round(bar_grid, 6),
            "form_role_margin": round(role_margin, 6),
        },
    }


def _scalars(grouped_sections: list[dict], key: str) -> list[float]:
    return [float(section.get(key, 0.0)) for section in grouped_sections]


def infer_form_family(
    grouped_sections: list[dict],
    timing: dict,
    song_facts: dict | None = None,
) -> dict:
    beats = [float(beat["time"]) for beat in timing.get("beats", [])]
    intervals = [later - earlier for earlier, later in zip(beats, beats[1:]) if later > earlier]
    if intervals and mean(intervals) > 0:
        tempo_cv = pstdev(intervals) / mean(intervals) if len(intervals) > 1 else 0.0
    else:
        tempo_cv = 1.0
    tempo_stable = tempo_cv < 0.05

    bass_values = _scalars(grouped_sections, "bass")
    drums_values = _scalars(grouped_sections, "drums")
    vocals_values = _scalars(grouped_sections, "vocals")

    bass_range = (max(bass_values) - min(bass_values)) if bass_values else 0.0
    has_bass_dropout = (
        bool(bass_values)
        and bass_range >= 0.35
        and min(bass_values) < 0.28
        and max(bass_values) > 0.55
    )
    steady_kick = bool(drums_values) and mean(drums_values) >= 0.40 and tempo_stable

    repetitions = _compute_section_repetition(grouped_sections)
    vocal_indices = [i for i, value in enumerate(vocals_values) if value >= 0.35]
    recurring_vocal = (
        len(vocal_indices) >= 2
        and mean(repetitions[i] for i in vocal_indices) >= 0.60
    )

    dance_score = (
        0.34 * (1.0 if tempo_stable else 0.0)
        + 0.33 * (1.0 if steady_kick else 0.0)
        + 0.33 * (1.0 if has_bass_dropout else 0.0)
    )
    song_score = (
        0.5 * (1.0 if recurring_vocal else 0.0)
        + 0.5 * min(1.0, len(vocal_indices) / max(1, len(grouped_sections)) * 2.0)
    )

    dance_present = dance_score >= 0.60
    song_present = song_score >= 0.55

    if dance_present and song_present:
        value, confidence = "hybrid", min(0.95, 0.45 + 0.5 * min(dance_score, song_score))
    elif dance_present:
        value, confidence = "dance_form", min(0.95, 0.4 + 0.55 * dance_score)
    elif song_present:
        value, confidence = "song_form", min(0.95, 0.4 + 0.55 * song_score)
    else:
        value, confidence = "unknown", max(0.15, 0.4 * max(dance_score, song_score))

    result = {
        "value": value,
        "confidence": round(float(confidence), 6),
        "provenance": "inferred",
        "evidence": {
            "tempo_cv": round(float(tempo_cv), 6),
            "tempo_stable": tempo_stable,
            "steady_kick": steady_kick,
            "has_bass_dropout": has_bass_dropout,
            "bass_range": round(float(bass_range), 6),
            "recurring_vocal_sections": recurring_vocal,
            "vocal_section_count": len(vocal_indices),
            "dance_score": round(float(dance_score), 6),
            "song_score": round(float(song_score), 6),
        },
    }

    human_value = None
    if song_facts:
        entry = song_facts.get("form_family")
        if isinstance(entry, dict):
            human_value = entry.get("value")
        elif isinstance(entry, str):
            human_value = entry
    if human_value in FORM_FAMILY_ROLES:
        if human_value == value:
            result["provenance"] = "human-confirmed"
        elif confidence < FORM_FAMILY_TIE_CONFIDENCE:
            result["evidence"]["inferred_value"] = value
            result["value"] = human_value
            result["provenance"] = "human-confirmed"
            result["confidence"] = round(max(confidence, 0.6), 6)
        else:
            result["evidence"]["human_form_family"] = human_value
            result["evidence"]["human_form_family_conflicts"] = True

    return result


def compute_repetition_groups(grouped_sections: list[dict], *, variant_threshold: float = 0.80,
                              same_threshold: float = 0.985) -> list[dict]:
    """Assign A/B/C repetition groups from vector self-similarity.

    A section joins the first existing group whose first occurrence it matches at
    >= `variant_threshold`; it is a literal repeat at >= `same_threshold` and a
    variant otherwise. Uses the combined harmonic+timbral `vector` only.
    """
    groups: list[dict] = []
    assignments: list[dict] = []
    next_letter = ord("A")

    def _vec(section: dict) -> np.ndarray:
        vector = np.asarray(section["vector"], dtype=float)
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector

    for index, section in enumerate(grouped_sections):
        vector = _vec(section)
        best_group = None
        best_similarity = 0.0
        for group in groups:
            similarity = float(vector @ group["vector"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_group = group
        if best_group is not None and best_similarity >= variant_threshold:
            is_repeat = best_similarity >= same_threshold
            assignments.append({
                "repetition_group": best_group["letter"],
                "variant_of": None if is_repeat else best_group["first_section_index"],
                "similarity": round(best_similarity, 6),
            })
        else:
            letter = chr(next_letter)
            next_letter += 1
            groups.append({"letter": letter, "vector": vector, "first_section_index": index})
            assignments.append({
                "repetition_group": letter,
                "variant_of": None,
                "similarity": 1.0,
            })
    return assignments


# form_role rules ---------------------------------------------------------- #

def _role_scores(section: dict, context: dict) -> dict[str, float]:
    """Deterministic per-role evidence scores in [0, 1]. Higher = better fit."""
    energy = float(section.get("energy", 0.0))
    onset = float(section.get("onset", 0.0))
    vocals = float(section.get("vocals", 0.0))
    drums = float(section.get("drums", 0.0))
    bass = float(section.get("bass", 0.0))
    harmonic = float(section.get("harmonic", 0.0))
    is_first = context["is_first"]
    is_last = context["is_last"]
    prev_energy = context["prev_energy"]
    energy_rank = context["energy_rank"]  # 0..1 within song
    repetition = context["repetition"]

    scores: dict[str, float] = {}
    scores["intro"] = 0.95 if is_first else (0.3 if energy_rank < 0.3 and context["index"] <= 1 else 0.0)
    scores["outro"] = 0.95 if is_last else (0.25 if energy_rank < 0.35 and context["index"] >= context["count"] - 2 else 0.0)
    scores["verse"] = min(1.0, 0.4 + vocals * 0.6 - drums * 0.15) if vocals >= 0.3 and energy_rank < 0.7 else 0.0
    scores["chorus"] = min(1.0, 0.3 + vocals * 0.4 + energy_rank * 0.4 + repetition * 0.2) if vocals >= 0.3 and energy_rank >= 0.55 else 0.0
    scores["pre_chorus"] = 0.5 if (vocals >= 0.25 and prev_energy is not None and energy > prev_energy and energy_rank < 0.8 and not is_last) else 0.0
    scores["hook"] = min(1.0, 0.3 + repetition * 0.4 + energy_rank * 0.3) if repetition >= 0.7 and vocals >= 0.25 and energy_rank >= 0.5 else 0.0
    scores["bridge"] = 0.45 if (0.3 <= energy_rank <= 0.7 and repetition < 0.6 and not is_first and not is_last) else 0.0
    scores["breakdown"] = min(1.0, 0.3 + (1.0 - energy_rank) * 0.5 + (bass < 0.3) * 0.3) if energy_rank < 0.4 and prev_energy is not None and energy < prev_energy and not is_last else 0.0
    scores["build"] = min(1.0, 0.3 + onset * 0.4 + (prev_energy is not None and energy > prev_energy) * 0.3) if prev_energy is not None and energy > prev_energy + 0.05 and energy_rank < 0.85 and not is_last else 0.0
    scores["drop"] = min(1.0, 0.25 + energy_rank * 0.5 + bass * 0.3) if energy_rank >= 0.75 and drums >= 0.35 else 0.0
    scores["post_drop"] = 0.4 if (prev_energy is not None and energy < prev_energy and energy_rank >= 0.4 and drums >= 0.3) else 0.0
    scores["instrumental"] = min(1.0, 0.3 + (0.3 - vocals) + drums * 0.3) if vocals < 0.15 else 0.0
    scores["unknown"] = 0.30  # floor: emitted when nothing else clears it
    return scores


def assign_form_roles(grouped_sections: list[dict], repetitions: list[float], form_family: str) -> list[dict]:
    admissible = FORM_FAMILY_ROLES.get(form_family, FORM_FAMILY_ROLES["unknown"])
    energies = [float(section.get("energy", 0.0)) for section in grouped_sections]
    lo, hi = (min(energies), max(energies)) if energies else (0.0, 1.0)
    span = hi - lo if hi > lo else 1.0
    count = len(grouped_sections)

    assignments: list[dict] = []
    for index, section in enumerate(grouped_sections):
        context = {
            "index": index,
            "count": count,
            "is_first": index == 0,
            "is_last": index == count - 1,
            "prev_energy": energies[index - 1] if index > 0 else None,
            "energy_rank": (energies[index] - lo) / span,
            "repetition": float(repetitions[index]) if index < len(repetitions) else 0.0,
        }
        scores = _role_scores(section, context)
        ranked = sorted(
            ((role, value) for role, value in scores.items() if role in admissible),
            key=lambda item: item[1],
            reverse=True,
        )
        if not ranked:
            ranked = [("unknown", 0.3)]
        best_role, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = round(best_score - second_score, 6)
        # Low absolute score or a thin margin -> unknown is the honest answer.
        if best_score < 0.4 or (margin < 0.08 and best_role != "unknown"):
            best_role = "unknown"
        assignments.append({
            "form_role": best_role,
            "form_role_confidence": round(min(0.95, 0.35 + best_score * 0.5 + margin * 0.3), 6),
            "form_role_margin": margin,
        })
    return assignments
