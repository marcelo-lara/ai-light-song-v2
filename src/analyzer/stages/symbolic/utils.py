from __future__ import annotations

from collections import Counter
from pathlib import Path
import math
import json
import subprocess
from statistics import mean, median
import sys

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import ensure_directory, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


SOURCE_CONFIGS = {
    "harmonic": {
        "path_key": "harmonic",
        "onset_threshold": 0.4,
        "frame_threshold": 0.25,
        "minimum_note_length": 90.0,
        "minimum_frequency": 65.0,
        "maximum_frequency": None,
        "promotion_policy": "core",
        "beat_alignment_tolerance_s": 0.30,
    },
    "bass": {
        "path_key": "bass",
        "onset_threshold": 0.3,
        "frame_threshold": 0.2,
        "minimum_note_length": 80.0,
        "minimum_frequency": 32.7,
        "maximum_frequency": 330.0,
        "promotion_policy": "core",
        "beat_alignment_tolerance_s": 0.20,
    },
    "vocals": {
        "path_key": "vocals",
        "onset_threshold": 0.35,
        "frame_threshold": 0.2,
        "minimum_note_length": 70.0,
        "minimum_frequency": 98.0,
        "maximum_frequency": 1400.0,
        "promotion_policy": "candidate",
        "beat_alignment_tolerance_s": 0.30,
    },
    "drums": {
        "path_key": "drums",
        "onset_threshold": 0.45,
        "frame_threshold": 0.35,
        "minimum_note_length": 60.0,
        "minimum_frequency": 36.0,
        "maximum_frequency": 2000.0,
        "promotion_policy": "auxiliary",
        "beat_alignment_tolerance_s": 0.20,
    },
    "full_mix": {
        "path_key": "full_mix",
        "onset_threshold": 0.4,
        "frame_threshold": 0.22,
        "minimum_note_length": 85.0,
        "minimum_frequency": 55.0,
        "maximum_frequency": None,
        "promotion_policy": "candidate",
        "beat_alignment_tolerance_s": 0.20,
    },
}

SOURCE_PRIORITY = {
    "bass": 0,
    "harmonic": 1,
    "vocals": 2,
    "full_mix": 3,
    "drums": 4,
}


def _predict_stem_notes(
    stem_path: str,
    output_dir: Path,
    source_stem: str,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_length: float,
    minimum_frequency: float | None,
    maximum_frequency: float | None,
) -> dict:
    output_json = output_dir / f"{source_stem}.json"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "analyzer.stages._basic_pitch_subprocess",
                stem_path,
                str(output_dir),
                source_stem,
                str(onset_threshold),
                str(frame_threshold),
                str(minimum_note_length),
                "none" if minimum_frequency is None else str(minimum_frequency),
                "none" if maximum_frequency is None else str(maximum_frequency),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise DependencyError("basic-pitch runtime is not available") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        if "basic-pitch" in detail or "tflite-runtime" in detail or "No module named" in detail:
            raise DependencyError("basic-pitch is required for symbolic transcription") from exc
        raise AnalysisError(f"Basic Pitch transcription failed for {stem_path}: {detail}") from exc

    if not output_json.exists():
        raise AnalysisError(f"Basic Pitch did not produce the expected raw cache: {output_json}")
    with output_json.open() as handle:
        return json.load(handle)


def _nearest_beat_alignment(time_s: float, beat_times: list[float], tolerance_seconds: float = 0.2) -> tuple[int | None, float | None]:
    if not beat_times:
        return None, None
    beat_index = min(range(len(beat_times)), key=lambda index: abs(beat_times[index] - time_s))
    delta = float(time_s - beat_times[beat_index])
    if abs(delta) > tolerance_seconds:
        return None, delta
    return beat_index, delta


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _align_note_events(notes: list[dict], timing: dict, sections_payload: dict, *, tolerance_seconds: float = 0.2) -> list[dict]:
    beat_points = timing["beats"]
    beat_times = [float(beat["time"]) for beat in beat_points]
    bars = timing["bars"]
    sections = sections_payload.get("sections", [])

    aligned_notes = []
    for note in notes:
        aligned_beat_index, beat_delta = _nearest_beat_alignment(float(note["time"]), beat_times, tolerance_seconds=tolerance_seconds)
        aligned_bar = None
        aligned_beat = None
        aligned_beat_global = None
        if aligned_beat_index is not None:
            beat = beat_points[aligned_beat_index]
            aligned_bar = int(beat["bar"])
            aligned_beat = int(beat["beat_in_bar"])
            aligned_beat_global = int(beat["index"])
        else:
            for bar in bars:
                if float(bar["start_s"]) <= float(note["time"]) < float(bar["end_s"]):
                    aligned_bar = int(bar["bar"])
                    break

        section = _section_for_time(float(note["time"]), sections)
        aligned = {key: value for key, value in note.items() if key != "pitch_bend"}
        aligned.update(
            {
                "aligned_beat": aligned_beat,
                "aligned_beat_global": aligned_beat_global,
                "aligned_bar": aligned_bar,
                "beat_time_delta": round(float(beat_delta), 6) if beat_delta is not None else None,
                "alignment_resolved": aligned_beat_index is not None,
                "section_id": section.get("section_id") if section else None,
                "section_name": (section.get("section_character") or section.get("label")) if section else None,
                "pitch_bend_step_count": len(note.get("pitch_bend", [])),
            }
        )
        aligned_notes.append(aligned)
    return aligned_notes


def _validate_transcription_source(source_stem: str, notes: list[dict]) -> dict:
    note_count = len(notes)
    confidence_values = [float(note["confidence"]) for note in notes]
    pitch_values = [int(note["pitch"]) for note in notes]
    resolved_count = sum(1 for note in notes if note.get("alignment_resolved"))
    duration_values = [float(note["duration"]) for note in notes]
    low_register_ratio = (
        sum(1 for pitch in pitch_values if pitch <= 55) / note_count if note_count else 0.0
    )
    mid_high_ratio = (
        sum(1 for pitch in pitch_values if pitch >= 60) / note_count if note_count else 0.0
    )

    if source_stem == "bass":
        promote = note_count > 0 and low_register_ratio >= 0.45
        decision = "promoted" if promote else "rejected"
        reason = "bass source passed low-register validation" if promote else "bass source did not sustain enough low-register notes"
    elif source_stem == "harmonic":
        promote = note_count > 0 and (resolved_count / max(note_count, 1)) >= 0.2
        decision = "promoted" if promote else "rejected"
        reason = "harmonic source provides core note texture" if promote else "harmonic source alignment coverage was too low"
    elif source_stem == "vocals":
        promote = note_count > 0 and (mean(confidence_values) if confidence_values else 0.0) >= 0.35 and mid_high_ratio >= 0.5
        decision = "promoted" if promote else "auxiliary_only"
        reason = "vocal melody notes passed confidence and register checks" if promote else "vocal source kept as auxiliary only"
    elif source_stem == "full_mix":
        promote = note_count > 0 and (mean(confidence_values) if confidence_values else 0.0) >= 0.3
        decision = "promoted" if promote else "auxiliary_only"
        reason = "full-mix source complements missing notes from stems" if promote else "full-mix source retained only as raw cache"
    else:
        promote = False
        decision = "auxiliary_only"
        reason = "percussive source analyzed for review but not promoted to the final melodic note stream by default"

    return {
        "source_stem": source_stem,
        "note_count": note_count,
        "alignment_resolved_ratio": round(resolved_count / max(note_count, 1), 6) if note_count else 0.0,
        "confidence_mean": round(mean(confidence_values), 6) if confidence_values else None,
        "confidence_median": round(median(confidence_values), 6) if confidence_values else None,
        "pitch_range": {
            "min": min(pitch_values) if pitch_values else None,
            "max": max(pitch_values) if pitch_values else None,
        },
        "median_duration": round(median(duration_values), 6) if duration_values else None,
        "low_register_ratio": round(low_register_ratio, 6),
        "mid_high_ratio": round(mid_high_ratio, 6),
        "decision": decision,
        "promote_to_final": promote,
        "reason": reason,
    }


def _deduplicate_notes(notes: list[dict]) -> list[dict]:
    deduplicated: list[dict] = []
    for note in sorted(
        notes,
        key=lambda item: (
            float(item["time"]),
            SOURCE_PRIORITY.get(str(item["source_stem"]), 99),
            -float(item["confidence"]),
        ),
    ):
        duplicate = None
        for existing in reversed(deduplicated[-12:]):
            if abs(float(existing["time"]) - float(note["time"])) > 0.075:
                continue
            if abs(int(existing["pitch"]) - int(note["pitch"])) > 1:
                continue
            duplicate = existing
            break
        if duplicate is None:
            deduplicated.append(note)
            continue
        current_priority = SOURCE_PRIORITY.get(str(note["source_stem"]), 99)
        existing_priority = SOURCE_PRIORITY.get(str(duplicate["source_stem"]), 99)
        if current_priority < existing_priority or (
            current_priority == existing_priority and float(note["confidence"]) > float(duplicate["confidence"])
        ):
            deduplicated[deduplicated.index(duplicate)] = note
    deduplicated.sort(key=lambda item: (float(item["time"]), int(item["pitch"]), str(item["source_stem"])))
    return deduplicated


def _safe_mean(values: list[float]) -> float | None:
    return round(float(mean(values)), 6) if values else None


def _notes_in_window(notes: list[dict], start_s: float, end_s: float) -> list[dict]:
    return [
        note
        for note in notes
        if float(note["time"]) < end_s and float(note["end_s"]) > start_s
    ]


def _section_name(section: dict | None) -> str | None:
    if not section:
        return None
    label = section.get("section_character") or section.get("label")
    return str(label) if label is not None else None


def _find_bar_sections(timing: dict, sections_payload: dict) -> dict[int, dict | None]:
    sections = sections_payload.get("sections", [])
    bar_sections: dict[int, dict | None] = {}
    for bar in timing["bars"]:
        midpoint = (float(bar["start_s"]) + float(bar["end_s"])) / 2.0
        bar_sections[int(bar["bar"])] = _section_for_time(midpoint, sections)
    return bar_sections


def _pitch_range_payload(pitches: list[int]) -> dict:
    return {
        "min": min(pitches) if pitches else None,
        "max": max(pitches) if pitches else None,
    }


def _register_label(centroid: float | None) -> str:
    if centroid is None:
        return "unknown"
    if centroid < 48:
        return "low"
    if centroid < 60:
        return "low-mid"
    if centroid < 72:
        return "mid"
    if centroid < 84:
        return "high"
    return "very-high"


def _contour_label(values: list[float]) -> str:
    filtered = [value for value in values if value is not None]
    if len(filtered) < 2:
        return "static"

    head_size = max(1, len(filtered) // 3)
    tail_size = max(1, len(filtered) // 3)
    head_mean = mean(filtered[:head_size])
    tail_mean = mean(filtered[-tail_size:])
    drift = tail_mean - head_mean
    spread = max(filtered) - min(filtered)
    if abs(drift) <= 1.5 and spread <= 3.0:
        return "static"
    if drift >= 3.0:
        return "rising"
    if drift <= -3.0:
        return "falling"
    return "undulating"


def _texture_label(active_note_peak_values: list[int], density_values: list[float]) -> str:
    peak_mean = mean(active_note_peak_values) if active_note_peak_values else 0.0
    density_mean = mean(density_values) if density_values else 0.0
    if peak_mean >= 4 or density_mean >= 3.0:
        return "layered"
    if peak_mean >= 2 or density_mean >= 1.5:
        return "polyphonic"
    if density_mean >= 0.7:
        return "melodic"
    return "sparse"


def _bass_motion_label(bass_notes: list[dict]) -> str:
    ordered = sorted(bass_notes, key=lambda note: float(note["time"]))
    if len(ordered) < 2:
        return "minimal"
    intervals = [
        abs(int(current["pitch"]) - int(previous["pitch"]))
        for previous, current in zip(ordered, ordered[1:])
    ]
    zero_ratio = sum(1 for interval in intervals if interval == 0) / len(intervals)
    median_interval = median(intervals)
    if zero_ratio >= 0.45:
        return "pedal"
    if median_interval <= 2:
        return "stepwise"
    if median_interval >= 5:
        return "leaping"
    return "mixed"


def _compute_density_per_beat(notes: list[dict], timing: dict, sections_payload: dict) -> list[dict]:
    beats = timing["beats"]
    bars = timing["bars"]
    sections = sections_payload.get("sections", [])
    density_rows: list[dict] = []
    for index, beat in enumerate(beats):
        start_s = float(beat["time"])
        if index + 1 < len(beats):
            end_s = float(beats[index + 1]["time"])
        else:
            end_s = float(bars[-1]["end_s"])
        window_notes = _notes_in_window(notes, start_s, end_s)
        section = _section_for_time((start_s + end_s) / 2.0, sections)
        duration = max(end_s - start_s, 1e-6)
        density_rows.append(
            {
                "beat": int(beat["index"]),
                "bar": int(beat["bar"]),
                "beat_in_bar": int(beat["beat_in_bar"]),
                "time": round(start_s, 6),
                "density": round(len(window_notes) / duration, 6),
                "note_count": len(window_notes),
                "section_id": section.get("section_id") if section else None,
                "section_name": _section_name(section),
            }
        )
    return density_rows


def _compute_density_per_bar(notes: list[dict], timing: dict, sections_payload: dict) -> list[dict]:
    bar_sections = _find_bar_sections(timing, sections_payload)
    density_rows: list[dict] = []
    for bar in timing["bars"]:
        bar_number = int(bar["bar"])
        start_s = float(bar["start_s"])
        end_s = float(bar["end_s"])
        window_notes = _notes_in_window(notes, start_s, end_s)
        pitches = [int(note["pitch"]) for note in window_notes]
        centroids = [int(note["pitch"]) for note in window_notes if int(note["pitch"]) >= 48]
        section = bar_sections.get(bar_number)
        active_note_peak = max(
            (
                sum(1 for note in window_notes if float(note["time"]) <= sample_time < float(note["end_s"]))
                for sample_time in (start_s, (start_s + end_s) / 2.0, end_s - 1e-6)
            ),
            default=0,
        )
        density_rows.append(
            {
                "bar": bar_number,
                "start_s": round(start_s, 6),
                "end_s": round(end_s, 6),
                "density": round(len(window_notes) / 4.0, 6),
                "note_count": len(window_notes),
                "active_note_peak": active_note_peak,
                "pitch_range": _pitch_range_payload(pitches),
                "register_centroid": round(float(mean(centroids)), 6) if centroids else None,
                "register_label": _register_label(float(mean(centroids)) if centroids else None),
                "section_id": section.get("section_id") if section else None,
                "section_name": _section_name(section),
            }
        )
    return density_rows


def _section_bar_numbers(section: dict, timing: dict) -> list[int]:
    start_s = float(section["start"])
    end_s = float(section["end"])
    return [
        int(bar["bar"])
        for bar in timing["bars"]
        if float(bar["start_s"]) < end_s and float(bar["end_s"]) > start_s
    ]


def _notes_for_bars(notes: list[dict], bar_numbers: list[int]) -> list[dict]:
    bar_set = set(bar_numbers)
    return [note for note in notes if note.get("aligned_bar") in bar_set]


def _section_summary(section: dict, notes: list[dict], density_per_bar: list[dict], timing: dict) -> dict:
    bar_numbers = _section_bar_numbers(section, timing)
    local_notes = _notes_for_bars(notes, bar_numbers)
    bar_number_set = set(bar_numbers)
    local_bars = [row for row in density_per_bar if int(row["bar"]) in bar_number_set]
    melodic_notes = [note for note in local_notes if str(note["source_stem"]) != "bass"] or local_notes
    melodic_centroids = [float(row["register_centroid"]) for row in local_bars if row["register_centroid"] is not None]
    pitches = [int(note["pitch"]) for note in local_notes]
    sustain_ratio = (
        sum(1 for note in local_notes if float(note["duration"]) >= 0.5) / len(local_notes)
        if local_notes
        else 0.0
    )
    return {
        "section_id": section["section_id"],
        "section_name": _section_name(section),
        "start_s": round(float(section["start"]), 6),
        "end_s": round(float(section["end"]), 6),
        "bar_start": min(bar_numbers) if bar_numbers else None,
        "bar_end": max(bar_numbers) if bar_numbers else None,
        "note_count": len(local_notes),
        "pitch_range": _pitch_range_payload(pitches),
        "register_centroid": _safe_mean([int(note["pitch"]) for note in melodic_notes]),
        "register_label": _register_label(_safe_mean([int(note["pitch"]) for note in melodic_notes])),
        "texture": _texture_label(
            [int(row["active_note_peak"]) for row in local_bars],
            [float(row["density"]) for row in local_bars],
        ),
        "melodic_contour": _contour_label(melodic_centroids),
        "density_mean": _safe_mean([float(row["density"]) for row in local_bars]),
        "repetition_score": 0.0,
        "sustain_ratio": round(float(sustain_ratio), 6),
    }


def _window_signature(notes: list[dict], bar_count: int) -> dict:
    pitches = [int(note["pitch"]) for note in notes]
    if not notes:
        return {
            "vector": [0.0] * 16,
            "contour": "static",
            "register_centroid": None,
            "note_count": 0,
            "density": 0.0,
            "pitch_range": _pitch_range_payload([]),
            "top_pitch_classes": [],
        }

    histogram = [0.0] * 12
    for pitch in pitches:
        histogram[pitch % 12] += 1.0
    hist_norm = math.sqrt(sum(value * value for value in histogram))
    if hist_norm > 0:
        histogram = [value / hist_norm for value in histogram]

    melodic = [note for note in notes if str(note["source_stem"]) != "bass"] or notes
    melodic_centroid = [int(note["pitch"]) for note in melodic]
    contour = _contour_label(melodic_centroid)
    density = len(notes) / max(bar_count, 1)
    range_span = max(pitches) - min(pitches) if pitches else 0
    vector = histogram + [
        density / 16.0,
        (mean(melodic_centroid) if melodic_centroid else 0.0) / 96.0,
        range_span / 48.0,
        (sum(1 for note in notes if float(note["duration"]) >= 0.5) / len(notes)) if notes else 0.0,
    ]
    pitch_class_counts = Counter(pitch % 12 for pitch in pitches)
    top_pitch_classes = [pitch_class for pitch_class, _ in pitch_class_counts.most_common(3)]
    return {
        "vector": vector,
        "contour": contour,
        "register_centroid": _safe_mean(melodic_centroid),
        "note_count": len(notes),
        "density": round(float(density), 6),
        "pitch_range": _pitch_range_payload(pitches),
        "top_pitch_classes": top_pitch_classes,
    }


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _shared_pitch_class_count(left: list[int], right: list[int]) -> int:
    return len(set(left) & set(right))


def _group_code(index: int) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code = ""
    current = index
    while True:
        current, remainder = divmod(current, 26)
        code = letters[remainder] + code
        if current == 0:
            return code
        current -= 1


def _motif_name(index: int) -> str:
    names = [
        "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
    ]
    if index < len(names):
        return names[index]
    return f"group_{index + 1:02d}"


def _phrase_windows(notes: list[dict], timing: dict, sections_payload: dict) -> tuple[list[dict], list[dict], list[dict], float]:
    windows: list[dict] = []
    for section in sections_payload.get("sections", []):
        bar_numbers = _section_bar_numbers(section, timing)
        if not bar_numbers:
            continue
        section_bar_count = len(bar_numbers)
        if section_bar_count >= 8:
            bars_per_window = 4
        elif section_bar_count >= 4:
            bars_per_window = 2
        else:
            bars_per_window = section_bar_count

        for start_index in range(0, len(bar_numbers), bars_per_window):
            window_bars = bar_numbers[start_index:start_index + bars_per_window]
            if not window_bars:
                continue
            window_notes = _notes_for_bars(notes, window_bars)
            start_bar = window_bars[0]
            end_bar = window_bars[-1]
            start_s = next(float(bar["start_s"]) for bar in timing["bars"] if int(bar["bar"]) == start_bar)
            end_s = next(float(bar["end_s"]) for bar in timing["bars"] if int(bar["bar"]) == end_bar)
            signature = _window_signature(window_notes, len(window_bars))
            windows.append(
                {
                    "section_id": section["section_id"],
                    "section_name": _section_name(section),
                    "start_s": round(start_s, 6),
                    "end_s": round(end_s, 6),
                    "start_bar": start_bar,
                    "end_bar": end_bar,
                    "start_beat": 1,
                    "end_beat": 4,
                    "bar_count": len(window_bars),
                    "note_count": signature["note_count"],
                    "density": signature["density"],
                    "melodic_contour": signature["contour"],
                    "register_centroid": signature["register_centroid"],
                    "register_label": _register_label(signature["register_centroid"]),
                    "pitch_range": signature["pitch_range"],
                    "top_pitch_classes": signature["top_pitch_classes"],
                    "vector": signature["vector"],
                    "phrase_group_id": None,
                    "id": None,
                    "label": None,
                }
            )

    groups: list[dict] = []
    for window in windows:
        best_group = None
        best_similarity = 0.0
        for group in groups:
            if group["bar_count"] != window["bar_count"]:
                continue
            if group["contour"] != window["melodic_contour"]:
                continue
            group_centroid = group["register_centroid"]
            window_centroid = window["register_centroid"]
            if group_centroid is not None and window_centroid is not None:
                if abs(float(group_centroid) - float(window_centroid)) > 4.5:
                    continue
            density_delta = abs(float(group["density_mean"]) - float(window["density"])) / max(float(group["density_mean"]), 1.0)
            if density_delta > 0.3:
                continue
            if _shared_pitch_class_count(group["top_pitch_classes"], window["top_pitch_classes"]) < 2:
                continue
            similarity = _cosine_similarity(group["prototype_vector"], window["vector"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_group = group
        if best_group is None or best_similarity < 0.97:
            groups.append(
                {
                    "bar_count": window["bar_count"],
                    "prototype_vector": list(window["vector"]),
                    "contour": window["melodic_contour"],
                    "density_mean": float(window["density"]),
                    "register_centroid": window["register_centroid"],
                    "top_pitch_classes": list(window["top_pitch_classes"]),
                    "windows": [window],
                }
            )
            continue
        count = len(best_group["windows"])
        best_group["windows"].append(window)
        best_group["prototype_vector"] = [
            ((value * count) + new_value) / (count + 1)
            for value, new_value in zip(best_group["prototype_vector"], window["vector"])
        ]
        best_group["density_mean"] = ((float(best_group["density_mean"]) * count) + float(window["density"])) / (count + 1)
        group_centroid = best_group["register_centroid"]
        window_centroid = window["register_centroid"]
        if group_centroid is None:
            best_group["register_centroid"] = window_centroid
        elif window_centroid is not None:
            best_group["register_centroid"] = ((float(group_centroid) * count) + float(window_centroid)) / (count + 1)

    repeated_phrase_groups: list[dict] = []
    motif_groups: list[dict] = []
    repeated_window_count = 0
    for group_index, group in enumerate(sorted(groups, key=lambda item: (-len(item["windows"]), item["windows"][0]["start_s"]))):
        group_code = _group_code(group_index)
        phrase_group_id = f"phrase_group_{group_code}"
        motif_id = f"motif_{_motif_name(group_index)}"
        group_windows = sorted(group["windows"], key=lambda item: item["start_s"])
        for occurrence_index, window in enumerate(group_windows, start=1):
            window["phrase_group_id"] = phrase_group_id
            window["id"] = f"{phrase_group_id}_{occurrence_index}"
            window["label"] = f"Phrase Group {group_code} - Occurrence {occurrence_index}"
        if len(group_windows) >= 2:
            repeated_window_count += len(group_windows)
            repeated_phrase_groups.append(
                {
                    "id": phrase_group_id,
                    "label": f"Phrase Group {group_code}",
                    "occurrence_count": len(group_windows),
                    "phrase_window_ids": [window["id"] for window in group_windows],
                }
            )
            representative = group_windows[0]
            motif_groups.append(
                {
                    "id": motif_id,
                    "label": f"Motif {_motif_name(group_index).replace('_', ' ').title()}",
                    "summary": (
                        f"Repeated {representative['melodic_contour']} {representative['register_label']} register figure "
                        f"across {len(group_windows)} phrase windows."
                    ),
                    "occurrence_count": len(group_windows),
                    "phrase_group_ids": [phrase_group_id],
                    "occurrence_refs": [
                        {
                            "phrase_window_id": window["id"],
                            "start_s": window["start_s"],
                            "end_s": window["end_s"],
                            "start_bar": window["start_bar"],
                            "end_bar": window["end_bar"],
                            "section_id": window["section_id"],
                        }
                        for window in group_windows
                    ],
                }
            )

    for window_index, window in enumerate(sorted(windows, key=lambda item: item["start_s"])):
        if window["id"] is not None:
            continue
        phrase_group_id = f"phrase_group_single_{window_index + 1:03d}"
        window["phrase_group_id"] = phrase_group_id
        window["id"] = f"{phrase_group_id}_1"
        window["label"] = f"Phrase Window {window_index + 1}"

    repetition_score = repeated_window_count / len(windows) if windows else 0.0
    normalized_windows = [
        {
            key: value
            for key, value in window.items()
            if key != "vector"
        }
        for window in sorted(windows, key=lambda item: item["start_s"])
    ]
    return normalized_windows, repeated_phrase_groups, motif_groups, round(float(repetition_score), 6)


def _compute_symbolic_summary(
    notes: list[dict],
    density_per_bar: list[dict],
    section_summaries: list[dict],
    repetition_score: float,
) -> dict:
    melodic_notes = [note for note in notes if str(note["source_stem"]) != "bass"] or notes
    melodic_centroids = [
        float(row["register_centroid"])
        for row in density_per_bar
        if row["register_centroid"] is not None
    ]
    pitches = [int(note["pitch"]) for note in notes]
    bass_notes = [note for note in notes if str(note["source_stem"]) == "bass"]
    sustain_ratio = (
        sum(1 for note in notes if float(note["duration"]) >= 0.5) / len(notes)
        if notes
        else 0.0
    )
    return {
        "note_count": len(notes),
        "pitch_range": _pitch_range_payload(pitches),
        "register_centroid": _safe_mean([int(note["pitch"]) for note in melodic_notes]),
        "register_label": _register_label(_safe_mean([int(note["pitch"]) for note in melodic_notes])),
        "texture": _texture_label(
            [int(row["active_note_peak"]) for row in density_per_bar],
            [float(row["density"]) for row in density_per_bar],
        ),
        "melodic_contour": _contour_label(melodic_centroids),
        "bass_motion": _bass_motion_label(bass_notes),
        "repetition_score": round(float(repetition_score), 6),
        "sustain_ratio": round(float(sustain_ratio), 6),
        "section_count": len(section_summaries),
        "loosely_aligned_note_count": sum(
            1 for note in notes
            if not note.get("alignment_resolved", False) and note.get("beat_time_delta") is not None
        ),
    }


def _global_density_label(density_mean: float | None) -> str:
    if density_mean is None:
        return "unknown density"
    if density_mean >= 18.0:
        return "very dense"
    if density_mean >= 12.0:
        return "dense"
    if density_mean >= 7.0:
        return "moderately dense"
    if density_mean >= 3.0:
        return "light"
    return "sparse"


def _phrase_density_label(density: float | None) -> str:
    if density is None:
        return "unknown activity"
    if density >= 70.0:
        return "high activity"
    if density >= 50.0:
        return "active motion"
    if density >= 30.0:
        return "moderate activity"
    return "restrained activity"


def _repetition_label(score: float | None) -> str:
    if score is None:
        return "unknown repetition"
    if score >= 0.75:
        return "strong repetition"
    if score >= 0.4:
        return "moderate repetition"
    if score >= 0.15:
        return "occasional repetition"
    return "limited repetition"


def _sustain_label(ratio: float | None) -> str:
    if ratio is None:
        return "unknown sustain"
    if ratio >= 0.15:
        return "long-held notes"
    if ratio >= 0.08:
        return "mixed sustain"
    if ratio >= 0.04:
        return "mostly short notes"
    return "clipped note lengths"


def _format_float(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def _build_global_description(symbolic_summary: dict, density_per_bar: list[dict]) -> str:
    density_values = [float(row["density"]) for row in density_per_bar]
    density_mean = mean(density_values) if density_values else None
    return (
        f"{str(symbolic_summary['texture']).capitalize()} {symbolic_summary['register_label']}-register material "
        f"with {symbolic_summary['melodic_contour']} contour, {str(_global_density_label(density_mean))} activity "
        f"({_format_float(density_mean, 1)} notes per bar), {symbolic_summary['bass_motion']} bass movement, "
        f"{_repetition_label(float(symbolic_summary['repetition_score']))}, and {_sustain_label(float(symbolic_summary['sustain_ratio']))}."
    )


def _build_section_descriptions(section_summaries: list[dict]) -> list[dict]:
    descriptions: list[dict] = []
    for summary in section_summaries:
        section_name = summary["section_name"] or summary["section_id"]
        description = (
            f"{str(section_name).capitalize()} spans bars {summary['bar_start']}-{summary['bar_end']} with a {summary['texture']} texture, "
            f"{summary['melodic_contour']} contour, {_global_density_label(summary['density_mean'])} activity "
            f"({_format_float(summary['density_mean'], 1)} notes per bar), {_repetition_label(summary['repetition_score'])}, "
            f"and {_sustain_label(summary['sustain_ratio'])}."
        )
        descriptions.append(
            {
                "section_id": summary["section_id"],
                "section_name": summary["section_name"],
                "description": description,
            }
        )
    return descriptions


def _build_phrase_group_descriptions(phrase_windows: list[dict], motif_summary: dict) -> list[dict]:
    phrase_windows_by_group: dict[str, list[dict]] = {}
    for window in phrase_windows:
        phrase_windows_by_group.setdefault(str(window["phrase_group_id"]), []).append(window)

    motif_by_group: dict[str, dict] = {}
    for motif_group in motif_summary.get("motif_groups", []):
        for phrase_group_id in motif_group.get("phrase_group_ids", []):
            motif_by_group[str(phrase_group_id)] = motif_group

    descriptions: list[dict] = []
    for phrase_group in motif_summary.get("repeated_phrase_groups", []):
        group_id = str(phrase_group["id"])
        windows = sorted(phrase_windows_by_group.get(group_id, []), key=lambda item: float(item["start_s"]))
        if not windows:
            continue
        density_mean = mean(float(window["density"]) for window in windows)
        dominant_section = Counter(
            str(window["section_name"] or window["section_id"])
            for window in windows
        ).most_common(1)[0][0]
        contours = Counter(str(window["melodic_contour"]) for window in windows)
        contour = contours.most_common(1)[0][0]
        motif_group = motif_by_group.get(group_id)
        motif_id = motif_group.get("id") if motif_group else None
        description = (
            f"{phrase_group['label']} recurs {phrase_group['occurrence_count']} times, usually in {dominant_section}, "
            f"with {contour} contour and {_phrase_density_label(density_mean)} ({_format_float(density_mean, 1)} notes per bar)."
        )
        descriptions.append(
            {
                "phrase_group_id": group_id,
                "motif_group_id": motif_id,
                "description": description,
            }
        )
    return descriptions


def _build_symbolic_abstraction(
    symbolic_summary: dict,
    density_per_bar: list[dict],
    section_summaries: list[dict],
    phrase_windows: list[dict],
    motif_summary: dict,
) -> dict:
    description = _build_global_description(symbolic_summary, density_per_bar)
    return {
        "description": description,
        "core_terms": {
            "texture": symbolic_summary["texture"],
            "register_label": symbolic_summary["register_label"],
            "melodic_contour": symbolic_summary["melodic_contour"],
            "bass_motion": symbolic_summary["bass_motion"],
            "repetition_level": _repetition_label(float(symbolic_summary["repetition_score"])),
            "sustain_profile": _sustain_label(float(symbolic_summary["sustain_ratio"])),
        },
        "section_descriptions": _build_section_descriptions(section_summaries),
        "phrase_group_descriptions": _build_phrase_group_descriptions(phrase_windows, motif_summary),
    }



__all__ = ['_predict_stem_notes', '_nearest_beat_alignment', '_section_for_time', '_align_note_events', '_validate_transcription_source', '_deduplicate_notes', '_safe_mean', '_notes_in_window', '_section_name', '_find_bar_sections', '_pitch_range_payload', '_register_label', '_contour_label', '_texture_label', '_bass_motion_label', '_compute_density_per_beat', '_compute_density_per_bar', '_section_bar_numbers', '_notes_for_bars', '_section_summary', '_window_signature', '_cosine_similarity', '_shared_pitch_class_count', '_group_code', '_motif_name', '_phrase_windows', '_compute_symbolic_summary', '_global_density_label', '_phrase_density_label', '_repetition_label', '_sustain_label', '_format_float', '_build_global_description', '_build_section_descriptions', '_build_phrase_group_descriptions', '_build_symbolic_abstraction', 'SOURCE_CONFIGS']
