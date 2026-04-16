from __future__ import annotations

from pathlib import Path
import sys

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.stages._basic_pitch_runtime import load_basic_pitch_predict


def _build_payload(
    *,
    stem_path: str,
    output_dir: Path,
    source_stem: str,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_length: float,
    minimum_frequency: float | None,
    maximum_frequency: float | None,
) -> dict:
    model_path, predict = load_basic_pitch_predict()
    model_output, midi_data, note_events = predict(
        stem_path,
        model_or_model_path=model_path,
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

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": output_dir.parent.parent.name,
        "source_stem": source_stem,
        "generated_from": {
            "stem_file": stem_path,
            "engine": "basic-pitch",
            "model": str(model_path),
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
    write_json(output_dir / f"{source_stem}.json", payload)
    return payload


def main(argv: list[str]) -> int:
    stem_path = argv[1]
    output_dir = Path(argv[2])
    source_stem = argv[3]
    onset_threshold = float(argv[4])
    frame_threshold = float(argv[5])
    minimum_note_length = float(argv[6])
    minimum_frequency = None if argv[7] == "none" else float(argv[7])
    maximum_frequency = None if argv[8] == "none" else float(argv[8])

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = _build_payload(
        stem_path=stem_path,
        output_dir=output_dir,
        source_stem=source_stem,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_length,
        minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency,
    )
    _ = payload
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))