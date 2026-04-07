from __future__ import annotations

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import EnergyBeat, EnergyFrame, GeneratedFrom, SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths


def extract_energy_features(paths: SongPaths, timing: dict) -> dict:
    try:
        from essentia.standard import FrameGenerator, MonoLoader, Spectrum, Windowing
    except ImportError as exc:
        raise DependencyError("essentia is required for energy feature extraction") from exc

    sample_rate = 44100
    frame_size = 2048
    hop_size = 512
    audio = MonoLoader(filename=str(paths.song_path), sampleRate=sample_rate)()
    windowing = Windowing(type="hann")
    spectrum = Spectrum(size=frame_size)

    raw_rows: list[dict[str, float]] = []
    previous_magnitude = None
    frequencies = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    for frame_index, frame in enumerate(FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True)):
        spec = np.asarray(spectrum(windowing(frame)), dtype=float)
        magnitude_sum = float(spec.sum())
        loudness = float(np.sqrt(np.mean(np.square(frame))))
        centroid = float((frequencies * spec).sum() / magnitude_sum) if magnitude_sum > 0 else 0.0
        normalized = spec / max(magnitude_sum, 1e-8)
        if previous_magnitude is None:
            flux = 0.0
        else:
            flux = float(np.linalg.norm(normalized - previous_magnitude))
        previous_magnitude = normalized
        onset_strength = float(max(flux, loudness))
        raw_rows.append({
            "time": frame_index * hop_size / sample_rate,
            "frame_index": frame_index,
            "loudness": loudness,
            "spectral_centroid": centroid,
            "spectral_flux": flux,
            "onset_strength": onset_strength,
        })

    if not raw_rows:
        raise AnalysisError("No energy frames were extracted from the source song")

    loudness_values = np.array([row["loudness"] for row in raw_rows], dtype=float)
    centroid_values = np.array([row["spectral_centroid"] for row in raw_rows], dtype=float)
    flux_values = np.array([row["spectral_flux"] for row in raw_rows], dtype=float)
    onset_values = np.array([row["onset_strength"] for row in raw_rows], dtype=float)

    def normalize(values: np.ndarray) -> np.ndarray:
        minimum = float(values.min())
        maximum = float(values.max())
        if maximum - minimum < 1e-8:
            return np.zeros_like(values)
        return (values - minimum) / (maximum - minimum)

    loudness_norm = normalize(loudness_values)
    centroid_norm = normalize(centroid_values)
    flux_norm = normalize(flux_values)
    onset_norm = normalize(onset_values)

    frames = [
        EnergyFrame(
            time=round(float(row["time"]), 6),
            frame_index=int(row["frame_index"]),
            loudness=round(float(loudness_norm[index]), 6),
            spectral_centroid=round(float(centroid_values[index]), 6),
            spectral_flux=round(float(flux_norm[index]), 6),
            onset_strength=round(float(onset_norm[index]), 6),
        )
        for index, row in enumerate(raw_rows)
    ]

    beat_times = [beat["time"] for beat in timing["beats"]]
    beat_rows: list[EnergyBeat] = []
    for index, beat_time in enumerate(beat_times):
        next_time = beat_times[index + 1] if index + 1 < len(beat_times) else frames[-1].time + (hop_size / sample_rate)
        selected = [frame for frame in frames if beat_time <= frame.time < next_time]
        if not selected:
            selected = [min(frames, key=lambda frame: abs(frame.time - beat_time))]
        beat_rows.append(
            EnergyBeat(
                beat=index + 1,
                time=round(float(beat_time), 6),
                loudness_avg=round(float(np.mean([frame.loudness for frame in selected])), 6),
                centroid_avg=round(float(np.mean([frame.spectral_centroid for frame in selected])), 6),
                flux_avg=round(float(np.mean([frame.spectral_flux for frame in selected])), 6),
                onset_density=round(float(np.mean([frame.onset_strength for frame in selected])), 6),
            )
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_id": paths.song_id,
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            beats_file=str(paths.artifact("essentia", "beats.json")),
            engine="essentia+numpy",
        ),
        "features": frames,
        "beat_features": beat_rows,
        "metadata": {
            "frame_rate": round(sample_rate / hop_size, 6),
            "total_frames": len(frames),
            "duration": round(float(frames[-1].time), 6),
            "normalization_scope": "per-song",
        },
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("energy_summary", "features.json"), payload)
    return payload
