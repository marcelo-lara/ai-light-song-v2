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
from .utils import ValidationResult, _result_from_checks, _section_for_time


def _validate_energy_layer(energy: dict, timing: dict, sections: dict) -> ValidationResult:
    section_rows = sections.get("sections", [])
    beat_count = len(timing.get("beats", []))
    max_time = float(timing["bars"][-1]["end_s"]) if timing.get("bars") else 0.0
    checks = []

    checks.append({
        "check": "global_energy_fields_present",
        "passed": all(key in energy.get("global_energy", {}) for key in ("mean", "peak", "dynamic_range", "transient_density", "energy_trend")),
    })
    checks.append({
        "check": "section_energy_count_matches_sections",
        "passed": len(energy.get("section_energy", [])) == len(section_rows),
        "expected": len(section_rows),
        "actual": len(energy.get("section_energy", [])),
    })
    checks.append({
        "check": "beat_energy_count_matches_timing",
        "passed": len(energy.get("beat_energy", [])) == beat_count,
        "expected": beat_count,
        "actual": len(energy.get("beat_energy", [])),
    })

    accent_rows = energy.get("accent_candidates", [])
    accent_ids: set[str] = set()
    accent_sorted = True
    previous_time = -1.0
    accent_integrity_passed = True
    for accent in accent_rows:
        accent_time = float(accent.get("time", -1.0))
        accent_id = str(accent.get("id"))
        accent_ids.add(accent_id)
        if accent_time < previous_time:
            accent_sorted = False
        previous_time = accent_time
        section = _section_for_time(accent_time, section_rows)
        if not (0.0 <= accent_time <= max_time):
            accent_integrity_passed = False
        if section is not None and accent.get("section_id") != section.get("section_id"):
            accent_integrity_passed = False
    checks.append({
        "check": "accent_candidate_ids_unique",
        "passed": len(accent_ids) == len(accent_rows),
        "expected": len(accent_rows),
        "actual": len(accent_ids),
    })
    checks.append({
        "check": "accent_candidates_sorted_by_time",
        "passed": accent_sorted,
    })
    checks.append({
        "check": "accent_candidates_reference_valid_time_and_section",
        "passed": accent_integrity_passed,
    })
    return _result_from_checks(checks)

