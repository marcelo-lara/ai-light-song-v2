from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from analyzer.io import read_json
from analyzer.paths import SongPaths
BEAT_MATCH_RATIO_THRESHOLD = 0.80
CHORD_MATCH_RATIO_THRESHOLD = 0.85
CHORD_MAX_LABEL_MISMATCHES = 0
CHORD_MAX_TIMING_OVERLAP_FAILURES = 2

#: The plan v3.0 item 8 acceptance metric is stated at this tolerance
#: specifically (independent of `--beat-tolerance-seconds`, which defaults to
#: 100 ms and scores beat *times*, not the downbeat *phase*).
DOWNBEAT_F1_TOLERANCE_SECONDS = 0.07

from .utils import ValidationResult, skipped_result, _median, _mean_abs, _round_or_none, _window, _timing_direction, _estimate_reference_beat_interval


def _score_downbeats(predicted_times: list[float], reference_times: list[float], tolerance_seconds: float) -> dict:
    """Precision/recall/F1 of predicted downbeat times against a reference set,
    at `tolerance_seconds`, via greedy nearest-neighbour one-to-one matching
    (each reference downbeat claims at most one predicted downbeat, and vice
    versa). This is the item 8 acceptance metric: downbeat F1 @±70 ms against
    `reference/moises/beats.json`, required to reach 0.50 against the shipped
    modulo assignment's measured 0.16.

    `predicted_times` is expected to already exclude `confidence: null`
    downbeats (the caller filters them out) — an abstention is not a
    prediction, so it is neither a potential true/false positive here, only a
    potential false negative via the reference side it fails to cover. See the
    filtering comment at this function's call site in `validate_beats`.
    """
    predicted_sorted = sorted(predicted_times)
    reference_sorted = sorted(reference_times)
    used_predicted: set[int] = set()
    true_positives = 0
    for reference_time in reference_sorted:
        best_index = None
        best_delta = tolerance_seconds
        for index, predicted_time in enumerate(predicted_sorted):
            if index in used_predicted:
                continue
            delta = abs(predicted_time - reference_time)
            if delta <= best_delta:
                best_delta = delta
                best_index = index
        if best_index is not None:
            used_predicted.add(best_index)
            true_positives += 1

    precision = true_positives / len(predicted_sorted) if predicted_sorted else None
    recall = true_positives / len(reference_sorted) if reference_sorted else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    return {
        "downbeat_true_positives": true_positives,
        "downbeat_predicted_count": len(predicted_sorted),
        "downbeat_reference_count": len(reference_sorted),
        "downbeat_precision": _round_or_none(precision),
        "downbeat_recall": _round_or_none(recall),
        "downbeat_f1": _round_or_none(f1),
        "downbeat_tolerance_seconds": tolerance_seconds,
    }


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
    if not reference_path.exists():
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

    # Downbeat *phase* F1 (plan v3.0 item 8) — a separate reference file from
    # the beat-time comparison above: `reference/moises/beats.json` carries an
    # explicit `beatNum` (1 == downbeat) that `reference/moises/chords.json`
    # does not.
    downbeat_reference_path = paths.reference("moises", "beats.json")
    if downbeat_reference_path.exists():
        moises_beat_rows = read_json(downbeat_reference_path)
        reference_downbeats = [
            float(row["time"]) for row in moises_beat_rows if int(row.get("beatNum", 0)) == 1
        ]
        # A `confidence: null` downbeat is an honest abstention (constitution
        # §7 — "say so rather than snapping"), not a confident claim. Scoring
        # it as a prediction would charge the honesty mechanism itself: a
        # correct-but-unmarked-unknown guess would inflate precision, and a
        # wrong one would deflate it, for a row that never claimed to be
        # right. Only confidence-bearing downbeats are scored as predictions;
        # an abstained-on reference downbeat still counts against recall
        # (nothing was claimed there), which is the honest outcome.
        predicted_downbeats = [
            float(beat["time"])
            for beat in timing.get("beats", [])
            if str(beat.get("type")) == "downbeat"
            and beat.get("confidence") is not None
            and reference_start <= float(beat["time"]) <= reference_end
        ]
        if reference_downbeats and predicted_downbeats:
            diagnostics = dict(diagnostics or {})
            diagnostics["downbeat_f1_diagnostics"] = _score_downbeats(
                predicted_downbeats, reference_downbeats, DOWNBEAT_F1_TOLERANCE_SECONDS
            )

    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=details,
        reference_file=str(reference_path),
        diagnostics=diagnostics,
    )



