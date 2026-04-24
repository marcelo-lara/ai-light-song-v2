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


@dataclass(slots=True)


class ValidationResult:
    status: str
    matched: int
    mismatched: int
    match_ratio: float | None
    details: list[dict]
    reference_file: str | None
    diagnostics: dict | None = None


@dataclass(slots=True)


class ValidationResult:
    status: str
    matched: int
    mismatched: int
    match_ratio: float | None
    details: list[dict]
    reference_file: str | None
    diagnostics: dict | None = None


def skipped_result() -> ValidationResult:
    return ValidationResult(status="skipped", matched=0, mismatched=0, match_ratio=None, details=[], reference_file=None, diagnostics=None)


def _failed_result(checks: list[dict], reference_file: str | None = None, diagnostics: dict | None = None) -> ValidationResult:
    matched = sum(1 for check in checks if bool(check.get("passed")))
    mismatched = len(checks) - matched
    ratio = matched / len(checks) if checks else None
    return ValidationResult(
        status="failed",
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=checks,
        reference_file=reference_file,
        diagnostics=diagnostics,
    )


def _result_from_checks(checks: list[dict], reference_file: str | None = None) -> ValidationResult:
    matched = sum(1 for check in checks if bool(check.get("passed")))
    mismatched = len(checks) - matched
    ratio = matched / len(checks) if checks else None
    status = "passed" if mismatched == 0 else "failed"
    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=checks,
        reference_file=reference_file,
        diagnostics=None,
    )


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _mean_abs(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(abs(value) for value in values) / len(values)


def _round_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def normalize_chord_label(label: str | None) -> str:
    if not label:
        return "N"
    normalized = label.strip()
    normalized = normalized.replace("Db", "C#")
    normalized = normalized.replace("Eb", "D#")
    normalized = normalized.replace("Gb", "F#")
    normalized = normalized.replace("Ab", "G#")
    normalized = normalized.replace("Bb", "A#")
    normalized = normalized.replace(":maj", "")
    normalized = normalized.replace(":min", "m")
    normalized = normalized.replace("maj7", "")
    normalized = normalized.replace("maj9", "")
    normalized = normalized.replace("add9", "")
    normalized = normalized.replace("sus2", "")
    normalized = normalized.replace("sus4", "")
    normalized = normalized.replace("7", "")
    normalized = normalized.replace("/", "")
    normalized = normalized.strip()
    if normalized.endswith("min"):
        normalized = normalized[:-3] + "m"
    return normalized or "N"


def _window(values: list[float], size: int) -> list[float]:
    if len(values) <= size:
        return values
    return values[:size]


def _timing_direction(delta_seconds: float | None, tolerance_seconds: float) -> str:
    if delta_seconds is None or abs(delta_seconds) <= tolerance_seconds:
        return "aligned"
    if delta_seconds > 0:
        return "late"
    return "early"


def _estimate_reference_beat_interval(reference_times: list[float]) -> float | None:
    if len(reference_times) < 2:
        return None
    intervals = [
        later - earlier
        for earlier, later in zip(reference_times, reference_times[1:])
        if later > earlier
    ]
    return _median(intervals)


def _reference_beat_interval_seconds(timing: dict) -> float | None:
    beat_times = [float(beat["time"]) for beat in timing.get("beats", [])]
    if len(beat_times) < 2:
        return None
    intervals = [later - earlier for earlier, later in zip(beat_times, beat_times[1:]) if later > earlier]
    return _median(intervals)


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None

