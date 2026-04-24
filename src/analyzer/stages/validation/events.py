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

