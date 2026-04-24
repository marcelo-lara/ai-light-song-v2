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
from .utils import ValidationResult, skipped_result, _median, _mean_abs, _round_or_none, _window, _timing_direction, _estimate_reference_beat_interval


def _build_beat_timing_diagnostics(
    details: list[dict],
    tolerance_seconds: float,
    reference_times: list[float],
) -> dict | None:
    deltas = [float(detail["delta_seconds"]) for detail in details if "delta_seconds" in detail]
    if not deltas:
        return None

    if len(deltas) <= 6:
        window_size = max(2, len(deltas) // 2)
    else:
        window_size = max(3, min(16, len(deltas) // 4))
    start_window = _window(deltas, window_size)
    end_window = deltas[-window_size:]
    median_delta = _median(deltas)
    start_median = _median(start_window)
    end_median = _median(end_window)
    reference_beat_interval = _estimate_reference_beat_interval(reference_times)
    residuals = [delta - (median_delta or 0.0) for delta in deltas]
    residual_spread = max(abs(value) for value in residuals) if residuals else None
    drift_span = None if start_median is None or end_median is None else end_median - start_median

    global_offset_present = median_delta is not None and abs(median_delta) > tolerance_seconds
    local_drift_present = drift_span is not None and abs(drift_span) > tolerance_seconds

    diagnostics = {
        "global_offset_seconds": _round_or_none(median_delta),
        "global_offset_direction": _timing_direction(median_delta, tolerance_seconds),
        "global_offset_present": global_offset_present,
        "mean_absolute_delta_seconds": _round_or_none(_mean_abs(deltas)),
        "start_window_median_seconds": _round_or_none(start_median),
        "end_window_median_seconds": _round_or_none(end_median),
        "local_drift_seconds": _round_or_none(drift_span),
        "local_drift_present": local_drift_present,
        "residual_spread_seconds": _round_or_none(residual_spread),
        "reference_beat_interval_seconds": _round_or_none(reference_beat_interval),
    }
    return diagnostics


def _build_section_timing_diagnostics(
    details: list[dict],
    tolerance_seconds: float,
    reference_times: list[float],
) -> dict | None:
    matched_deltas = [
        float(detail["delta_seconds"])
        for detail in details
        if detail.get("match_type") == "matched_boundary" and detail.get("delta_seconds") is not None
    ]
    if not matched_deltas:
        return None

    reference_beat_interval = _estimate_reference_beat_interval(reference_times)
    snapped_boundary_count = 0
    dominant_snap_multiple = None
    if reference_beat_interval and reference_beat_interval > 0:
        snap_multiples = [round(delta / reference_beat_interval) for delta in matched_deltas]
        non_zero_snap_multiples = [multiple for multiple in snap_multiples if multiple != 0]
        for delta in matched_deltas:
            multiple = round(delta / reference_beat_interval)
            snapped_seconds = multiple * reference_beat_interval
            if multiple != 0 and abs(delta - snapped_seconds) <= tolerance_seconds:
                snapped_boundary_count += 1
        if non_zero_snap_multiples:
            dominant_snap_multiple = max(set(non_zero_snap_multiples), key=non_zero_snap_multiples.count)

    median_delta = _median(matched_deltas)
    diagnostics = {
        "boundary_offset_seconds": _round_or_none(median_delta),
        "boundary_offset_direction": _timing_direction(median_delta, 1e-6),
        "reference_beat_interval_seconds": _round_or_none(reference_beat_interval),
        "snap_like_boundary_count": snapped_boundary_count,
        "dominant_snap_multiple_beats": dominant_snap_multiple,
    }
    return diagnostics


def validate_beats(paths: SongPaths, timing: dict, tolerance_seconds: float) -> ValidationResult:
    reference_path = paths.reference("moises", "chords.json")
    if reference_path is None or not reference_path.exists():
        return skipped_result()

    reference_rows = read_json(reference_path)
    reference_times = sorted({round(float(row["curr_beat_time"]), 6) for row in reference_rows if "curr_beat_time" in row})
    inferred_beats = timing.get("beats", [])
    if not inferred_beats or not reference_times:
        return skipped_result()

    reference_start = reference_times[0]
    reference_end = reference_times[-1]
    inferred_beats = [
        beat for beat in inferred_beats
        if reference_start <= float(beat["time"]) <= reference_end
    ]
    if not inferred_beats:
        return skipped_result()

    matched = 0
    mismatched = 0
    details: list[dict] = []
    for beat in inferred_beats:
        inferred_time = float(beat["time"])
        reference_time = min(reference_times, key=lambda item: abs(item - inferred_time))
        delta_seconds = inferred_time - reference_time
        within_tolerance = abs(delta_seconds) <= tolerance_seconds
        if within_tolerance:
            matched += 1
        else:
            mismatched += 1
        details.append({
            "beat_index": int(beat.get("index", 0)),
            "beat_type": beat.get("type", "beat"),
            "inferred_time": round(inferred_time, 6),
            "reference_time": round(reference_time, 6),
            "delta_seconds": round(delta_seconds, 6),
            "within_tolerance": within_tolerance,
        })

    total = matched + mismatched
    ratio = matched / total if total else None
    status = "passed" if ratio is None or ratio >= BEAT_MATCH_RATIO_THRESHOLD else "failed"
    diagnostics = _build_beat_timing_diagnostics(details, tolerance_seconds, reference_times)
    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=details,
        reference_file=str(reference_path),
        diagnostics=diagnostics,
    )


def generate_timing_diagnosis(
    paths: SongPaths,
    inferred_timing: dict,
    reference_timing: dict,
) -> dict:
    """Compare inferred beats against the reference beat grid and write a dedicated diagnosis file.

    Writes global_offset_s (mean signed error), local_drift_s (end-vs-start window drift),
    and snap_multiple_histogram (how often errors cluster at beat-interval multiples).
    """
    inferred_beats = [float(b["time"]) for b in inferred_timing.get("beats", [])]
    reference_beats = [float(b["time"]) for b in reference_timing.get("beats", [])]

    if not inferred_beats or not reference_beats:
        payload: dict = {
            "schema_version": SCHEMA_VERSION,
            "song_name": paths.song_name,
            "status": "skipped",
            "reason": "insufficient beat data for diagnosis",
        }
        write_json(paths.artifact("validation", "timing_diagnosis.json"), payload)
        return payload

    errors: list[float] = []
    for inferred_time in inferred_beats:
        nearest_ref = min(reference_beats, key=lambda t: abs(t - inferred_time))
        errors.append(inferred_time - nearest_ref)

    global_offset_s = sum(errors) / len(errors)
    beat_interval = _estimate_reference_beat_interval(reference_beats)
    window_size = max(4, min(20, len(errors) // 8))
    start_median = _median(errors[:window_size])
    end_median = _median(errors[-window_size:])
    local_drift_s = (end_median - start_median) if (start_median is not None and end_median is not None) else None
    mean_abs_error = sum(abs(e) for e in errors) / len(errors)

    snap_multiple_histogram: dict[str, int] = {}
    if beat_interval and beat_interval > 0:
        for error in errors:
            multiple = round(error / beat_interval * 2) / 2.0
            bucket = str(multiple)
            snap_multiple_histogram[bucket] = snap_multiple_histogram.get(bucket, 0) + 1

    dominant_mode = "well_aligned"
    if beat_interval and beat_interval > 0:
        if mean_abs_error > beat_interval * 0.4:
            dominant_snap = max(snap_multiple_histogram, key=lambda k: snap_multiple_histogram[k]) if snap_multiple_histogram else "0.0"
            dominant_count = snap_multiple_histogram.get(dominant_snap, 0)
            if dominant_snap != "0.0" and dominant_count > len(errors) * 0.4:
                dominant_mode = f"systematic_snap_error_{dominant_snap}_beats"
            elif abs(global_offset_s) > beat_interval * 0.25:
                dominant_mode = "global_offset"
            else:
                dominant_mode = "local_drift"
        elif abs(global_offset_s) > beat_interval * 0.1:
            dominant_mode = "minor_global_offset"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "inferred_beats_file": str(paths.artifact("essentia", "beats_inferred.json")),
            "reference_beats_source": str(paths.reference("moises", "chords.json")) if paths.reference("moises", "chords.json") else None,
        },
        "beat_count": {
            "inferred": len(inferred_beats),
            "reference": len(reference_beats),
        },
        "global_offset_s": _round_or_none(global_offset_s),
        "local_drift_s": _round_or_none(local_drift_s),
        "mean_absolute_error_s": _round_or_none(mean_abs_error),
        "reference_beat_interval_s": _round_or_none(beat_interval),
        "snap_multiple_histogram": snap_multiple_histogram,
        "dominant_failure_mode": dominant_mode,
    }
    write_json(paths.artifact("validation", "timing_diagnosis.json"), payload)
    return payload

