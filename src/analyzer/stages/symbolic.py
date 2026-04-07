from __future__ import annotations

from pathlib import Path
from statistics import mean, median

from analyzer.exceptions import DependencyError
from analyzer.io import ensure_directory, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths


SOURCE_CONFIGS = {
    "harmonic": {
        "path_key": "harmonic",
        "onset_threshold": 0.4,
        "frame_threshold": 0.25,
        "minimum_note_length": 90.0,
        "minimum_frequency": 65.0,
        "maximum_frequency": None,
        "promotion_policy": "core",
    },
    "bass": {
        "path_key": "bass",
        "onset_threshold": 0.3,
        "frame_threshold": 0.2,
        "minimum_note_length": 80.0,
        "minimum_frequency": 32.7,
        "maximum_frequency": 330.0,
        "promotion_policy": "core",
    },
    "vocals": {
        "path_key": "vocals",
        "onset_threshold": 0.35,
        "frame_threshold": 0.2,
        "minimum_note_length": 70.0,
        "minimum_frequency": 98.0,
        "maximum_frequency": 1400.0,
        "promotion_policy": "candidate",
    },
    "drums": {
        "path_key": "drums",
        "onset_threshold": 0.45,
        "frame_threshold": 0.35,
        "minimum_note_length": 60.0,
        "minimum_frequency": 36.0,
        "maximum_frequency": 2000.0,
        "promotion_policy": "auxiliary",
    },
    "full_mix": {
        "path_key": "full_mix",
        "onset_threshold": 0.4,
        "frame_threshold": 0.22,
        "minimum_note_length": 85.0,
        "minimum_frequency": 55.0,
        "maximum_frequency": None,
        "promotion_policy": "candidate",
    },
}

SOURCE_PRIORITY = {
    "bass": 0,
    "harmonic": 1,
    "vocals": 2,
    "full_mix": 3,
    "drums": 4,
}


def _predict_stem_notes(
    stem_path: str,
    output_dir: Path,
    source_stem: str,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_length: float,
    minimum_frequency: float | None,
    maximum_frequency: float | None,
) -> dict:
    try:
        from basic_pitch.inference import ICASSP_2022_MODEL_PATH, predict
    except ImportError as exc:
        raise DependencyError("basic-pitch is required for symbolic transcription") from exc

    model_output, midi_data, note_events = predict(
        stem_path,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_length,
        minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency,
        multiple_pitch_bends=True,
        melodia_trick=True,
    )

    midi_path = output_dir / f"{source_stem}.mid"
    midi_data.write(str(midi_path))

    notes = []
    pitch_bend_count = 0
    for index, event in enumerate(note_events, start=1):
        start_s, end_s, pitch, confidence, pitch_bend = event
        bends = [int(value) for value in pitch_bend] if pitch_bend else []
        pitch_bend_count += len(bends)
        notes.append(
            {
                "note_id": f"{source_stem}-note-{index:05d}",
                "time": round(float(start_s), 6),
                "end_s": round(float(end_s), 6),
                "duration": round(float(end_s - start_s), 6),
                "pitch": int(pitch),
                "velocity": round(float(confidence), 6),
                "confidence": round(float(confidence), 6),
                "source_stem": source_stem,
                "transcription_engine": "basic-pitch",
                "pitch_bend": bends,
                "pitch_bend_range": {
                    "min": min(bends) if bends else None,
                    "max": max(bends) if bends else None,
                },
            }
        )

    raw_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_id": output_dir.parent.parent.name,
        "source_stem": source_stem,
        "generated_from": {
            "stem_file": stem_path,
            "engine": "basic-pitch",
            "model": str(ICASSP_2022_MODEL_PATH),
            "thresholds": {
                "onset_threshold": onset_threshold,
                "frame_threshold": frame_threshold,
                "minimum_note_length_ms": minimum_note_length,
                "minimum_frequency": minimum_frequency,
                "maximum_frequency": maximum_frequency,
            },
        },
        "model_output_summary": {
            key: {
                "shape": list(value.shape),
                "max": round(float(value.max()), 6),
                "mean": round(float(value.mean()), 6),
            }
            for key, value in model_output.items()
        },
        "note_count": len(notes),
        "pitch_bend_count": pitch_bend_count,
        "notes": notes,
        "midi_file": str(midi_path),
    }
    write_json(output_dir / f"{source_stem}.json", raw_payload)
    return raw_payload


def _nearest_beat_alignment(time_s: float, beat_times: list[float], tolerance_seconds: float = 0.2) -> tuple[int | None, float | None]:
    if not beat_times:
        return None, None
    beat_index = min(range(len(beat_times)), key=lambda index: abs(beat_times[index] - time_s))
    delta = float(time_s - beat_times[beat_index])
    if abs(delta) > tolerance_seconds:
        return None, delta
    return beat_index, delta


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _align_note_events(notes: list[dict], timing: dict, sections_payload: dict) -> list[dict]:
    beat_points = timing["beats"]
    beat_times = [float(beat["time"]) for beat in beat_points]
    bars = timing["bars"]
    sections = sections_payload.get("sections", [])

    aligned_notes = []
    for note in notes:
        aligned_beat_index, beat_delta = _nearest_beat_alignment(float(note["time"]), beat_times)
        aligned_bar = None
        aligned_beat = None
        if aligned_beat_index is not None:
            beat = beat_points[aligned_beat_index]
            aligned_bar = int(beat["bar"])
            aligned_beat = int(beat["index"])
        else:
            for bar in bars:
                if float(bar["start_s"]) <= float(note["time"]) < float(bar["end_s"]):
                    aligned_bar = int(bar["bar"])
                    break

        section = _section_for_time(float(note["time"]), sections)
        aligned = {key: value for key, value in note.items() if key != "pitch_bend"}
        aligned.update(
            {
                "aligned_beat": aligned_beat,
                "aligned_bar": aligned_bar,
                "beat_time_delta": round(float(beat_delta), 6) if beat_delta is not None else None,
                "alignment_resolved": aligned_beat_index is not None,
                "section_id": section.get("section_id") if section else None,
                "section_name": section.get("label") if section else None,
                "pitch_bend_step_count": len(note.get("pitch_bend", [])),
            }
        )
        aligned_notes.append(aligned)
    return aligned_notes


def _validate_transcription_source(source_stem: str, notes: list[dict]) -> dict:
    note_count = len(notes)
    confidence_values = [float(note["confidence"]) for note in notes]
    pitch_values = [int(note["pitch"]) for note in notes]
    resolved_count = sum(1 for note in notes if note.get("alignment_resolved"))
    duration_values = [float(note["duration"]) for note in notes]
    low_register_ratio = (
        sum(1 for pitch in pitch_values if pitch <= 55) / note_count if note_count else 0.0
    )
    mid_high_ratio = (
        sum(1 for pitch in pitch_values if pitch >= 60) / note_count if note_count else 0.0
    )

    if source_stem == "bass":
        promote = note_count > 0 and low_register_ratio >= 0.45
        decision = "promoted" if promote else "rejected"
        reason = "bass source passed low-register validation" if promote else "bass source did not sustain enough low-register notes"
    elif source_stem == "harmonic":
        promote = note_count > 0 and (resolved_count / max(note_count, 1)) >= 0.2
        decision = "promoted" if promote else "rejected"
        reason = "harmonic source provides core note texture" if promote else "harmonic source alignment coverage was too low"
    elif source_stem == "vocals":
        promote = note_count > 0 and (mean(confidence_values) if confidence_values else 0.0) >= 0.35 and mid_high_ratio >= 0.5
        decision = "promoted" if promote else "auxiliary_only"
        reason = "vocal melody notes passed confidence and register checks" if promote else "vocal source kept as auxiliary only"
    elif source_stem == "full_mix":
        promote = note_count > 0 and (mean(confidence_values) if confidence_values else 0.0) >= 0.3
        decision = "promoted" if promote else "auxiliary_only"
        reason = "full-mix source complements missing notes from stems" if promote else "full-mix source retained only as raw cache"
    else:
        promote = False
        decision = "auxiliary_only"
        reason = "percussive source analyzed for review but not promoted to the final melodic note stream by default"

    return {
        "source_stem": source_stem,
        "note_count": note_count,
        "alignment_resolved_ratio": round(resolved_count / max(note_count, 1), 6) if note_count else 0.0,
        "confidence_mean": round(mean(confidence_values), 6) if confidence_values else None,
        "confidence_median": round(median(confidence_values), 6) if confidence_values else None,
        "pitch_range": {
            "min": min(pitch_values) if pitch_values else None,
            "max": max(pitch_values) if pitch_values else None,
        },
        "median_duration": round(median(duration_values), 6) if duration_values else None,
        "low_register_ratio": round(low_register_ratio, 6),
        "mid_high_ratio": round(mid_high_ratio, 6),
        "decision": decision,
        "promote_to_final": promote,
        "reason": reason,
    }


def _deduplicate_notes(notes: list[dict]) -> list[dict]:
    deduplicated: list[dict] = []
    for note in sorted(
        notes,
        key=lambda item: (
            float(item["time"]),
            SOURCE_PRIORITY.get(str(item["source_stem"]), 99),
            -float(item["confidence"]),
        ),
    ):
        duplicate = None
        for existing in reversed(deduplicated[-12:]):
            if abs(float(existing["time"]) - float(note["time"])) > 0.075:
                continue
            if abs(int(existing["pitch"]) - int(note["pitch"])) > 1:
                continue
            duplicate = existing
            break
        if duplicate is None:
            deduplicated.append(note)
            continue
        current_priority = SOURCE_PRIORITY.get(str(note["source_stem"]), 99)
        existing_priority = SOURCE_PRIORITY.get(str(duplicate["source_stem"]), 99)
        if current_priority < existing_priority or (
            current_priority == existing_priority and float(note["confidence"]) > float(duplicate["confidence"])
        ):
            deduplicated[deduplicated.index(duplicate)] = note
    deduplicated.sort(key=lambda item: (float(item["time"]), int(item["pitch"]), str(item["source_stem"])))
    return deduplicated


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
        aligned_notes = _align_note_events(raw_payload["notes"], timing, sections_payload)
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

    pitch_values = [int(note["pitch"]) for note in final_notes]
    bass_notes = [note for note in final_notes if note["source_stem"] == "bass"]
    harmonic_notes = [note for note in final_notes if note["source_stem"] == "harmonic"]

    validation_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_id": paths.song_id,
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
        "song_id": paths.song_id,
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
            "note_count": len(final_notes),
            "harmonic_note_count": len(harmonic_notes),
            "bass_note_count": len(bass_notes),
            "pitch_range": {
                "min": min(pitch_values) if pitch_values else None,
                "max": max(pitch_values) if pitch_values else None,
            },
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
            ],
            "promoted_sources": promoted_sources,
        },
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