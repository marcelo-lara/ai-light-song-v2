
from __future__ import annotations
from collections import Counter

from typing import Any

from analyzer.paths import SongPaths
from analyzer.io import ensure_directory, write_json, read_json
from analyzer.models import to_jsonable, SCHEMA_VERSION

from .utils import *

def extract_symbolic_features(paths: SongPaths, stems: dict[str, str], timing: dict, sections_payload: dict) -> dict:
    raw_dir = paths.artifact("symbolic_transcription", "basic_pitch")
    ensure_directory(raw_dir)

    source_paths = dict(stems)
    source_paths["full_mix"] = str(paths.song_path)

    raw_payloads: dict[str, dict] = {}
    aligned_by_source: dict[str, list[dict]] = {}
    validation_rows: list[dict] = []
    for source_stem, config in SOURCE_CONFIGS.items():
        raw_payload = _predict_stem_notes(
            stem_path=source_paths[config["path_key"]],
            output_dir=raw_dir,
            source_stem=source_stem,
            onset_threshold=float(config["onset_threshold"]),
            frame_threshold=float(config["frame_threshold"]),
            minimum_note_length=float(config["minimum_note_length"]),
            minimum_frequency=config["minimum_frequency"],
            maximum_frequency=config["maximum_frequency"],
        )
        raw_payloads[source_stem] = raw_payload
        aligned_notes = _align_note_events(
            raw_payload["notes"],
            timing,
            sections_payload,
            tolerance_seconds=float(config.get("beat_alignment_tolerance_s", 0.2)),
        )
        aligned_by_source[source_stem] = aligned_notes
        validation_row = _validate_transcription_source(source_stem, aligned_notes)
        validation_row["promotion_policy"] = config["promotion_policy"]
        validation_rows.append(validation_row)

    promoted_sources = [row["source_stem"] for row in validation_rows if row["promote_to_final"]]
    merged_notes = [
        note
        for source_stem in promoted_sources
        for note in aligned_by_source[source_stem]
    ]
    final_notes = _deduplicate_notes(merged_notes)

    bass_notes = [note for note in final_notes if note["source_stem"] == "bass"]
    harmonic_notes = [note for note in final_notes if note["source_stem"] == "harmonic"]
    density_per_beat = _compute_density_per_beat(final_notes, timing, sections_payload)
    density_per_bar = _compute_density_per_bar(final_notes, timing, sections_payload)
    section_summaries = [
        _section_summary(section, final_notes, density_per_bar, timing)
        for section in sections_payload.get("sections", [])
    ]
    phrase_windows, repeated_phrase_groups, motif_groups, repetition_score = _phrase_windows(
        final_notes,
        timing,
        sections_payload,
    )
    section_repetition_index = {
        summary["section_id"]: 0.0
        for summary in section_summaries
    }
    phrase_window_index = {window["id"]: window for window in phrase_windows}
    for group in repeated_phrase_groups:
        windows = [phrase_window_index[window_id] for window_id in group["phrase_window_ids"] if window_id in phrase_window_index]
        grouped_sections = Counter(window["section_id"] for window in windows if window["section_id"])
        for section_id, occurrence_count in grouped_sections.items():
            section_repetition_index[section_id] += occurrence_count
    max_section_occurrences = max(section_repetition_index.values(), default=0.0)
    for summary in section_summaries:
        raw_value = section_repetition_index.get(summary["section_id"], 0.0)
        summary["repetition_score"] = round(
            float(raw_value / max_section_occurrences) if max_section_occurrences else 0.0,
            6,
        )

    symbolic_summary = _compute_symbolic_summary(
        final_notes,
        density_per_bar,
        section_summaries,
        repetition_score,
    )
    dominant_motif_id = (
        max(motif_groups, key=lambda group: (group["occurrence_count"], len(group["occurrence_refs"]))) ["id"]
        if motif_groups
        else None
    )
    motif_summary = {
        "dominant_motif_id": dominant_motif_id,
        "motif_groups": motif_groups,
        "repeated_phrase_groups": repeated_phrase_groups,
    }
    abstraction = _build_symbolic_abstraction(
        symbolic_summary,
        density_per_bar,
        section_summaries,
        phrase_windows,
        motif_summary,
    )

    validation_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "transcription_sources": [
                str(raw_dir / f"{source_stem}.json") for source_stem in SOURCE_CONFIGS
            ],
        },
        "sources": validation_rows,
        "promoted_sources": promoted_sources,
        "final_note_count": len(final_notes),
    }
    write_json(paths.artifact("symbolic_transcription", "validation.json"), validation_payload)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "harmonic_stem": stems["harmonic"],
            "bass_stem": stems["bass"],
            "vocals_stem": stems["vocals"],
            "drums_stem": stems["drums"],
            "full_mix": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "transcription_sources": [
                str(raw_dir / f"{source_stem}.json") for source_stem in SOURCE_CONFIGS
            ],
            "validation_file": str(paths.artifact("symbolic_transcription", "validation.json")),
            "engine": "basic-pitch-all-sources-validated",
        },
        "note_events": final_notes,
        "symbolic_summary": {
            **symbolic_summary,
            "harmonic_note_count": len(harmonic_notes),
            "bass_note_count": len(bass_notes),
            "bass_pitch_range": {
                "min": min(int(note["pitch"]) for note in bass_notes) if bass_notes else None,
                "max": max(int(note["pitch"]) for note in bass_notes) if bass_notes else None,
            },
            "transcription_engines": ["basic-pitch"],
            "extra_features": [
                "pitch_bend",
                "model_output_summary",
                "per-stem midi cache",
                "all-source validation",
                "density-per-beat",
                "phrase-window grouping",
            ],
            "promoted_sources": promoted_sources,
        },
        "description": abstraction["description"],
        "abstraction": abstraction,
        "density_per_beat": density_per_beat,
        "density_per_bar": density_per_bar,
        "section_summaries": section_summaries,
        "phrase_windows": phrase_windows,
        "motif_summary": motif_summary,
        "validation_summary": validation_payload,
        "transcription_sources": {
            source_stem: {
                "raw_file": str(raw_dir / f"{source_stem}.json"),
                "midi_file": raw_payloads[source_stem]["midi_file"],
                "note_count": raw_payloads[source_stem]["note_count"],
                "pitch_bend_count": raw_payloads[source_stem]["pitch_bend_count"],
            }
            for source_stem in SOURCE_CONFIGS
        },
    }
    write_json(paths.artifact("layer_b_symbolic.json"), payload)
    return payload