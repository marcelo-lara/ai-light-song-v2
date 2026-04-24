import numpy as np
from typing import Any

ROLLING_WINDOWS = {
    "local": 1,
    "phrasal": 16,
    "structural": 128,
}


def _attenuated_series(values: list[float], decay: float = 0.85) -> list[float]:
    if not values:
        return []
    attenuated: list[float] = []
    previous = 0.0
    for value in values:
        current = max(float(value), previous * decay)
        attenuated.append(current)
        previous = current
    return attenuated

def _window_end_s(timing: dict, beat_index: int) -> float:
    beats = timing.get("beats", [])
    bars = timing.get("bars", [])
    if beat_index + 1 < len(beats):
        return float(beats[beat_index + 1]["time"])
    if bars:
        return float(bars[-1]["end_s"])
    return float(beats[beat_index]["time"])

def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None

def _phrase_for_time(time_s: float, phrases: list[dict]) -> dict | None:
    for phrase in phrases:
        if float(phrase["start_s"]) <= time_s < float(phrase["end_s"]):
            return phrase
    if phrases and time_s >= float(phrases[-1]["start_s"]):
        return phrases[-1]
    return None

def _chord_for_time(time_s: float, chords: list[dict]) -> dict | None:
    for chord in chords:
        if float(chord["time"]) <= time_s < float(chord["end_s"]):
            return chord
    if chords and time_s >= float(chords[-1]["time"]):
        return chords[-1]
    return None

def _overlap(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))

def _window_note_overlap_score(notes: list[dict], start_s: float, end_s: float) -> float:
    duration = max(end_s - start_s, 1e-6)
    overlap_sum = 0.0
    for note in notes:
        overlap_sum += _overlap(start_s, end_s, float(note["time"]), float(note["end_s"]))
    return min(overlap_sum / duration, 1.0)

def _calculate_song_statistics(raw_rows: list[dict], numeric_keys: list[str]) -> dict[str, dict]:
    statistics = {}
    for key in numeric_keys:
        values = np.array([float(row[key]) for row in raw_rows])
        mean = float(np.mean(values))
        std = float(np.std(values))
        statistics[key] = {
            "mean": round(mean, 6),
            "std_dev": round(std, 6),
            "min": round(float(np.min(values)), 6),
            "max": round(float(np.max(values)), 6),
        }
    return statistics

def _apply_zscore(value: float, mean: float, std_dev: float) -> float:
    if std_dev < 1e-9:
        return 0.0
    return round((value - mean) / std_dev, 6)

def _accent_lookup(accent_candidates: list[dict], start_s: float, end_s: float) -> tuple[str | None, float]:
    for accent in accent_candidates:
        accent_time = float(accent["time"])
        if start_s <= accent_time < end_s:
            return str(accent["id"]), float(accent.get("intensity", 0.0))
    return None, 0.0

def _rolling_mean(rows: list[dict[str, Any]], end_index: int, dotted_key: str, window_size: int) -> float:
    start_index = max(0, end_index - window_size + 1)
    window = rows[start_index : end_index + 1]
    if not window:
        return 0.0
    key_parts = dotted_key.split(".")
    total = 0.0
    for row in window:
        value: Any = row
        for key in key_parts:
            value = value[key]
        total += float(value)
    return total / len(window)


def _rolling_peak(rows: list[dict[str, Any]], end_index: int, dotted_key: str, window_size: int) -> float:
    start_index = max(0, end_index - window_size + 1)
    window = rows[start_index : end_index + 1]
    if not window:
        return 0.0
    key_parts = dotted_key.split(".")
    peak = None
    for row in window:
        value: Any = row
        for key in key_parts:
            value = value[key]
        numeric = float(value)
        peak = numeric if peak is None else max(peak, numeric)
    return 0.0 if peak is None else peak
