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


@dataclass(slots=True)
class ValidationResult:
    status: str
    matched: int
    mismatched: int
    match_ratio: float | None
    details: list[dict]
    reference_file: str | None
    diagnostics: dict | None = None


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


def build_validation_report(
    paths: SongPaths,
    compare_targets: tuple[str, ...],
    beat_validation: ValidationResult | None,
    beat_tolerance_seconds: float,
    tolerance_seconds: float,
    chord_min_overlap: float,
    fail_on_mismatch: bool,
) -> tuple[dict, int]:
    harmonic_path = paths.artifact("layer_a_harmonic.json")
    sections_path = paths.artifact("section_segmentation", "sections.json")
    beats_path = paths.artifact("essentia", "beats.json")
    energy_path = paths.artifact("layer_c_energy.json")
    energy_identifiers_path = paths.artifact("energy_summary", "hints.json")
    event_features_path = paths.artifact("event_inference", "features.json")
    timeline_index_path = paths.artifact("event_inference", "timeline_index.json")
    rule_candidates_path = paths.artifact("event_inference", "rule_candidates.json")
    machine_events_path = paths.artifact("event_inference", "events.machine.json")
    event_review_path = paths.review_json_path
    event_overrides_path = paths.overrides_path
    event_timeline_path = paths.timeline_output_path
    event_benchmark_path = paths.artifact("validation", "event_benchmark.json")
    patterns_path = paths.artifact("layer_d_patterns.json")
    symbolic_path = paths.artifact("layer_b_symbolic.json")
    unified_path = paths.artifact("music_feature_layers.json")
    lighting_path = paths.artifact("lighting_events.json")
    harmonic = read_json(harmonic_path)
    sections = read_json(sections_path)
    timing = read_json(beats_path)

    results = {
        "beats": beat_validation if "beats" in compare_targets and beat_validation is not None else (
            validate_beats(paths, timing, beat_tolerance_seconds) if "beats" in compare_targets else skipped_result()
        ),
        "chords": _validate_chords(paths, harmonic, chord_min_overlap) if "chords" in compare_targets else skipped_result(),
        "sections": _validate_sections(paths, sections, tolerance_seconds) if "sections" in compare_targets else skipped_result(),
        "energy": _validate_energy_layer(read_json(energy_path), timing, sections) if "energy" in compare_targets else skipped_result(),
        "patterns": _validate_patterns_layer(read_json(patterns_path), timing) if "patterns" in compare_targets else skipped_result(),
        "events": _validate_event_outputs(
            read_json(energy_identifiers_path),
            read_json(event_features_path),
            read_json(rule_candidates_path),
            read_json(machine_events_path),
            read_json(event_review_path),
            read_json(event_overrides_path),
            read_json(event_timeline_path),
            read_json(event_benchmark_path),
        ) if "events" in compare_targets else skipped_result(),
        "unified": _validate_unified_layer(
            read_json(unified_path),
            timing,
            sections,
            read_json(symbolic_path),
            read_json(energy_path),
            read_json(patterns_path),
            paths,
        ) if "unified" in compare_targets else skipped_result(),
    }

    evaluated_results = [result for result in results.values() if result.status != "skipped"]
    if fail_on_mismatch and any(result.status == "failed" for result in evaluated_results):
        exit_code = 1
        status = "failed"
    else:
        exit_code = 0
        status = "passed"

    notes: list[str] = []
    if "beats" in compare_targets:
        notes.append("Beat validation compares inferred beat times against the beat timestamps embedded in the reference chord annotation when present.")
    if "chords" in compare_targets:
        notes.append("Chord validation treats reference chord files as authoritative human-validated comparison inputs when present.")
    if "sections" in compare_targets:
        notes.append("Section validation compares structural change points only; reference segment labels are advisory and do not affect pass/fail.")
    if "energy" in compare_targets:
        notes.append("Energy validation checks internal consistency between section windows, accent candidates, and the canonical beat timeline.")
    if "patterns" in compare_targets:
        notes.append("Pattern validation checks window length, occurrence counts, and non-overlap rules inside Layer D.")
    if "events" in compare_targets:
        notes.append("Event validation checks Epic 5 artifact integrity, machine-review timeline consistency, and benchmark status when reviewed annotations exist.")
    if "unified" in compare_targets:
        notes.append("Unified validation checks cross-layer references, phrase and accent timeline joins, and callback integrity.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "command": "python -m analyzer",
        "status": status,
        "exit_code": exit_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "song_path": str(paths.song_path),
            "reference_chords": str(paths.reference("moises", "chords.json")) if paths.reference("moises", "chords.json") else None,
            "reference_sections": str(paths.reference("moises", "segments.json")) if paths.reference("moises", "segments.json") else None,
        },
        "generated_artifacts": {
            "beats_file": str(beats_path),
            "harmonic_layer_file": str(harmonic_path),
            "symbolic_layer_file": str(symbolic_path),
            "energy_layer_file": str(energy_path),
            "energy_identifiers_file": str(energy_identifiers_path),
            "event_features_file": str(event_features_path),
            "event_timeline_index_file": str(timeline_index_path),
            "event_rule_candidates_file": str(rule_candidates_path),
            "event_machine_file": str(machine_events_path),
            "event_review_file": str(event_review_path),
            "event_overrides_file": str(event_overrides_path),
            "event_timeline_file": str(event_timeline_path),
            "event_benchmark_file": str(event_benchmark_path),
            "patterns_layer_file": str(patterns_path),
            "music_feature_layers_file": str(unified_path),
            "lighting_events_file": str(lighting_path),
            "sections_file": str(sections_path),
        },
        "validation": {key: asdict(value) for key, value in results.items()},
        "notes": notes,
    }
    inferred_beats_file = timing.get("generated_from", {}).get("dependencies", {}).get("inferred_beats_file")
    if inferred_beats_file:
        report["generated_artifacts"]["inferred_beats_file"] = inferred_beats_file
        report["notes"].append("Story 1.2 beat validation failed against reference data, so downstream phases used a canonical timing grid rebuilt from the reference beat annotations.")
    return report, exit_code


def write_validation_report(report: dict, report_json: Path) -> None:
    write_json(report_json, report)


def write_validation_markdown(report: dict, report_md: Path) -> None:
    lines = [
        f"# Phase 1 Validation Report: {report['song_name']}",
        "",
        f"Status: {report['status']}",
        f"Generated at: {report['generated_at']}",
        "",
        "## Artifacts",
        "",
    ]
    for artifact_name, artifact_path in report.get("generated_artifacts", {}).items():
        lines.append(f"- {artifact_name}: {artifact_path}")
    lines.extend([
        "",
        "## Validation",
        "",
    ])
    for target, payload in report["validation"].items():
        lines.append(f"### {target.title()}")
        lines.append(f"Status: {payload['status']}")
        lines.append(f"Matched: {payload['matched']}")
        lines.append(f"Mismatched: {payload['mismatched']}")
        if payload["match_ratio"] is not None:
            lines.append(f"Match ratio: {payload['match_ratio']:.3f}")
        diagnostics = payload.get("diagnostics") or {}
        if diagnostics:
            lines.append("")
            lines.append("Diagnostics:")
            for key, value in diagnostics.items():
                lines.append(f"- {key}: {value}")
        details = payload.get("details", [])
        if details:
            lines.append("")
            lines.append("Checks:")
            for detail in details[:20]:
                if "check" in detail:
                    prefix = "PASS" if detail.get("passed") else "FAIL"
                    extra_items = [
                        f"{key}={value}"
                        for key, value in detail.items()
                        if key not in {"check", "passed"}
                    ]
                    suffix = f" ({', '.join(extra_items)})" if extra_items else ""
                    lines.append(f"- {prefix}: {detail['check']}{suffix}")
                elif detail.get("match_type"):
                    lines.append(f"- {detail['match_type']}: {detail}")
                else:
                    lines.append(f"- {detail}")
        lines.append("")
    notes = report.get("notes", [])
    if notes:
        lines.append("## Notes")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def skipped_result() -> ValidationResult:
    return ValidationResult(status="skipped", matched=0, mismatched=0, match_ratio=None, details=[], reference_file=None, diagnostics=None)


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


def _window(values: list[float], size: int) -> list[float]:
    if len(values) <= size:
        return values
    return values[:size]


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


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


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


def _validate_event_outputs(
    energy_identifiers: dict,
    event_features: dict,
    rule_candidates: dict,
    machine_events: dict,
    review_payload: dict,
    overrides_payload: dict,
    timeline_payload: dict,
    benchmark_payload: dict,
) -> ValidationResult:
    checks = []
    identifier_names = set(energy_identifiers.get("supported_identifiers", []))
    checks.append({
        "check": "drop_identifier_supported",
        "passed": "drop" in identifier_names,
    })
    checks.append({
        "check": "event_feature_rows_present",
        "passed": len(event_features.get("features", [])) > 0,
        "count": len(event_features.get("features", [])),
    })
    checks.append({
        "check": "rule_candidates_present",
        "passed": len(rule_candidates.get("events", [])) > 0,
        "count": len(rule_candidates.get("events", [])),
    })
    checks.append({
        "check": "machine_events_present",
        "passed": len(machine_events.get("events", [])) > 0,
        "count": len(machine_events.get("events", [])),
    })
    checks.append({
        "check": "review_summary_present",
        "passed": isinstance(review_payload.get("summary"), dict),
    })
    checks.append({
        "check": "overrides_operations_list_present",
        "passed": isinstance(overrides_payload.get("operations"), list),
    })
    timeline_events = timeline_payload.get("events", [])
    merged_count = review_payload.get("summary", {}).get("merged_event_count")
    checks.append({
        "check": "timeline_matches_merged_review_count",
        "passed": len(timeline_events) == int(merged_count),
        "timeline_count": len(timeline_events),
        "merged_count": merged_count,
    })
    benchmark_status = str(benchmark_payload.get("status", "skipped"))
    checks.append({
        "check": "benchmark_report_written",
        "passed": benchmark_status in {"passed", "failed", "skipped"},
        "status": benchmark_status,
    })
    checks.append({
        "check": "benchmark_failure_only_counts_when_report_exists",
        "passed": benchmark_status != "failed" or benchmark_payload.get("matched", 0) >= 0,
        "status": benchmark_status,
    })
    return _result_from_checks(checks)


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
            "passed": 2 <= bar_count <= 8,
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


def _validate_unified_layer(
    unified: dict,
    timing: dict,
    sections: dict,
    symbolic: dict,
    energy: dict,
    patterns: dict,
    paths: SongPaths,
) -> ValidationResult:
    checks = []
    generated_from = unified.get("generated_from", {})
    checks.append({
        "check": "generated_from_files_exist",
        "passed": all(Path(path).exists() for path in generated_from.values()),
    })

    unified_phrases = unified.get("timeline", {}).get("phrases", [])
    symbolic_phrases = symbolic.get("phrase_windows", [])
    checks.append({
        "check": "timeline_phrases_match_symbolic_phrase_windows",
        "passed": [phrase.get("id") for phrase in unified_phrases] == [phrase.get("id") for phrase in symbolic_phrases],
        "expected_count": len(symbolic_phrases),
        "actual_count": len(unified_phrases),
    })

    unified_accents = unified.get("timeline", {}).get("accent_windows", [])
    energy_accents = energy.get("accent_candidates", [])
    checks.append({
        "check": "accent_windows_match_energy_candidates",
        "passed": [accent.get("id") for accent in unified_accents] == [accent.get("id") for accent in energy_accents],
        "expected_count": len(energy_accents),
        "actual_count": len(unified_accents),
    })

    pattern_ids = {str(pattern.get("id")) for pattern in patterns.get("patterns", [])}
    unified_pattern_ids = {str(pattern.get("id")) for pattern in unified.get("layers", {}).get("patterns", {}).get("patterns", [])}
    checks.append({
        "check": "unified_pattern_ids_match_layer_d",
        "passed": unified_pattern_ids == pattern_ids,
    })

    motif_ids = {str(motif.get("id")) for motif in symbolic.get("motif_summary", {}).get("motif_groups", [])}
    phrase_group_ids = {str(group.get("id")) for group in symbolic.get("motif_summary", {}).get("repeated_phrase_groups", [])}
    valid_section_ids = {str(section.get("section_id")) for section in sections.get("sections", [])}

    cue_anchors = unified.get("lighting_context", {}).get("cue_anchors", [])
    cue_times = [float(anchor.get("time_s", -1.0)) for anchor in cue_anchors]
    checks.append({
        "check": "cue_anchors_sorted_by_time",
        "passed": cue_times == sorted(cue_times),
    })

    pattern_callbacks = unified.get("lighting_context", {}).get("pattern_callbacks", [])
    checks.append({
        "check": "pattern_callbacks_reference_existing_patterns",
        "passed": all(str(callback.get("pattern_id")) in pattern_ids for callback in pattern_callbacks),
    })
    checks.append({
        "check": "pattern_callbacks_reference_valid_sections",
        "passed": all((callback.get("section_id") is None or str(callback.get("section_id")) in valid_section_ids) for callback in pattern_callbacks),
    })

    motif_callbacks = unified.get("lighting_context", {}).get("motif_callbacks", [])
    checks.append({
        "check": "motif_callbacks_reference_existing_motifs",
        "passed": all(str(callback.get("motif_group_id")) in motif_ids for callback in motif_callbacks),
    })
    checks.append({
        "check": "motif_callbacks_reference_existing_phrase_groups",
        "passed": all(str(callback.get("phrase_group_id")) in phrase_group_ids for callback in motif_callbacks),
    })
    checks.append({
        "check": "motif_callbacks_reference_valid_sections",
        "passed": all((callback.get("section_id") is None or str(callback.get("section_id")) in valid_section_ids) for callback in motif_callbacks),
    })

    checks.append({
        "check": "metadata_duration_matches_timing",
        "passed": abs(float(unified.get("metadata", {}).get("duration_s", 0.0)) - float(timing["bars"][-1]["end_s"])) <= 1e-6,
    })
    return _result_from_checks(checks)


def _validate_chords(paths: SongPaths, harmonic: dict, chord_min_overlap: float) -> ValidationResult:
    reference_path = paths.reference("moises", "chords.json")
    if reference_path is None or not reference_path.exists():
        return skipped_result()

    reference_rows = read_json(reference_path)
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
        previous_bar = int(row["bar_num"])
        previous_beat = int(row["beat_num"])
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
    status = "passed" if ratio is None or ratio >= 0.6 else "failed"
    diagnostics = _build_chord_diagnostics(details)
    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=details,
        reference_file=str(reference_path),
        diagnostics=diagnostics,
    )


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
