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
from .utils import ValidationResult, _failed_result, _median, _round_or_none, _reference_beat_interval_seconds


def _validate_drums_summary(summary: dict, events: list[dict]) -> bool:
    event_types = [str(event.get("event_type")) for event in events]
    return summary == {
        "event_count": len(events),
        "kick_count": event_types.count("kick"),
        "snare_count": event_types.count("snare"),
        "hat_count": event_types.count("hat"),
        "unresolved_count": event_types.count("unresolved"),
    }


def _drum_diagnostics(events: list[dict], timing: dict) -> dict:
    event_types = [str(event.get("event_type")) for event in events]
    beat_interval = _reference_beat_interval_seconds(timing)
    hat_times = [float(event["time"]) for event in events if event.get("event_type") == "hat"]
    hat_intervals = [later - earlier for earlier, later in zip(hat_times, hat_times[1:]) if later > earlier]
    median_hat_interval = _median(hat_intervals)
    aligned_event_ratio = sum(1 for event in events if event.get("alignment_resolved")) / len(events) if events else 0.0

    backbeat_snares = sum(
        1
        for event in events
        if event.get("event_type") == "snare" and event.get("aligned_beat") in {2, 4}
    )
    downbeat_kicks = sum(
        1
        for event in events
        if event.get("event_type") == "kick" and event.get("aligned_beat") in {1, 3}
    )
    recognizable_backbeat = backbeat_snares >= 2 and downbeat_kicks >= 2
    recognizable_hat_pulse = (
        beat_interval is not None
        and median_hat_interval is not None
        and len(hat_times) >= 2
        and (beat_interval * 0.2) <= median_hat_interval <= (beat_interval * 0.75)
    )
    overdense_hat_regions = 0
    if beat_interval is not None:
        overdense_hat_regions = sum(1 for interval in hat_intervals if interval < (beat_interval / 6.0))

    return {
        "event_count": len(events),
        "kick_count": event_types.count("kick"),
        "snare_count": event_types.count("snare"),
        "hat_count": event_types.count("hat"),
        "unresolved_count": event_types.count("unresolved"),
        "aligned_event_ratio": _round_or_none(aligned_event_ratio),
        "reference_beat_interval_seconds": _round_or_none(beat_interval),
        "median_hat_interval_seconds": _round_or_none(median_hat_interval),
        "recognizable_backbeat": recognizable_backbeat,
        "recognizable_hat_pulse": recognizable_hat_pulse,
        "overdense_hat_regions": overdense_hat_regions,
    }


def validate_drums(paths: SongPaths, timing: dict) -> ValidationResult:
    drum_events_path = paths.artifact("symbolic_transcription", "drum_events.json")
    drum_midi_path = paths.artifact("symbolic_transcription", "omnizart", "drums.mid")
    if not drum_events_path.exists():
        return _failed_result(
            [{"check": "drum_events_present", "passed": False, "path": str(drum_events_path)}],
            reference_file=str(drum_events_path),
        )

    payload = read_json(drum_events_path)
    events = payload.get("events", [])
    summary = payload.get("summary", {})
    debug_sources = payload.get("generated_from", {}).get("debug_sources", {})
    dependencies = payload.get("generated_from", {}).get("dependencies", {})
    checks = [
        {
            "check": "drum_events_present",
            "passed": len(events) > 0,
            "count": len(events),
        },
        {
            "check": "event_ids_unique",
            "passed": len({str(event.get("event_id")) for event in events}) == len(events),
        },
        {
            "check": "event_times_sorted",
            "passed": [float(event.get("time", -1.0)) for event in events] == sorted(float(event.get("time", -1.0)) for event in events),
        },
        {
            "check": "event_types_supported",
            "passed": all(str(event.get("event_type")) in {"kick", "snare", "hat", "unresolved"} for event in events),
        },
        {
            "check": "summary_counts_match_event_rows",
            "passed": _validate_drums_summary(summary, events),
        },
        {
            "check": "resolved_events_have_alignment_fields",
            "passed": all(
                (not event.get("alignment_resolved"))
                or (event.get("aligned_bar") is not None and event.get("aligned_beat") is not None and event.get("aligned_beat_global") is not None)
                for event in events
            ),
        },
        {
            "check": "raw_midi_cache_present",
            "passed": drum_midi_path.exists() and dependencies.get("raw_midi_cache") == str(drum_midi_path),
        },
        {
            "check": "generated_engine_is_omnizart",
            "passed": payload.get("generated_from", {}).get("engine") == "audiohacking.omnizart.drum",
        },
        {
            "check": "debug_source_paths_present",
            "passed": bool(debug_sources.get("full_mix")) and bool(debug_sources.get("drums_stem")),
        },
    ]
    diagnostics = _drum_diagnostics(events, timing)
    return ValidationResult(
        status="passed" if all(bool(check.get("passed")) for check in checks) else "failed",
        matched=sum(1 for check in checks if bool(check.get("passed"))),
        mismatched=sum(1 for check in checks if not bool(check.get("passed"))),
        match_ratio=(sum(1 for check in checks if bool(check.get("passed"))) / len(checks)) if checks else None,
        details=checks,
        reference_file=str(drum_events_path),
        diagnostics=diagnostics,
    )

