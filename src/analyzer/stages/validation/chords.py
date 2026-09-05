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
BEAT_MATCH_RATIO_THRESHOLD = 0.80
CHORD_MATCH_RATIO_THRESHOLD = 0.85
CHORD_MAX_LABEL_MISMATCHES = 0
CHORD_MAX_TIMING_OVERLAP_FAILURES = 2
#: Reference chord rows carry no bar/beat position of their own
#: (`reference/moises/chords.json` is `curr_beat_time`, `curr_beat`,
#: `prev_chord`, `chord_*` -- see docs/issues.md's now-deleted
#: "validate-chords crashes ..." entry). The bar/beat position attached to
#: each reference event is instead read off the nearest beat in the
#: pipeline's own grid (`essentia/beats.json`); this tolerance bounds how far
#: a reference timestamp may sit from that nearest beat before the position
#: is reported as unknown rather than guessed. Matches the alignment
#: tolerance `stages/drums.py::_nearest_beat_alignment` uses for the same
#: kind of nearest-beat snap.
REFERENCE_BAR_POSITION_TOLERANCE_SECONDS = 0.2
from .utils import ValidationResult, skipped_result, _median, _round_or_none, normalize_chord_label


def _build_chord_diagnostics(details: list[dict]) -> dict | None:
    mismatch_reasons: dict[str, int] = {}
    overlap_ratios = [float(detail["overlap_ratio"]) for detail in details if detail.get("overlap_ratio") is not None]
    for detail in details:
        reason = detail.get("result") or "unknown"
        mismatch_reasons[reason] = mismatch_reasons.get(reason, 0) + 1
    diagnostics = {
        "matched_event_count": mismatch_reasons.get("matched", 0),
        "timing_overlap_failure_count": mismatch_reasons.get("timing_overlap_failure", 0),
        "label_mismatch_count": mismatch_reasons.get("label_mismatch", 0),
        "no_reference_overlap_count": mismatch_reasons.get("no_reference_overlap", 0),
        "median_overlap_ratio": _round_or_none(_median(overlap_ratios)),
    }
    return diagnostics


def _reference_grid_position(
    time_s: float,
    grid_beats: list[dict],
    tolerance_seconds: float = REFERENCE_BAR_POSITION_TOLERANCE_SECONDS,
) -> tuple[int | None, int | None]:
    """Bar/beat position of `time_s` on the pipeline's own beat grid.

    `reference/moises/chords.json` carries only `curr_beat_time` -- no bar or
    beat number of its own -- so the position is derived by snapping to the
    nearest beat in `essentia/beats.json` (`bar`, `beat_in_bar`). When the grid
    is empty or the nearest beat is farther than `tolerance_seconds`, the
    position genuinely cannot be computed and both values are `None` rather
    than an invented default (no silent fallbacks).
    """
    if not grid_beats:
        return None, None
    nearest = min(grid_beats, key=lambda beat: abs(float(beat["time"]) - time_s))
    if abs(float(nearest["time"]) - time_s) > tolerance_seconds:
        return None, None
    bar = nearest.get("bar")
    beat_in_bar = nearest.get("beat_in_bar")
    return (int(bar) if bar is not None else None, int(beat_in_bar) if beat_in_bar is not None else None)


def _validate_chords(paths: SongPaths, harmonic: dict, timing: dict, chord_min_overlap: float) -> ValidationResult:
    reference_path = paths.reference("moises", "chords.json")
    if not reference_path.exists():
        return skipped_result()

    reference_rows = read_json(reference_path)
    grid_beats = timing.get("beats", [])
    reference_events = []
    current_label = None
    current_start = None
    previous_time = None
    previous_bar = None
    previous_beat = None
    for row in reference_rows:
        label = normalize_chord_label(row.get("chord_simple_pop") or row.get("chord_basic_pop") or row.get("prev_chord"))
        current_time = float(row["curr_beat_time"])
        if label != current_label:
            if current_label is not None and current_start is not None and previous_time is not None:
                reference_events.append({
                    "time": current_start,
                    "end_s": current_time,
                    "bar": previous_bar,
                    "beat": previous_beat,
                    "chord": current_label,
                })
            current_label = label
            current_start = current_time
        previous_time = current_time
        previous_bar, previous_beat = _reference_grid_position(current_time, grid_beats)
    if current_label is not None and current_start is not None and previous_time is not None:
        reference_events.append({
            "time": current_start,
            "end_s": previous_time,
            "bar": previous_bar,
            "beat": previous_beat,
            "chord": current_label,
        })

    matched = 0
    mismatched = 0
    details = []
    for event in harmonic["chords"]:
        overlap_match = None
        best_overlap = 0.0
        for reference in reference_events:
            overlap = min(float(event["end_s"]), float(reference["end_s"])) - max(float(event["time"]), float(reference["time"]))
            if overlap <= 0:
                continue
            duration = max(float(event["end_s"]) - float(event["time"]), 1e-6)
            ratio = overlap / duration
            if ratio > best_overlap:
                best_overlap = ratio
                overlap_match = reference
        normalized_inferred = normalize_chord_label(event["chord"])
        normalized_reference = normalize_chord_label(overlap_match["chord"]) if overlap_match else None
        if overlap_match is None:
            result = "no_reference_overlap"
            mismatched += 1
        elif best_overlap < chord_min_overlap:
            result = "timing_overlap_failure"
            mismatched += 1
        elif normalized_inferred != normalized_reference:
            result = "label_mismatch"
            mismatched += 1
        else:
            result = "matched"
            matched += 1
        details.append({
            "inferred": event,
            "reference": overlap_match,
            "inferred_label_normalized": normalized_inferred,
            "reference_label_normalized": normalized_reference,
            "overlap_ratio": round(best_overlap, 6),
            "result": result,
        })

    total = matched + mismatched
    ratio = matched / total if total else None
    diagnostics = _build_chord_diagnostics(details)
    label_mismatch_count = int((diagnostics or {}).get("label_mismatch_count", 0))
    timing_overlap_failure_count = int((diagnostics or {}).get("timing_overlap_failure_count", 0))
    status = "passed"
    if ratio is not None and ratio < CHORD_MATCH_RATIO_THRESHOLD:
        status = "failed"
    if label_mismatch_count > CHORD_MAX_LABEL_MISMATCHES:
        status = "failed"
    if timing_overlap_failure_count > CHORD_MAX_TIMING_OVERLAP_FAILURES:
        status = "failed"
    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=details,
        reference_file=str(reference_path),
        diagnostics=diagnostics,
    )


def validate_chords(paths: SongPaths, harmonic: dict, timing: dict, chord_min_overlap: float) -> ValidationResult:
    return _validate_chords(paths, harmonic, timing, chord_min_overlap)

