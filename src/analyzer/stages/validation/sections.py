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
from .beats import _build_section_timing_diagnostics
from .utils import ValidationResult, skipped_result


def _validate_sections(paths: SongPaths, sections: dict, tolerance_seconds: float) -> ValidationResult:
    reference_path = paths.reference("moises", "segments.json")
    if reference_path is None or not reference_path.exists():
        return skipped_result()

    reference_rows = read_json(reference_path)
    reference_chords_path = paths.reference("moises", "chords.json")
    reference_chord_rows = read_json(reference_chords_path) if reference_chords_path and reference_chords_path.exists() else []
    reference_times = sorted({round(float(row["curr_beat_time"]), 6) for row in reference_chord_rows if "curr_beat_time" in row})
    inferred_sections = sections.get("sections", [])
    inferred_boundaries = [
        {
            "time": float(section["start"]),
            "section_id": section.get("section_id"),
            "label": section.get("label"),
        }
        for section in inferred_sections[1:]
    ]
    reference_boundaries = [
        {
            "time": float(reference["start"]),
            "label": reference.get("label"),
        }
        for reference in reference_rows[1:]
    ]

    matched = 0
    details: list[dict] = []
    inferred_index = 0
    reference_index = 0
    while inferred_index < len(inferred_boundaries) and reference_index < len(reference_boundaries):
        inferred_boundary = inferred_boundaries[inferred_index]
        reference_boundary = reference_boundaries[reference_index]
        delta_seconds = float(inferred_boundary["time"] - reference_boundary["time"])
        if abs(delta_seconds) <= tolerance_seconds:
            matched += 1
            details.append(
                {
                    "match_type": "matched_boundary",
                    "inferred": inferred_boundary,
                    "reference": reference_boundary,
                    "delta_seconds": round(delta_seconds, 6),
                    "within_tolerance": True,
                }
            )
            inferred_index += 1
            reference_index += 1
            continue
        if inferred_boundary["time"] < reference_boundary["time"]:
            details.append(
                {
                    "match_type": "extra_inferred_boundary",
                    "inferred": inferred_boundary,
                    "reference": None,
                    "delta_seconds": None,
                    "within_tolerance": False,
                }
            )
            inferred_index += 1
            continue
        details.append(
            {
                "match_type": "missed_reference_boundary",
                "inferred": None,
                "reference": reference_boundary,
                "delta_seconds": None,
                "within_tolerance": False,
            }
        )
        reference_index += 1

    for inferred_boundary in inferred_boundaries[inferred_index:]:
        details.append(
            {
                "match_type": "extra_inferred_boundary",
                "inferred": inferred_boundary,
                "reference": None,
                "delta_seconds": None,
                "within_tolerance": False,
            }
        )
    for reference_boundary in reference_boundaries[reference_index:]:
        details.append(
            {
                "match_type": "missed_reference_boundary",
                "inferred": None,
                "reference": reference_boundary,
                "delta_seconds": None,
                "within_tolerance": False,
            }
        )

    mismatched = len(details) - matched
    denominator = max(len(inferred_boundaries), len(reference_boundaries))
    ratio = matched / denominator if denominator else None
    status = "passed" if ratio is None or ratio >= 0.75 else "failed"
    diagnostics = _build_section_timing_diagnostics(details, tolerance_seconds, reference_times)
    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=details,
        reference_file=str(reference_path),
        diagnostics=diagnostics,
    )

