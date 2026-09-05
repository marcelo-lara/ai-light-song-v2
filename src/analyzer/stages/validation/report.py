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
from .drums import validate_drums
from .beats import validate_beats
from .chords import validate_chords
from .utils import ValidationResult, skipped_result
from .sections import _validate_sections
from .drops import validate_drops


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
    event_timeline_path = paths.timeline_output_path
    harmonic = read_json(harmonic_path)
    sections = read_json(sections_path)
    timing = read_json(beats_path)

    results = {
        "beats": beat_validation if "beats" in compare_targets and beat_validation is not None else (
            validate_beats(paths, timing, beat_tolerance_seconds) if "beats" in compare_targets else skipped_result()
        ),
        "chords": chord_validation if "chords" in compare_targets and chord_validation is not None else (
            validate_chords(paths, harmonic, timing, chord_min_overlap) if "chords" in compare_targets else skipped_result()
        ),
        "drums": validate_drums(paths, timing) if "drums" in compare_targets else skipped_result(),
        "sections": _validate_sections(paths, sections, tolerance_seconds) if "sections" in compare_targets else skipped_result(),
        "drops": validate_drops(paths) if "drops" in compare_targets else skipped_result(),
    }

    # drops is an advisory structural score (plan item 0.3): it surfaces in
    # the report but never flips the pipeline exit code, even under
    # --fail-on-mismatch, because its ground truth is an incomplete gold set.
    ADVISORY_TARGETS = {"drops"}
    evaluated_results = [result for result in results.values() if result.status != "skipped"]
    gating_results = [
        result for key, result in results.items()
        if result.status != "skipped" and key not in ADVISORY_TARGETS
    ]
    if fail_on_mismatch and any(result.status == "failed" for result in gating_results):
        exit_code = 1
        status = "failed"
    else:
        exit_code = 0
        status = "passed"

    notes: list[str] = []
    if "beats" in compare_targets:
        notes.append("Beat validation compares inferred beat times against the beat timestamps embedded in the reference chord annotation when present.")
    if "chords" in compare_targets:
        notes.append("reference/moises/*.json is Moises.ai inference, not human ground truth. Only lyrics.json carries a confidence field, and only its \"0.99\" rows are operator-curated. Chord validation therefore measures agreement with a second model, not correctness.")
    if "drums" in compare_targets:
        notes.append("Drum validation checks the producer-scoped drum_events.json artifact for structural integrity, Omnizart provenance, debug-source metadata, and song-level pulse plausibility.")
    if "sections" in compare_targets:
        notes.append("Section validation compares structural change points only; reference segment labels are advisory and do not affect pass/fail.")
    if "drops" in compare_targets:
        notes.append("Drop validation scores detected drops against timed human drop hints in reference/human/human_hints.json; advisory only, and reports 'skipped' when a song has no timed drop hints (plan v3.0 item 10 -- no presence-only fallback).")

    report = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "command": "python -m analyzer",
        "status": status,
        "exit_code": exit_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "song_path": str(paths.song_path),
            "reference_chords": str(paths.reference("moises", "chords.json")),
            "reference_sections": str(paths.reference("moises", "segments.json")),
        },
        "generated_artifacts": {
            "beats_file": str(beats_path),
            "harmonic_layer_file": str(harmonic_path),
            "drum_events_file": str(drum_events_path),
            "drum_midi_file": str(drum_midi_path),
            "energy_layer_file": str(energy_path),
            "event_timeline_file": str(event_timeline_path),
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

