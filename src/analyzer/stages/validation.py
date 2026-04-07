from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


@dataclass(slots=True)
class ValidationResult:
    status: str
    matched: int
    mismatched: int
    match_ratio: float | None
    details: list[dict]
    reference_file: str | None


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
    tolerance_seconds: float,
    chord_min_overlap: float,
    fail_on_mismatch: bool,
) -> tuple[dict, int]:
    harmonic_path = paths.artifact("layer_a_harmonic.json")
    sections_path = paths.artifact("section_segmentation", "sections.json")
    harmonic = read_json(harmonic_path)
    sections = read_json(sections_path)

    chord_result = _validate_chords(paths, harmonic, chord_min_overlap) if "chords" in compare_targets else skipped_result()
    section_result = _validate_sections(paths, sections, tolerance_seconds) if "sections" in compare_targets else skipped_result()

    if fail_on_mismatch and any(result.status == "failed" for result in (chord_result, section_result)):
        exit_code = 1
        status = "failed"
    else:
        exit_code = 0
        status = "passed"

    notes: list[str] = []
    if "chords" in compare_targets:
        notes.append("Chord validation treats reference chord files as authoritative human-validated comparison inputs when present.")
    if "sections" in compare_targets:
        notes.append("Section validation compares structural change points only; reference segment labels are advisory and do not affect pass/fail.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "song_id": paths.song_id,
        "command": "python -m analyzer.cli validate-phase-1",
        "status": status,
        "exit_code": exit_code,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "song_path": str(paths.song_path),
            "reference_chords": str(paths.reference("moises", "chords.json")) if paths.reference("moises", "chords.json") else None,
            "reference_sections": str(paths.reference("moises", "segments.json")) if paths.reference("moises", "segments.json") else None,
        },
        "generated_artifacts": {
            "harmonic_layer_file": str(harmonic_path),
            "energy_layer_file": str(paths.artifact("layer_c_energy.json")),
            "sections_file": str(sections_path),
        },
        "validation": {
            "chords": asdict(chord_result),
            "sections": asdict(section_result),
        },
        "notes": notes,
    }
    return report, exit_code


def write_validation_report(report: dict, report_json: Path) -> None:
    write_json(report_json, report)


def write_validation_markdown(report: dict, report_md: Path) -> None:
    lines = [
        f"# Phase 1 Validation Report: {report['song_id']}",
        "",
        f"Status: {report['status']}",
        f"Generated at: {report['generated_at']}",
        "",
        "## Validation",
        "",
    ]
    for target, payload in report["validation"].items():
        lines.append(f"### {target.title()}")
        lines.append(f"Status: {payload['status']}")
        lines.append(f"Matched: {payload['matched']}")
        lines.append(f"Mismatched: {payload['mismatched']}")
        if payload["match_ratio"] is not None:
            lines.append(f"Match ratio: {payload['match_ratio']:.3f}")
        lines.append("")
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def skipped_result() -> ValidationResult:
    return ValidationResult(status="skipped", matched=0, mismatched=0, match_ratio=None, details=[], reference_file=None)


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
        if overlap_match and best_overlap >= chord_min_overlap and normalize_chord_label(event["chord"]) == normalize_chord_label(overlap_match["chord"]):
            matched += 1
        else:
            mismatched += 1
        details.append({
            "inferred": event,
            "reference": overlap_match,
            "overlap_ratio": round(best_overlap, 6),
        })

    total = matched + mismatched
    ratio = matched / total if total else None
    status = "passed" if ratio is None or ratio >= 0.6 else "failed"
    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=details,
        reference_file=str(reference_path),
    )


def _validate_sections(paths: SongPaths, sections: dict, tolerance_seconds: float) -> ValidationResult:
    reference_path = paths.reference("moises", "segments.json")
    if reference_path is None or not reference_path.exists():
        return skipped_result()

    reference_rows = read_json(reference_path)
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
    return ValidationResult(
        status=status,
        matched=matched,
        mismatched=mismatched,
        match_ratio=ratio,
        details=details,
        reference_file=str(reference_path),
    )
