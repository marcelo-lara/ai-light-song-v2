from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import GeneratedFrom, SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths


SAMPLE_RATE = 44100
RMS_INTERVAL_MS = 10
ENVELOPE_WINDOW_MS = 200
SOURCE_ORDER: tuple[tuple[str, str], ...] = (
    ("mix", "Mix"),
    ("bass", "Bass"),
    ("drums", "Drums"),
    ("harmonic", "Harmonic"),
    ("vocals", "Vocals"),
)


def _normalize(values: np.ndarray) -> np.ndarray:
    maximum = float(values.max()) if values.size else 0.0
    if maximum <= 1e-12:
        return np.zeros_like(values)
    return values / maximum


def _build_source_rows(paths: SongPaths, stems: dict[str, str]) -> list[dict[str, str]]:
    rows = [{"id": "mix", "label": "Mix", "path": str(paths.song_path), "kind": "mix"}]
    for source_id, label in SOURCE_ORDER[1:]:
        source_path = stems.get(source_id)
        if not source_path:
            raise AnalysisError(f"Missing required stem path for loudness extraction: {source_id}")
        rows.append({"id": source_id, "label": label, "path": str(source_path), "kind": "stem"})
    return rows


def _load_audio(path: str) -> np.ndarray:
    try:
        from essentia.standard import MonoLoader
    except ImportError as exc:
        raise DependencyError("essentia is required for loudness extraction") from exc
    audio = np.asarray(MonoLoader(filename=path, sampleRate=SAMPLE_RATE)(), dtype=np.float32)
    if audio.size == 0:
        raise AnalysisError(f"No audio samples were available for loudness extraction: {path}")
    return audio


def _rms_for_window(audio: np.ndarray, start_sample: int, window_samples: int) -> float:
    if start_sample >= len(audio):
        return 0.0
    segment = audio[start_sample : start_sample + window_samples]
    if segment.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(segment, dtype=np.float64))))


def _extract_series(audio_by_source: dict[str, np.ndarray], duration_seconds: float, window_ms: int) -> tuple[list[dict], dict]:
    window_samples = max(1, int(round(SAMPLE_RATE * (window_ms / 1000.0))))
    total_frames = max(1, int(math.ceil((duration_seconds * 1000.0) / window_ms)))
    values_by_source: dict[str, np.ndarray] = {}
    for source_id, audio in audio_by_source.items():
        values_by_source[source_id] = np.asarray(
            [_rms_for_window(audio, frame_index * window_samples, window_samples) for frame_index in range(total_frames)],
            dtype=np.float64,
        )

    normalized_by_source = {source_id: _normalize(values) for source_id, values in values_by_source.items()}

    rows: list[dict] = []
    for frame_index in range(total_frames):
        start_s = round((frame_index * window_samples) / SAMPLE_RATE, 6)
        end_s = round(min(duration_seconds, ((frame_index + 1) * window_samples) / SAMPLE_RATE), 6)
        center_s = round((start_s + end_s) / 2.0, 6)
        rows.append(
            {
                "frame_index": frame_index,
                "start_s": start_s,
                "end_s": end_s,
                "time": center_s,
                "values": [round(float(values_by_source[source_id][frame_index]), 8) for source_id, _ in SOURCE_ORDER],
                "normalized_values": [round(float(normalized_by_source[source_id][frame_index]), 6) for source_id, _ in SOURCE_ORDER],
            }
        )

    metadata = {
        "sample_rate": SAMPLE_RATE,
        "window_ms": window_ms,
        "window_size": window_samples,
        "duration": round(duration_seconds, 6),
        "total_frames": total_frames,
        "normalization_scope": "per-song-per-source-peak-rms",
        "source_order": [source_id for source_id, _ in SOURCE_ORDER],
    }
    return rows, metadata


def extract_mix_stem_loudness(paths: SongPaths, stems: dict[str, str]) -> dict[str, dict]:
    sources = _build_source_rows(paths, stems)
    audio_by_source = {source["id"]: _load_audio(source["path"]) for source in sources}
    duration_seconds = len(audio_by_source["mix"]) / SAMPLE_RATE

    rms_frames, rms_metadata = _extract_series(audio_by_source, duration_seconds, RMS_INTERVAL_MS)
    rms_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": GeneratedFrom(source_song_path=str(paths.song_path), engine="essentia+numpy.rms_loudness"),
        "sources": sources,
        "frames": rms_frames,
        "metadata": rms_metadata | {"interval_ms": RMS_INTERVAL_MS},
    }
    rms_payload = to_jsonable(rms_payload)
    write_json(paths.artifact("essentia", "rms_loudness.json"), rms_payload)

    envelope_frames, envelope_metadata = _extract_series(audio_by_source, duration_seconds, ENVELOPE_WINDOW_MS)
    envelope_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": GeneratedFrom(source_song_path=str(paths.song_path), engine="essentia+numpy.loudness_envelope"),
        "sources": sources,
        "frames": envelope_frames,
        "metadata": envelope_metadata | {"window_ms": ENVELOPE_WINDOW_MS},
    }
    envelope_payload = to_jsonable(envelope_payload)
    write_json(paths.artifact("essentia", "loudness_envelope.json"), envelope_payload)

    return {
        "rms_loudness": rms_payload,
        "loudness_envelope": envelope_payload,
    }
