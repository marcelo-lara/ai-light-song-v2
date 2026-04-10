from __future__ import annotations

from pathlib import Path

from analyzer.io import ensure_directory, read_json, write_json
from analyzer.models import SCHEMA_VERSION, build_song_schema_fields, round_schema_float
from analyzer.paths import SongPaths


def _density_label(density_mean: float | None) -> str:
    if density_mean is None:
        return "unknown activity"
    if density_mean >= 18.0:
        return "very dense activity"
    if density_mean >= 12.0:
        return "dense activity"
    if density_mean >= 7.0:
        return "moderate activity"
    if density_mean >= 3.0:
        return "light activity"
    return "sparse activity"


def _sustain_label(ratio: float | None) -> str:
    if ratio is None:
        return "unknown sustain"
    if ratio >= 0.15:
        return "long-held notes"
    if ratio >= 0.08:
        return "mixed sustain"
    if ratio >= 0.04:
        return "mostly short notes"
    return "clipped note lengths"


def _repetition_label(score: float | None) -> str:
    if score is None:
        return "unknown repetition"
    if score >= 0.75:
        return "strong repetition"
    if score >= 0.4:
        return "moderate repetition"
    if score >= 0.15:
        return "occasional repetition"
    return "limited repetition"


def _section_label(section: dict) -> str:
    label = section.get("section_character") or section.get("label") or section.get("section_id")
    return str(label)


def _hint_id(section_id: str, category: str) -> str:
    return f"{section_id}-inference-{category}"


def _build_inference_hint(
    section_id: str,
    category: str,
    text: str,
    *,
    phrase_window_ids: list[str] | None = None,
    phrase_group_ids: list[str] | None = None,
    motif_group_ids: list[str] | None = None,
) -> dict:
    return {
        "id": _hint_id(section_id, category),
        "source": "inference",
        "category": category,
        "text": text,
        "anchor_refs": {
            "phrase_window_ids": phrase_window_ids or [],
            "phrase_group_ids": phrase_group_ids or [],
            "motif_group_ids": motif_group_ids or [],
        },
    }


def _section_inference_hints(
    section: dict,
    summary: dict | None,
    phrase_windows: list[dict],
    repeated_groups: list[dict],
    phrase_group_to_motif: dict[str, str],
) -> list[dict]:
    section_id = str(section["section_id"])
    section_name = _section_label(section)
    section_phrase_ids = [str(window["id"]) for window in phrase_windows[:4]]
    section_phrase_group_ids = list(dict.fromkeys(str(window["phrase_group_id"]) for window in phrase_windows))

    hints: list[dict] = []
    if summary is not None:
        hints.append(
            _build_inference_hint(
                section_id,
                "section_shape",
                (
                    f"{section_name.replace('_', ' ')} reads as a {summary['texture']} section with "
                    f"{summary['melodic_contour']} contour, {_density_label(summary.get('density_mean'))}, "
                    f"and {_sustain_label(summary.get('sustain_ratio'))}."
                ),
                phrase_window_ids=section_phrase_ids,
                phrase_group_ids=section_phrase_group_ids,
            )
        )

    if section_phrase_ids:
        phrase_label = ", ".join(section_phrase_ids)
        hints.append(
            _build_inference_hint(
                section_id,
                "phrase_boundaries",
                f"Treat phrase anchors {phrase_label} as the main internal cue boundaries inside this section.",
                phrase_window_ids=section_phrase_ids,
                phrase_group_ids=section_phrase_group_ids,
            )
        )

    recurring_group_ids = [
        str(group["id"])
        for group in repeated_groups
        if any(
            str(window.get("phrase_group_id")) == str(group["id"])
            for window in phrase_windows
        )
    ]
    recurring_motif_ids = [
        phrase_group_to_motif[group_id]
        for group_id in recurring_group_ids
        if group_id in phrase_group_to_motif
    ]
    if recurring_group_ids:
        group_label = ", ".join(recurring_group_ids[:3])
        motif_label = ", ".join(recurring_motif_ids[:3])
        recall_suffix = f" via motifs {motif_label}" if motif_label else ""
        hints.append(
            _build_inference_hint(
                section_id,
                "motif_recall",
                f"Repeated material returns here through phrase groups {group_label}{recall_suffix}; keep recalls visibly related instead of inventing a disconnected look.",
                phrase_window_ids=section_phrase_ids,
                phrase_group_ids=recurring_group_ids,
                motif_group_ids=recurring_motif_ids,
            )
        )
    elif summary is not None and float(summary.get("repetition_score", 0.0)) >= 0.15:
        hints.append(
            _build_inference_hint(
                section_id,
                "variation_rule",
                f"This section carries {_repetition_label(summary.get('repetition_score'))}; vary recalled looks deliberately instead of resetting to an unrelated scene.",
                phrase_window_ids=section_phrase_ids,
                phrase_group_ids=section_phrase_group_ids,
            )
        )

    return hints


def _build_inferred_sections(symbolic: dict, sections_payload: dict) -> list[dict]:
    section_summaries = {
        str(summary["section_id"]): summary
        for summary in symbolic.get("section_summaries", [])
    }
    phrase_windows_by_section: dict[str, list[dict]] = {}
    for window in symbolic.get("phrase_windows", []):
        section_id = window.get("section_id")
        if section_id is None:
            continue
        phrase_windows_by_section.setdefault(str(section_id), []).append(window)

    repeated_groups = symbolic.get("motif_summary", {}).get("repeated_phrase_groups", [])
    phrase_group_to_motif: dict[str, str] = {}
    for motif_group in symbolic.get("motif_summary", {}).get("motif_groups", []):
        motif_id = str(motif_group["id"])
        for phrase_group_id in motif_group.get("phrase_group_ids", []):
            phrase_group_to_motif[str(phrase_group_id)] = motif_id

    inferred_sections: list[dict] = []
    for section in sections_payload.get("sections", []):
        section_id = str(section["section_id"])
        inferred_sections.append(
            {
                "section_id": section_id,
                "label": _section_label(section),
                "start": round_schema_float(float(section["start"]), digits=6),
                "end": round_schema_float(float(section["end"]), digits=6),
                "hints": _section_inference_hints(
                    section,
                    section_summaries.get(section_id),
                    phrase_windows_by_section.get(section_id, []),
                    repeated_groups,
                    phrase_group_to_motif,
                ),
            }
        )
    return inferred_sections


def _load_existing_output(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _user_hints_by_section(existing_payload: dict | None) -> tuple[dict[str, list[dict]], list[dict]]:
    if existing_payload is None:
        return {}, []

    user_hints: dict[str, list[dict]] = {}
    orphan_sections: list[dict] = []
    for section in existing_payload.get("sections", []):
        section_id = str(section.get("section_id") or "")
        hints = [hint for hint in section.get("hints", []) if str(hint.get("source")) == "user"]
        if not hints:
            continue
        normalized_section = {
            "section_id": section_id,
            "label": section.get("label") or section_id,
            "start": section.get("start"),
            "end": section.get("end"),
            "hints": hints,
        }
        user_hints[section_id] = hints
        orphan_sections.append(normalized_section)

    return user_hints, orphan_sections


def _merge_sections(inferred_sections: list[dict], existing_payload: dict | None) -> list[dict]:
    user_hints, preserved_sections = _user_hints_by_section(existing_payload)
    inferred_ids = {section["section_id"] for section in inferred_sections}

    merged_sections: list[dict] = []
    for section in inferred_sections:
        section_id = section["section_id"]
        merged_sections.append(
            {
                "section_id": section_id,
                "label": section["label"],
                "start": section["start"],
                "end": section["end"],
                "hints": [*user_hints.get(section_id, []), *section["hints"]],
            }
        )

    for section in preserved_sections:
        if section["section_id"] in inferred_ids:
            continue
        merged_sections.append(section)
    return merged_sections


def _hint_count(sections: list[dict], source: str) -> int:
    return sum(
        1
        for section in sections
        for hint in section.get("hints", [])
        if str(hint.get("source")) == source
    )


def generate_section_hints(paths: SongPaths, symbolic: dict, sections_payload: dict) -> dict[str, str]:
    inferred_sections = _build_inferred_sections(symbolic, sections_payload)

    inferred_payload = {
        "schema_version": SCHEMA_VERSION,
        **build_song_schema_fields(paths),
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "symbolic-section-hints-v1",
            "dependencies": {
                "symbolic_layer_file": str(paths.artifact("layer_b_symbolic.json")),
                "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            },
        },
        "sections": inferred_sections,
    }
    inferred_path = paths.artifact("symbolic_transcription", "hints.json")
    write_json(inferred_path, inferred_payload)

    output_path = paths.song_output_dir / "hints.json"
    ensure_directory(paths.song_output_dir)
    existing_output = _load_existing_output(output_path)
    merged_sections = _merge_sections(inferred_sections, existing_output)
    merged_payload = {
        "schema_version": SCHEMA_VERSION,
        **build_song_schema_fields(paths),
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "editable-hints-merge-v1",
            "dependencies": {
                "inferred_hints_file": str(inferred_path),
                "symbolic_layer_file": str(paths.artifact("layer_b_symbolic.json")),
                "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            },
        },
        "summary": {
            "section_count": len(merged_sections),
            "inference_hint_count": _hint_count(merged_sections, "inference"),
            "user_hint_count": _hint_count(merged_sections, "user"),
        },
        "sections": merged_sections,
    }
    write_json(output_path, merged_payload)
    return {
        "symbolic_hints": str(inferred_path),
        "hints": str(output_path),
    }