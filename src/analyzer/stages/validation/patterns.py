from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from analyzer.exceptions import AnalysisError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths
from analyzer.stages.patterns import MAX_PATTERN_BARS, _build_bars, _build_beat_rows, _display_window, _pattern_sequence
BEAT_MATCH_RATIO_THRESHOLD = 0.80
CHORD_MATCH_RATIO_THRESHOLD = 0.85
CHORD_MAX_LABEL_MISMATCHES = 0
CHORD_MAX_TIMING_OVERLAP_FAILURES = 2
from .utils import ValidationResult, _result_from_checks


def _validate_bar_beat_window(
    *,
    start_bar: int,
    start_beat: int,
    end_bar: int,
    end_beat: int,
) -> None:
    if start_beat not in {1, 2, 3, 4} or end_beat not in {1, 2, 3, 4}:
        raise AnalysisError("Bar-window beats must be between 1 and 4")
    if start_bar < 1 or end_bar < 1:
        raise AnalysisError("Bar-window bars must be >= 1")
    if (end_bar, end_beat) < (start_bar, start_beat):
        raise AnalysisError("Bar-window end must not precede the start")


def _flatten_window_beats(
    bars_by_number: dict[int, dict],
    *,
    start_bar: int,
    start_beat: int,
    end_bar: int,
    end_beat: int,
) -> list[str | None]:
    labels: list[str | None] = []
    for bar_number in range(start_bar, end_bar + 1):
        bar = bars_by_number.get(bar_number)
        if bar is None:
            raise AnalysisError(f"Bar {bar_number} is missing from the canonical timing grid")
        beat_start = start_beat if bar_number == start_bar else 1
        beat_end = end_beat if bar_number == end_bar else 4
        labels.extend(bar["beats"][beat_start - 1:beat_end])
    return labels


def _window_display_rows(
    bars_by_number: dict[int, dict],
    *,
    start_bar: int,
    end_bar: int,
) -> list[dict]:
    return [bars_by_number[bar_number] for bar_number in range(start_bar, end_bar + 1)]


def find_pattern_matches_for_bar_window(
    patterns: dict,
    timing: dict,
    harmonic: dict,
    *,
    start_bar: int,
    start_beat: int = 1,
    end_bar: int,
    end_beat: int = 4,
) -> list[dict]:
    _validate_bar_beat_window(
        start_bar=start_bar,
        start_beat=start_beat,
        end_bar=end_bar,
        end_beat=end_beat,
    )

    bars = _build_bars(_build_beat_rows(timing, harmonic), timing)
    bars_by_number = {int(bar["bar"]): bar for bar in bars}
    window_beats = _flatten_window_beats(
        bars_by_number,
        start_bar=start_bar,
        start_beat=start_beat,
        end_bar=end_bar,
        end_beat=end_beat,
    )
    full_bar_window = start_beat == 1 and end_beat == 4
    window_rows = _window_display_rows(bars_by_number, start_bar=start_bar, end_bar=end_bar) if full_bar_window else []

    matches: list[dict] = []
    for pattern in patterns.get("patterns", []):
        for occurrence in pattern.get("occurrences", []):
            occurrence_start_bar = int(occurrence.get("start_bar", 0))
            occurrence_end_bar = int(occurrence.get("end_bar", 0))
            if not (occurrence_start_bar <= start_bar <= end_bar <= occurrence_end_bar):
                continue

            occurrence_beats = _flatten_window_beats(
                bars_by_number,
                start_bar=occurrence_start_bar,
                start_beat=1,
                end_bar=occurrence_end_bar,
                end_beat=4,
            )
            offset = ((start_bar - occurrence_start_bar) * 4) + (start_beat - 1)
            window_length = ((end_bar - start_bar) * 4) + (end_beat - start_beat + 1)
            candidate_beats = occurrence_beats[offset:offset + window_length]
            if candidate_beats != window_beats:
                continue

            match_row = {
                "pattern_id": pattern.get("id"),
                "pattern_label": pattern.get("label"),
                "pattern_sequence": pattern.get("sequence"),
                "occurrence_start_bar": occurrence_start_bar,
                "occurrence_end_bar": occurrence_end_bar,
                "window_start_bar": start_bar,
                "window_start_beat": start_beat,
                "window_end_bar": end_bar,
                "window_end_beat": end_beat,
                "contained": True,
                "mismatch_count": occurrence.get("mismatch_count"),
            }
            if full_bar_window:
                match_row["window_sequence"] = _pattern_sequence(window_rows)
                match_row["window_bar_sequence"] = _display_window(window_rows)
            matches.append(match_row)
    return matches


def _validate_patterns_layer(patterns: dict, timing: dict) -> ValidationResult:
    max_bar = int(timing["bars"][-1]["bar"]) if timing.get("bars") else 0
    checks = []
    pattern_rows = patterns.get("patterns", [])
    checks.append({
        "check": "pattern_count_matches_rows",
        "passed": int(patterns.get("pattern_count", 0)) == len(pattern_rows),
        "expected": len(pattern_rows),
        "actual": int(patterns.get("pattern_count", 0)),
    })
    checks.append({
        "check": "pattern_ids_unique",
        "passed": len({str(pattern.get("id")) for pattern in pattern_rows}) == len(pattern_rows),
    })
    for pattern in pattern_rows:
        occurrences = pattern.get("occurrences", [])
        pattern_id = str(pattern.get("id"))
        bar_count = int(pattern.get("bar_count", 0))
        checks.append({
            "check": f"{pattern_id}_bar_count_range",
            "passed": 2 <= bar_count <= MAX_PATTERN_BARS,
            "bar_count": bar_count,
        })
        checks.append({
            "check": f"{pattern_id}_occurrence_count_matches_rows",
            "passed": int(pattern.get("occurrence_count", 0)) == len(occurrences),
            "expected": len(occurrences),
            "actual": int(pattern.get("occurrence_count", 0)),
        })
        non_overlap_passed = True
        occurrence_shape_passed = True
        previous_end_bar = 0
        for occurrence in sorted(occurrences, key=lambda item: int(item["start_bar"])):
            start_bar = int(occurrence["start_bar"])
            end_bar = int(occurrence["end_bar"])
            if end_bar - start_bar + 1 != bar_count:
                occurrence_shape_passed = False
            if not (1 <= start_bar <= end_bar <= max_bar):
                occurrence_shape_passed = False
            if start_bar <= previous_end_bar:
                non_overlap_passed = False
            previous_end_bar = end_bar
        checks.append({
            "check": f"{pattern_id}_occurrence_lengths_match_bar_count",
            "passed": occurrence_shape_passed,
        })
        checks.append({
            "check": f"{pattern_id}_occurrences_non_overlapping",
            "passed": non_overlap_passed,
        })
    return _result_from_checks(checks)

