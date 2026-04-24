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

