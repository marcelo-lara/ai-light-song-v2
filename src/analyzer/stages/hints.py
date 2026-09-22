from __future__ import annotations

from analyzer.io import ensure_directory, read_json, write_json
from analyzer.models import (
    SCHEMA_VERSION,
    build_song_schema_fields,
    round_schema_float,
    validate_field_sources,
)
from analyzer.paths import SongPaths
from analyzer.stages.hint_alignment import find_primary_section

# v3.6 item 8 — hints.json is now a flat, human-only `hints[]`: no `sections[]`
# wrapper (it duplicated sections.json), no `id` / `category` / `anchor_refs`
# (dead — anchor_refs pointed at removed stages), and no inference rows
# (cue-authoring prose like "Treat 30.00s as the main cue reset..." — out of
# scope; the code that generated them is deleted below, not just filtered at
# publish time). Every row is `source: "human"` by construction, so `source`
# is declared once in `field_sources` rather than repeated per row.

HINT_ROW_FIELDS = ("section_id", "title", "text", "start_time", "end_time", "lighting_hint")


def _build_human_hint_rows(paths: SongPaths, sections_payload: dict) -> list[dict]:
    """`sections_payload` must be the PUBLISHED `sections.json` (v3.7 item 6)
    — never `artifacts/section_segmentation/sections.json` (allin1's raw,
    coarser boundaries). The published table is what a reader sees when it
    looks up `section_id`, so attribution has to match it: a hint inside the
    human-curated pre-chorus must report that pre-chorus's `section_id`, not
    whichever coarser allin1 run happened to contain the same timestamp."""
    reference_path = paths.reference("human", "human_hints.json")
    if not reference_path.exists():
        return []

    hints_payload = read_json(reference_path)
    sections = sections_payload.get("sections", [])

    rows: list[dict] = []
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

        lighting_hint = (human_hint.get("lighting_hint") or "").strip() or None

        rows.append(
            {
                "section_id": section_id,
                "title": title,
                "text": text,
                "start_time": start_time,
                "end_time": end_time,
                "lighting_hint": lighting_hint,
            }
        )

    rows.sort(key=lambda row: row["start_time"])
    return rows


def generate_section_hints(paths: SongPaths, sections_payload: dict) -> dict[str, str]:
    hint_rows = _build_human_hint_rows(paths, sections_payload)

    output_path = paths.hints_output_path
    ensure_directory(paths.song_output_dir)

    # v3.7 item 6 — `section_id` is attributed by timestamp against the
    # published sections.json (source "sections"), never the human-authored
    # hint text itself; every other field is genuinely human-authored.
    hints_field_sources = validate_field_sources(
        {**dict.fromkeys(HINT_ROW_FIELDS, "human"), "section_id": "sections"},
        hint_rows[0].keys() if hint_rows else HINT_ROW_FIELDS,
        file="hints.json",
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        **build_song_schema_fields(paths),
        "field_sources": hints_field_sources,
        "hints": hint_rows,
    }
    write_json(output_path, payload)
    return {
        "hints": str(output_path),
    }
