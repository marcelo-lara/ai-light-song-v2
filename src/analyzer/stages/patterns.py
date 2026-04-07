from __future__ import annotations

from collections import Counter

from analyzer.io import ensure_directory, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


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


def _best_candidate(bars: list[dict], covered: set[int]) -> dict | None:
    search_lengths = [4, 5, 6, 7, 8, 3, 2]
    for window_length in search_lengths:
        best: dict | None = None
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
                    "sequence": _display_window(window_bars),
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
                if window_length == 2 and mismatch_count != 0:
                    continue
                if window_length > 2 and mismatch_count > 3:
                    continue
                occurrences.append(
                    {
                        "bar_index": other_index,
                        "start_bar": int(candidate_bars[0]["bar"]),
                        "end_bar": int(candidate_bars[-1]["bar"]),
                        "start_s": round(float(candidate_bars[0]["start_s"]), 6),
                        "end_s": round(float(candidate_bars[-1]["end_s"]), 6),
                        "mismatch_count": mismatch_count,
                        "sequence": _display_window(candidate_bars),
                    }
                )
                candidate_used_bars.update(candidate_bar_numbers)

            if len(occurrences) < 2:
                continue

            total_mismatch = sum(int(item["mismatch_count"]) for item in occurrences[1:])
            score = (
                len(occurrences) * window_length * 100
                + (250 if window_length == 4 else 0)
                - (total_mismatch * 5)
            )
            candidate = {
                "window_length": window_length,
                "score": score,
                "occurrences": occurrences,
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate

        if best is not None:
            return best
    return None


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
        occurrences = sorted(candidate["occurrences"], key=lambda item: int(item["start_bar"]))
        representative = _representative_window(occurrences, bars, window_length)
        sequence = _display_window(representative)
        pattern_index = len(pattern_rows)
        pattern_id = f"pattern_{chr(ord('A') + pattern_index)}"
        pattern_rows.append(
            {
                "id": pattern_id,
                "label": chr(ord('A') + pattern_index),
                "bar_count": window_length,
                "sequence": sequence,
                "occurrence_count": len(occurrences),
                "occurrences": [
                    {
                        "start_bar": int(occurrence["start_bar"]),
                        "end_bar": int(occurrence["end_bar"]),
                        "start_s": occurrence["start_s"],
                        "end_s": occurrence["end_s"],
                        "mismatch_count": int(occurrence["mismatch_count"]),
                        "sequence": occurrence["sequence"],
                    }
                    for occurrence in occurrences
                ],
            }
        )
        for occurrence in occurrences:
            for bar_index in range(int(occurrence["bar_index"]), int(occurrence["bar_index"]) + window_length):
                covered.add(int(bars[bar_index]["bar"]))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_id": paths.song_id,
        "generated_from": {
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
        },
        "pattern_count": len(pattern_rows),
        "settings": {
            "priority_bars": 4,
            "max_pattern_bars": 8,
            "noise_tolerance_beats": 3,
        },
        "patterns": pattern_rows,
    }

    raw_dir = ensure_directory(paths.artifact("pattern_mining"))
    write_json(raw_dir / "chord_patterns.json", payload)
    write_json(paths.artifact("layer_d_patterns.json"), payload)
    return payload