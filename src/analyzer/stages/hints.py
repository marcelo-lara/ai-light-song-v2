from __future__ import annotations

from pathlib import Path

from analyzer.io import ensure_directory, read_json, write_json
from analyzer.models import SCHEMA_VERSION, build_song_schema_fields, round_schema_float
from analyzer.paths import SongPaths
from analyzer.stages.hint_alignment import find_primary_section


def _section_label(section: dict) -> str:
    label = section.get("function") or section.get("label") or section.get("section_id")
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


def _transition_role_phrase(section_function: str) -> str:
    if section_function in {"chorus", "hook"}:
        return "new focal state"
    if section_function == "verse":
        return "new pulse state"
    if section_function in {"inst", "solo"}:
        return "new accompaniment-led state"
    if section_function == "bridge":
        return "new drum-led state"
    return "new section state"


def _transition_role_hint(section: dict, previous_section: dict | None) -> dict | None:
    if previous_section is None:
        return None

    previous_label = _section_label(previous_section)
    current_label = _section_label(section)
    if previous_label == current_label:
        return None
    if previous_label not in {"intro", "break", "outro"}:
        return None
    if current_label not in {"verse", "chorus", "bridge", "inst", "solo"}:
        return None

    start_s = round_schema_float(float(section["start"]), digits=2)
    section_id = str(section["section_id"])
    section_label = current_label.replace("_", " ")
    role_phrase = _transition_role_phrase(current_label)
    return _build_inference_hint(
        section_id,
        "transition",
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


def _human_hint_id(section_id: str, human_hint_id: str) -> str:
    return f"{section_id}-human-{human_hint_id}"


def _build_human_hints(paths: SongPaths, sections_payload: dict) -> dict[str, list[dict]]:
    reference_path = paths.reference("human", "human_hints.json")
    if not reference_path.exists():
        return {}

    hints_payload = read_json(reference_path)
    sections = sections_payload.get("sections", [])

    human_hints_by_section: dict[str, list[dict]] = {}
    unsectioned_hints: list[dict] = []
    for human_hint in hints_payload.get("human_hints", []):
        summary = human_hint.get("summary") or ""
        title = human_hint.get("title") or ""
        text = summary.strip() or title.strip()
        if not text:
            continue

        start_time = round_schema_float(float(human_hint["start_time"]), digits=6)
        end_time = round_schema_float(float(human_hint["end_time"]), digits=6)

        primary_section = find_primary_section(sections, start_time, end_time)
        section_id = str(primary_section["section_id"]) if primary_section is not None else "unsectioned"

        hint: dict = {
            "id": _human_hint_id(section_id, str(human_hint.get("id"))),
            "source": "human",
            "text": text,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "anchor_refs": {
                "phrase_window_ids": [],
                "phrase_group_ids": [],
                "motif_group_ids": [],
            },
        }
        lighting_hint = human_hint.get("lighting_hint") or ""
        if lighting_hint.strip():
            hint["lighting_hint"] = lighting_hint

        if primary_section is not None:
            human_hints_by_section.setdefault(section_id, []).append(hint)
        else:
            unsectioned_hints.append(hint)

    if unsectioned_hints:
        human_hints_by_section.setdefault("unsectioned", []).extend(unsectioned_hints)

    return human_hints_by_section


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


def _merge_sections(
    inferred_sections: list[dict],
    existing_payload: dict | None,
    human_hints_by_section: dict[str, list[dict]] | None = None,
) -> list[dict]:
    user_hints, preserved_sections = _user_hints_by_section(existing_payload)
    human_hints_by_section = human_hints_by_section or {}
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
                "hints": [
                    *user_hints.get(section_id, []),
                    *human_hints_by_section.get(section_id, []),
                    *section["hints"],
                ],
            }
        )

    for section in preserved_sections:
        if section["section_id"] in inferred_ids:
            continue
        merged_sections.append(section)

    unsectioned_hints = human_hints_by_section.get("unsectioned")
    if unsectioned_hints and "unsectioned" not in inferred_ids:
        merged_sections.append(
            {
                "section_id": "unsectioned",
                "label": "unsectioned",
                "start": min(hint["start_time"] for hint in unsectioned_hints),
                "end": max(hint["end_time"] for hint in unsectioned_hints),
                "hints": unsectioned_hints,
            }
        )
    return merged_sections


def _hint_count(sections: list[dict], *sources: str) -> int:
    return sum(
        1
        for section in sections
        for hint in section.get("hints", [])
        if str(hint.get("source")) in sources
    )


def generate_section_hints(paths: SongPaths, sections_payload: dict) -> dict[str, str]:
    inferred_sections = _build_inferred_sections(sections_payload)
    human_hints_by_section = _build_human_hints(paths, sections_payload)

    output_path = paths.hints_output_path
    ensure_directory(paths.song_output_dir)
    existing_output = _load_existing_output(output_path)
    merged_sections = _merge_sections(inferred_sections, existing_output, human_hints_by_section)
    merged_payload = {
        "schema_version": SCHEMA_VERSION,
        **build_song_schema_fields(paths),
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "editable-hints-merge-v1",
            "dependencies": {
                "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
                "human_hints_file": str(paths.reference("human", "human_hints.json")),
            },
        },
        "summary": {
            "section_count": len(merged_sections),
            "inference_hint_count": _hint_count(merged_sections, "inference"),
            "user_hint_count": _hint_count(merged_sections, "user", "human"),
        },
        "sections": merged_sections,
    }
    write_json(output_path, merged_payload)
    return {
        "hints": str(output_path),
    }
