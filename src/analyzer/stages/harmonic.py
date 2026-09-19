from __future__ import annotations

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import GeneratedFrom, SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths


FLAT_TO_SHARP = {
    "Cb": "B",
    "Db": "C#",
    "Eb": "D#",
    "Fb": "E",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}

FRAME_SIZE = 4096
HOP_SIZE = 2048
SAMPLE_RATE = 44100


def _normalize_note_spelling(label: str) -> str:
    normalized = (label or "N").strip()
    if not normalized:
        return "N"
    for flat, sharp in FLAT_TO_SHARP.items():
        normalized = normalized.replace(flat, sharp)
    normalized = normalized.replace(":maj", "")
    normalized = normalized.replace(":min", "m")
    return normalized


def _extract_hpcp(audio: np.ndarray) -> tuple[list[np.ndarray], list[float]]:
    from essentia.standard import FrameGenerator, HPCP, Spectrum, SpectralPeaks, Windowing

    windowing = Windowing(type="hann")
    spectrum = Spectrum()
    spectral_peaks = SpectralPeaks(
        minFrequency=40,
        maxFrequency=5000,
        magnitudeThreshold=1e-5,
        maxPeaks=60,
        orderBy="magnitude",
    )
    hpcp_algorithm = HPCP(size=12, referenceFrequency=440, normalized="unitMax")

    frame_vectors: list[np.ndarray] = []
    frame_times: list[float] = []
    for frame_index, frame in enumerate(FrameGenerator(audio, frameSize=FRAME_SIZE, hopSize=HOP_SIZE, startFromZero=True)):
        spec = spectrum(windowing(frame))
        frequencies, magnitudes = spectral_peaks(spec)
        if len(frequencies) == 0:
            vector = np.zeros(12, dtype=float)
        else:
            vector = np.array(hpcp_algorithm(frequencies, magnitudes), dtype=float)
        frame_vectors.append(vector)
        frame_times.append(frame_index * HOP_SIZE / SAMPLE_RATE)

    if not frame_vectors:
        raise AnalysisError("No HPCP frames were extracted from the harmonic stem")

    return frame_vectors, frame_times


def _aggregate_hpcp_by_beat(
    frame_vectors: list[np.ndarray],
    frame_times: list[float],
    beat_times: list[float],
) -> list[dict[str, object]]:
    hpcp_by_beat = []
    for index, beat_time in enumerate(beat_times):
        next_time = beat_times[index + 1] if index + 1 < len(beat_times) else frame_times[-1] + (HOP_SIZE / SAMPLE_RATE)
        selected = [vector for frame_time, vector in zip(frame_times, frame_vectors) if beat_time <= frame_time < next_time]
        if not selected:
            nearest_index = min(range(len(frame_times)), key=lambda item: abs(frame_times[item] - beat_time))
            selected = [frame_vectors[nearest_index]]
        beat_vector = np.mean(np.vstack(selected), axis=0)
        norm = np.linalg.norm(beat_vector)
        if norm > 0:
            beat_vector = beat_vector / norm
        hpcp_by_beat.append({
            "beat": index + 1,
            "time": round(beat_time, 6),
            "vector": [round(float(value), 6) for value in beat_vector],
        })
    return hpcp_by_beat


def extract_hpcp_and_key(paths: SongPaths, stems: dict[str, str], timing: dict) -> tuple[dict, dict]:
    """HPCP chroma per beat plus the whole-song key estimate.

    Chord inference (per-beat decode, Viterbi, bass-root correction, boundary
    alignment) was removed: it failed on every song and never served its
    purpose, finding where a song repeats. Only the essentia key survives —
    a separate claim, published as `key` and gated in `ui_data.py`."""
    try:
        from essentia.standard import Key, MonoLoader
    except ImportError as exc:
        raise DependencyError("essentia is required for HPCP and key extraction") from exc

    harmonic_stem = stems["harmonic"]
    audio = MonoLoader(filename=harmonic_stem, sampleRate=SAMPLE_RATE)()
    beat_times = [beat["time"] if isinstance(beat, dict) else beat.time for beat in timing["beats"]]
    frame_vectors, frame_times = _extract_hpcp(audio)
    hpcp_by_beat = _aggregate_hpcp_by_beat(frame_vectors, frame_times, beat_times)
    aggregated_vectors = np.vstack([row["vector"] for row in hpcp_by_beat]).astype("float32")

    hpcp_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            harmonic_stem=harmonic_stem,
            beats_file=str(paths.artifact("essentia", "beats.json")),
            engine="essentia.HPCP",
        ),
        "hpcp_by_beat": hpcp_by_beat,
    }
    hpcp_payload = to_jsonable(hpcp_payload)
    write_json(paths.artifact("essentia", "hpcp.json"), hpcp_payload)

    key_label, key_scale, key_strength, _ = Key(profileType="edma", pcpSize=12)(aggregated_vectors.mean(axis=0))
    normalized_key_label = _normalize_note_spelling(key_label)

    layer_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "harmonic_stem": harmonic_stem,
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "hpcp_file": str(paths.artifact("essentia", "hpcp.json")),
            "engine": "essentia.HPCP+Key",
        },
        "global_key": {
            "label": f"{normalized_key_label} {key_scale}",
            "confidence": round(float(key_strength), 6),
            "source": "hpcp",
        },
    }
    layer_payload = to_jsonable(layer_payload)
    write_json(paths.artifact("layer_a_harmonic.json"), layer_payload)
    return hpcp_payload, layer_payload
