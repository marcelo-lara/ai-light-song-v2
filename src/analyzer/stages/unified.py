from __future__ import annotations

from collections import Counter

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _phrase_id_label(phrase: dict) -> str:
    return str(phrase.get("id") or phrase.get("phrase_group_id") or "phrase")


def assemble_music_feature_layers(
    paths: SongPaths,
    timing: dict,
    harmonic: dict,
    symbolic: dict,
    energy: dict,
    patterns: dict,
    sections_payload: dict,
) -> dict:
    section_rows = sections_payload.get("sections", [])
    phrases = symbolic.get("phrase_windows", [])
    accent_windows = [
        {
            "id": accent["id"],
            "time_s": accent["time"],
            "kind": accent["kind"],
            "intensity": accent["intensity"],
            "section_id": accent.get("section_id"),
            "section_name": accent.get("section_name"),
        }
        for accent in energy.get("accent_candidates", [])
    ]

    cue_anchors: list[dict] = []
    for phrase in phrases:
        cue_anchors.append(
            {
                "id": f"anchor_{_phrase_id_label(phrase)}_start",
                "time_s": phrase["start_s"],
                "anchor_type": "phrase_start",
                "section_id": phrase.get("section_id"),
                "phrase_window_id": phrase["id"],
            }
        )
    for section in section_rows:
        cue_anchors.append(
            {
                "id": f"anchor_{section['section_id']}_start",
                "time_s": round(float(section["start"]), 6),
                "anchor_type": "section_start",
                "section_id": section["section_id"],
                "phrase_window_id": None,
            }
        )
    for accent in accent_windows:
        cue_anchors.append(
            {
                "id": f"anchor_{accent['id']}",
                "time_s": accent["time_s"],
                "anchor_type": f"accent_{accent['kind']}",
                "section_id": accent.get("section_id"),
                "phrase_window_id": None,
            }
        )
    cue_anchors.sort(key=lambda item: (float(item["time_s"]), str(item["id"])))

    pattern_callbacks: list[dict] = []
    for pattern in patterns.get("patterns", []):
        for occurrence_index, occurrence in enumerate(pattern.get("occurrences", []), start=1):
            section = _section_for_time(float(occurrence["start_s"]), section_rows)
            pattern_callbacks.append(
                {
                    "id": f"pattern_callback_{pattern['id']}_{occurrence_index}",
                    "pattern_id": pattern["id"],
                    "occurrence_index": occurrence_index,
                    "start_s": occurrence["start_s"],
                    "end_s": occurrence["end_s"],
                    "section_id": section.get("section_id") if section else None,
                    "callback_action": "repeat_with_variation" if occurrence_index > 1 else "establish",
                }
            )

    repeated_phrase_groups = {
        group["id"]: group
        for group in symbolic.get("motif_summary", {}).get("repeated_phrase_groups", [])
    }
    phrase_group_primary_section: dict[str, str | None] = {}
    for group_id in repeated_phrase_groups:
        refs = [phrase for phrase in phrases if str(phrase.get("phrase_group_id")) == group_id]
        if not refs:
            phrase_group_primary_section[group_id] = None
            continue
        phrase_group_primary_section[group_id] = Counter(
            str(phrase.get("section_id"))
            for phrase in refs
            if phrase.get("section_id") is not None
        ).most_common(1)[0][0]

    motif_callbacks: list[dict] = []
    for motif_group in symbolic.get("motif_summary", {}).get("motif_groups", []):
        for phrase_group_id in motif_group.get("phrase_group_ids", []):
            refs = [
                reference
                for reference in motif_group.get("occurrence_refs", [])
                if reference.get("phrase_window_id") in set(repeated_phrase_groups.get(phrase_group_id, {}).get("phrase_window_ids", []))
            ]
            if not refs:
                continue
            start_s = min(float(reference["start_s"]) for reference in refs)
            end_s = max(float(reference["end_s"]) for reference in refs)
            motif_callbacks.append(
                {
                    "id": f"motif_callback_{motif_group['id']}_{phrase_group_id}",
                    "motif_group_id": motif_group["id"],
                    "phrase_group_id": phrase_group_id,
                    "start_s": round(start_s, 6),
                    "end_s": round(end_s, 6),
                    "section_id": phrase_group_primary_section.get(phrase_group_id),
                    "callback_action": "echo",
                }
            )

    section_cards = []
    symbolic_section_index = {
        row["section_id"]: row
        for row in symbolic.get("section_summaries", [])
    }
    energy_section_index = {
        row["section_id"]: row
        for row in energy.get("section_energy", [])
    }
    for section in section_rows:
        section_id = section["section_id"]
        symbolic_card = symbolic_section_index.get(section_id, {})
        energy_card = energy_section_index.get(section_id, {})
        local_phrases = [phrase for phrase in phrases if phrase.get("section_id") == section_id]
        section_cards.append(
            {
                "section_id": section_id,
                "section_name": section.get("label"),
                "start_s": round(float(section["start"]), 6),
                "end_s": round(float(section["end"]), 6),
                "symbolic_description": next(
                    (
                        row["description"]
                        for row in symbolic.get("abstraction", {}).get("section_descriptions", [])
                        if row.get("section_id") == section_id
                    ),
                    None,
                ),
                "energy_level": energy_card.get("level"),
                "energy_trend": energy_card.get("trend"),
                "phrase_count": len(local_phrases),
                "motif_activity": symbolic_card.get("repetition_score"),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "source_song_path": str(paths.song_path),
        "generated_from": {
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "symbolic_layer_file": str(paths.artifact("layer_b_symbolic.json")),
            "energy_layer_file": str(paths.artifact("layer_c_energy.json")),
            "patterns_layer_file": str(paths.artifact("layer_d_patterns.json")),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
        },
        "metadata": {
            "title": paths.song_name,
            "duration_s": round(float(timing["bars"][-1]["end_s"]), 6),
            "bpm": round(float(timing["bpm"]), 2),
            "time_signature": timing.get("time_signature", "4/4"),
            "key": harmonic.get("global_key", {}).get("label"),
        },
        "timeline": {
            "beats": timing["beats"],
            "bars": timing["bars"],
            "sections": section_rows,
            "phrases": [
                {
                    "id": phrase["id"],
                    "phrase_group_id": phrase["phrase_group_id"],
                    "start_s": phrase["start_s"],
                    "end_s": phrase["end_s"],
                    "start_bar": phrase["start_bar"],
                    "end_bar": phrase["end_bar"],
                    "section_id": phrase.get("section_id"),
                }
                for phrase in phrases
            ],
            "accent_windows": accent_windows,
        },
        "layers": {
            "harmonic": {
                "global_key": harmonic.get("global_key"),
                "chords": harmonic.get("chords"),
                "description": harmonic.get("description"),
            },
            "symbolic": {
                "description": symbolic.get("description"),
                "symbolic_summary": symbolic.get("symbolic_summary"),
                "motif_summary": symbolic.get("motif_summary"),
                "phrase_groups": symbolic.get("motif_summary", {}).get("repeated_phrase_groups", []),
                "abstraction": symbolic.get("abstraction"),
            },
            "energy": {
                "global_energy": energy.get("global_energy"),
                "section_energy": energy.get("section_energy"),
                "accent_candidates": energy.get("accent_candidates"),
            },
            "patterns": {
                "patterns": patterns.get("patterns", []),
                "occurrences": [
                    {
                        **occurrence,
                        "pattern_id": pattern["id"],
                    }
                    for pattern in patterns.get("patterns", [])
                    for occurrence in pattern.get("occurrences", [])
                ],
            },
        },
        "section_cards": section_cards,
        "lighting_context": {
            "cue_anchors": cue_anchors,
            "pattern_callbacks": pattern_callbacks,
            "motif_callbacks": motif_callbacks,
        },
        "generation_notes": [
            "Symbolic motif repetition remains sourced from layer_b_symbolic.json.",
            "Harmonic progression repetition remains sourced from layer_d_patterns.json.",
            "Accent windows are derived from layer_c_energy.json accent candidates.",
        ],
        "mapping_rules": [],
    }
    write_json(paths.artifact("music_feature_layers.json"), payload)
    return payload