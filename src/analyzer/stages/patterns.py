from __future__ import annotations

from collections import Counter

from analyzer.io import ensure_directory, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


MIN_PATTERN_BARS = 2
PRIORITY_PATTERN_BARS = 4
MAX_PATTERN_BARS = 24
NOISE_TOLERANCE_BEATS = 3


def _normalize_chord(label: str | None) -> str | None:
    if label is None:
        return None
    normalized = str(label).strip()
    if not normalized or normalized == "N":
        return None
    normalized = normalized.replace(":maj", "")
    normalized = normalized.replace(":min", "m")
    normalized = normalized.replace("maj7", "maj")
    normalized = normalized.replace("M7", "maj")
    normalized = normalized.replace("min7", "m")
    normalized = normalized.replace("m7", "m")
    normalized = normalized.replace("7", "")
    normalized = normalized.strip()
    return normalized or None


def _chord_for_time(time_s: float, chords: list[dict]) -> str | None:
    for chord in chords:
        if float(chord["time"]) <= time_s < float(chord["end_s"]):
            return _normalize_chord(chord.get("chord"))
    if chords and time_s >= float(chords[-1]["time"]):
        return _normalize_chord(chords[-1].get("chord"))
    return None


def _build_beat_rows(timing: dict, harmonic: dict) -> list[dict]:
    rows: list[dict] = []
    for beat in timing["beats"]:
        rows.append(
            {
                "bar": int(beat["bar"]),
                "beat": int(beat["beat_in_bar"]),
                "time": float(beat["time"]),
                "chord": _chord_for_time(float(beat["time"]), harmonic["chords"]),
            }
        )
    return rows


def _build_bars(beat_rows: list[dict], timing: dict) -> list[dict]:
    rows_by_bar: dict[int, dict[int, dict]] = {}
    for row in beat_rows:
        if not isinstance(row, dict):
            continue
        bar_number = int(row.get("bar", 0))
        beat_number = int(row.get("beat", 0))
        if bar_number < 1 or beat_number not in (1, 2, 3, 4):
            continue
        rows_by_bar.setdefault(bar_number, {})[beat_number] = row

    bar_windows = {int(bar["bar"]): bar for bar in timing["bars"]}
    bars: list[dict] = []
    for bar_number in sorted(rows_by_bar):
        beats = rows_by_bar[bar_number]
        if len(beats) != 4:
            continue
        bar_window = bar_windows.get(bar_number)
        if bar_window is None:
            continue
        beat_sequence = [beats[index]["chord"] for index in (1, 2, 3, 4)]
        bars.append(
            {
                "bar": bar_number,
                "start_s": float(bar_window["start_s"]),
                "end_s": float(bar_window["end_s"]),
                "beats": beat_sequence,
            }
        )
    return bars


def _window_mismatch_count(reference: list[dict], candidate: list[dict]) -> int:
    mismatch_count = 0
    for ref_bar, cand_bar in zip(reference, candidate):
        for ref_chord, cand_chord in zip(ref_bar["beats"], cand_bar["beats"]):
            if ref_chord != cand_chord:
                mismatch_count += 1
    return mismatch_count


def _display_bar(beat_labels: list[str | None]) -> str:
    collapsed: list[str] = []
    previous = object()
    for label in beat_labels:
        display = label if label is not None else "N"
        if display != previous:
            collapsed.append(display)
            previous = display
    return "-".join(collapsed)


def _display_window(window_bars: list[dict]) -> str:
    return "|".join(_display_bar(bar["beats"]) for bar in window_bars)


def _display_bar_sequence(labels: list[str]) -> str:
    return "|".join(labels)


def _display_sequence(labels: list[str]) -> str:
    if not labels:
        return ""

    runs: list[tuple[str, int]] = []
    for label in labels:
        if runs and runs[-1][0] == label:
            previous_label, previous_count = runs[-1]
            runs[-1] = (previous_label, previous_count + 1)
            continue
        runs.append((label, 1))

    parts = [runs[0][0]]
    for index in range(1, len(runs)):
        previous_count = runs[index - 1][1]
        label, count = runs[index]
        delimiter = "→" if previous_count > 1 or count > 1 else "|"
        parts.append(f"{delimiter}{label}")
    return "".join(parts)


def _shortest_repeating_unit(labels: list[str]) -> list[str]:
    if not labels:
        return labels
    for unit_length in range(1, (len(labels) // 2) + 1):
        if len(labels) % unit_length != 0:
            continue
        unit = labels[:unit_length]
        if unit * (len(labels) // unit_length) == labels:
            return unit
    return labels


def _repeating_unit_length(window_bars: list[dict]) -> int:
    bar_labels = [_display_bar(bar["beats"]) for bar in window_bars]
    repeated_unit = _shortest_repeating_unit(bar_labels)
    return len(repeated_unit) if repeated_unit else len(window_bars)


def _pattern_sequence(window_bars: list[dict]) -> str:
    bar_labels = [_display_bar(bar["beats"]) for bar in window_bars]
    repeated_unit = _shortest_repeating_unit(bar_labels)
    return _display_sequence(repeated_unit)


def _reduce_window_to_repeating_unit(window_bars: list[dict]) -> list[dict]:
    unit_length = _repeating_unit_length(window_bars)
    return window_bars[:unit_length]


def _split_occurrences_by_repeating_unit(
    occurrences: list[dict],
    bars: list[dict],
    window_length: int,
    representative_unit: list[dict],
) -> list[dict]:
    unit_length = len(representative_unit)
    if unit_length <= 0 or unit_length >= window_length or window_length % unit_length != 0:
        return [
            {
                "start_bar": int(occurrence["start_bar"]),
                "end_bar": int(occurrence["end_bar"]),
                "start_s": occurrence["start_s"],
                "end_s": occurrence["end_s"],
                "mismatch_count": int(occurrence["mismatch_count"]),
                "sequence": occurrence["sequence"],
                "bar_sequence": occurrence["bar_sequence"],
            }
            for occurrence in occurrences
        ]

    split_rows: list[dict] = []
    for occurrence in occurrences:
        occurrence_start_index = int(occurrence["bar_index"])
        for unit_offset in range(0, window_length, unit_length):
            chunk_start_index = occurrence_start_index + unit_offset
            chunk_bars = bars[chunk_start_index:chunk_start_index + unit_length]
            split_rows.append(
                {
                    "start_bar": int(chunk_bars[0]["bar"]),
                    "end_bar": int(chunk_bars[-1]["bar"]),
                    "start_s": round(float(chunk_bars[0]["start_s"]), 6),
                    "end_s": round(float(chunk_bars[-1]["end_s"]), 6),
                    "mismatch_count": _window_mismatch_count(representative_unit, chunk_bars),
                    "sequence": _pattern_sequence(chunk_bars),
                    "bar_sequence": _display_window(chunk_bars),
                }
            )
    return split_rows


def _representative_window(occurrences: list[dict], bars: list[dict], window_length: int) -> list[dict]:
    sorted_occurrences = sorted(occurrences, key=lambda item: (int(item["mismatch_count"]), int(item["start_bar"])))
    representative: list[dict] = []
    for offset in range(window_length):
        beats: list[str | None] = []
        for beat_index in range(4):
            choices = [
                bars[occurrence["bar_index"] + offset]["beats"][beat_index]
                for occurrence in sorted_occurrences
            ]
            counts = Counter(choices)
            best_count = max(counts.values())
            tied = {label for label, count in counts.items() if count == best_count}
            chosen = next(label for label in choices if label in tied)
            beats.append(chosen)
        source_bar = bars[sorted_occurrences[0]["bar_index"] + offset]
        representative.append(
            {
                "bar": int(source_bar["bar"]),
                "start_s": float(source_bar["start_s"]),
                "end_s": float(source_bar["end_s"]),
                "beats": beats,
            }
        )
    return representative


def _search_lengths(bar_count: int) -> list[int]:
    max_window_length = min(MAX_PATTERN_BARS, bar_count)
    search_lengths: list[int] = []
    if max_window_length >= PRIORITY_PATTERN_BARS:
        search_lengths.append(PRIORITY_PATTERN_BARS)
    for window_length in range(max_window_length, MIN_PATTERN_BARS - 1, -1):
        if window_length != PRIORITY_PATTERN_BARS:
            search_lengths.append(window_length)
    return search_lengths


def _candidate_score(window_length: int, occurrence_count: int, total_mismatch: int) -> int:
    covered_bars = window_length * occurrence_count
    return (
        covered_bars * 1000
        + (window_length * 10)
        + occurrence_count
        + (50 if window_length == PRIORITY_PATTERN_BARS else 0)
        - (total_mismatch * 5)
    )


def _best_candidate(bars: list[dict], covered: set[int]) -> dict | None:
    best: dict | None = None
    search_lengths = _search_lengths(len(bars))
    for window_length in search_lengths:
        for start_index in range(0, len(bars) - window_length + 1):
            window_bars = bars[start_index:start_index + window_length]
            window_bar_numbers = {int(bar["bar"]) for bar in window_bars}
            if window_bar_numbers & covered:
                continue
            candidate_used_bars = set(window_bar_numbers)

            occurrences = [
                {
                    "bar_index": start_index,
                    "start_bar": int(window_bars[0]["bar"]),
                    "end_bar": int(window_bars[-1]["bar"]),
                    "start_s": round(float(window_bars[0]["start_s"]), 6),
                    "end_s": round(float(window_bars[-1]["end_s"]), 6),
                    "mismatch_count": 0,
                    "sequence": _pattern_sequence(window_bars),
                    "bar_sequence": _display_window(window_bars),
                }
            ]

            for other_index in range(start_index + window_length, len(bars) - window_length + 1):
                candidate_bars = bars[other_index:other_index + window_length]
                candidate_bar_numbers = {int(bar["bar"]) for bar in candidate_bars}
                if candidate_bar_numbers & covered:
                    continue
                if candidate_bar_numbers & candidate_used_bars:
                    continue
                mismatch_count = _window_mismatch_count(window_bars, candidate_bars)
                if window_length == MIN_PATTERN_BARS and mismatch_count != 0:
                    continue
                if window_length > MIN_PATTERN_BARS and mismatch_count > NOISE_TOLERANCE_BEATS:
                    continue
                occurrences.append(
                    {
                        "bar_index": other_index,
                        "start_bar": int(candidate_bars[0]["bar"]),
                        "end_bar": int(candidate_bars[-1]["bar"]),
                        "start_s": round(float(candidate_bars[0]["start_s"]), 6),
                        "end_s": round(float(candidate_bars[-1]["end_s"]), 6),
                        "mismatch_count": mismatch_count,
                        "sequence": _pattern_sequence(candidate_bars),
                        "bar_sequence": _display_window(candidate_bars),
                    }
                )
                candidate_used_bars.update(candidate_bar_numbers)

            if len(occurrences) < 2:
                continue

            total_mismatch = sum(int(item["mismatch_count"]) for item in occurrences[1:])
            score = _candidate_score(window_length, len(occurrences), total_mismatch)
            candidate = {
                "window_length": window_length,
                "score": score,
                "occurrences": occurrences,
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
    return best


def extract_chord_patterns(paths: SongPaths, timing: dict, harmonic: dict) -> dict:
    beat_rows = _build_beat_rows(timing, harmonic)
    bars = _build_bars(beat_rows, timing)
    covered: set[int] = set()
    pattern_rows: list[dict] = []

    while True:
        candidate = _best_candidate(bars, covered)
        if candidate is None:
            break
        window_length = int(candidate["window_length"])
        raw_occurrences = sorted(candidate["occurrences"], key=lambda item: int(item["start_bar"]))
        representative = _representative_window(raw_occurrences, bars, window_length)
        representative_unit = _reduce_window_to_repeating_unit(representative)
        occurrences = _split_occurrences_by_repeating_unit(raw_occurrences, bars, window_length, representative_unit)
        sequence = _pattern_sequence(representative_unit)
        bar_sequence = _display_window(representative)
        pattern_index = len(pattern_rows)
        pattern_id = f"pattern_{chr(ord('A') + pattern_index)}"
        pattern_rows.append(
            {
                "id": pattern_id,
                "label": chr(ord('A') + pattern_index),
                "bar_count": len(representative_unit),
                "sequence": sequence,
                "bar_sequence": bar_sequence,
                "occurrence_count": len(occurrences),
                "occurrences": [
                    {
                        "start_bar": int(occurrence["start_bar"]),
                        "end_bar": int(occurrence["end_bar"]),
                        "start_s": occurrence["start_s"],
                        "end_s": occurrence["end_s"],
                        "mismatch_count": int(occurrence["mismatch_count"]),
                        "sequence": occurrence["sequence"],
                        "bar_sequence": occurrence["bar_sequence"],
                    }
                    for occurrence in occurrences
                ],
            }
        )
        for occurrence in raw_occurrences:
            for bar_index in range(int(occurrence["bar_index"]), int(occurrence["bar_index"]) + window_length):
                covered.add(int(bars[bar_index]["bar"]))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
        },
        "pattern_count": len(pattern_rows),
        "settings": {
            "priority_bars": PRIORITY_PATTERN_BARS,
            "max_pattern_bars": MAX_PATTERN_BARS,
            "noise_tolerance_beats": NOISE_TOLERANCE_BEATS,
        },
        "patterns": pattern_rows,
    }

    raw_dir = ensure_directory(paths.artifact("pattern_mining"))
    write_json(raw_dir / "chord_patterns.json", payload)
    write_json(paths.artifact("layer_d_patterns.json"), payload)
    return payload