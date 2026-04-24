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
from .patterns import _validate_patterns_layer
from .drums import validate_drums
from .energy import _validate_energy_layer
from .beats import validate_beats
from .events import _validate_event_outputs
from .unified import _validate_unified_layer
from .chords import validate_chords
from .utils import ValidationResult, skipped_result
from .sections import _validate_sections


def build_validation_report(
    paths: SongPaths,
    compare_targets: tuple[str, ...],
    beat_validation: ValidationResult | None,
    chord_validation: ValidationResult | None,
    beat_tolerance_seconds: float,
    tolerance_seconds: float,
    chord_min_overlap: float,
    fail_on_mismatch: bool,
) -> tuple[dict, int]:
    harmonic_path = paths.artifact("layer_a_harmonic.json")
    sections_path = paths.artifact("section_segmentation", "sections.json")
    beats_path = paths.artifact("essentia", "beats.json")
    drum_events_path = paths.artifact("symbolic_transcription", "drum_events.json")
    drum_midi_path = paths.artifact("symbolic_transcription", "omnizart", "drums.mid")
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
        "chords": chord_validation if "chords" in compare_targets and chord_validation is not None else (
            validate_chords(paths, harmonic, chord_min_overlap) if "chords" in compare_targets else skipped_result()
        ),
        "drums": validate_drums(paths, timing) if "drums" in compare_targets else skipped_result(),
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
    if "drums" in compare_targets:
        notes.append("Drum validation checks the producer-scoped drum_events.json artifact for structural integrity, Omnizart provenance, debug-source metadata, and song-level pulse plausibility.")
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
            "drum_events_file": str(drum_events_path),
            "drum_midi_file": str(drum_midi_path),
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

