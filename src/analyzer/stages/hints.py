from __future__ import annotations

from pathlib import Path

from analyzer.io import ensure_directory, read_json, write_json
from analyzer.models import SCHEMA_VERSION, build_song_schema_fields, round_schema_float
from analyzer.paths import SongPaths


def _section_label(section: dict) -> str:
    label = section.get("section_character") or section.get("label") or section.get("section_id")
    return str(label)


def _hint_id(section_id: str, category: str) -> str:
    return f"{section_id}-inference-{category}"


def _build_inference_hint(section_id: str, category: str, text: str) -> dict:
    return {
        "id": _hint_id(section_id, category),
        "source": "inference",
        "category": category,
        "text": text,
        "anchor_refs": {
            "phrase_window_ids": [],
            "phrase_group_ids": [],
            "motif_group_ids": [],
        },
    }


def _transition_role_phrase(section_name: str) -> str:
    if section_name in {"groove_plateau", "momentum_lift", "flowing_plateau"}:
        return "new pulse state"
    if section_name in {"focal_lift", "vocal_lift", "vocal_spotlight"}:
        return "new focal state"
    if section_name == "instrumental_bed":
        return "new accompaniment-led state"
    if section_name == "percussion_break":
        return "new drum-led state"
    return "new section state"


def _transition_role_hint(section: dict, previous_section: dict | None) -> dict | None:
    if previous_section is None:
        return None

    previous_label = _section_label(previous_section)
    current_label = _section_label(section)
    if previous_label == current_label:
        return None
    if previous_label not in {"contrast_bridge", "breath_space", "ambient_opening"}:
        return None
    if current_label not in {
        "groove_plateau",
        "momentum_lift",
        "flowing_plateau",
        "instrumental_bed",
        "focal_lift",
        "vocal_lift",
        "vocal_spotlight",
        "percussion_break",
    }:
        return None

    start_s = round_schema_float(float(section["start"]), digits=2)
    section_id = str(section["section_id"])
    section_label = current_label.replace("_", " ")
    role_phrase = _transition_role_phrase(current_label)
    return _build_inference_hint(
        section_id,
        "transition_role",
        (
            f"Treat {start_s:.2f}s as the main cue reset into this {section_label}; "
            f"let the {role_phrase} land on the boundary instead of drifting late."
        ),
    )


def _section_inference_hints(section: dict, previous_section: dict | None = None) -> list[dict]:
    hints: list[dict] = []
    transition_hint = _transition_role_hint(section, previous_section)
    if transition_hint is not None:
        hints.append(transition_hint)
    return hints


def _build_inferred_sections(sections_payload: dict) -> list[dict]:
    inferred_sections: list[dict] = []
    previous_section: dict | None = None
    for section in sections_payload.get("sections", []):
        section_id = str(section["section_id"])
        inferred_sections.append(
            {
                "section_id": section_id,
                "label": _section_label(section),
                "start": round_schema_float(float(section["start"]), digits=6),
                "end": round_schema_float(float(section["end"]), digits=6),
                "hints": _section_inference_hints(section, previous_section),
            }
        )
        previous_section = section
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


def generate_section_hints(paths: SongPaths, sections_payload: dict) -> dict[str, str]:
    inferred_sections = _build_inferred_sections(sections_payload)

    output_path = paths.hints_output_path
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
        "hints": str(output_path),
    }
