from __future__ import annotations

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import GeneratedFrom, SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths


BAND_DEFINITIONS: tuple[dict[str, float | str], ...] = (
    {"id": "sub", "label": "Sub", "start_hz": 20.0, "end_hz": 60.0},
    {"id": "bass", "label": "Bass", "start_hz": 60.0, "end_hz": 150.0},
    {"id": "low_mid", "label": "Low Mid", "start_hz": 150.0, "end_hz": 400.0},
    {"id": "mid", "label": "Mid", "start_hz": 400.0, "end_hz": 1000.0},
    {"id": "upper_mid", "label": "Upper Mid", "start_hz": 1000.0, "end_hz": 2500.0},
    {"id": "presence", "label": "Presence", "start_hz": 2500.0, "end_hz": 6000.0},
    {"id": "brilliance", "label": "Brilliance", "start_hz": 6000.0, "end_hz": 16000.0},
)

EPSILON = 1e-12
LOW_PERCENTILE = 5.0
HIGH_PERCENTILE = 95.0
HIGH_BAND_IDS = {"upper_mid", "presence", "brilliance"}


def _normalize(values: np.ndarray) -> np.ndarray:
    minimum = float(values.min())
    maximum = float(values.max())
    if maximum - minimum < 1e-8:
        return np.zeros_like(values)
    return (values - minimum) / (maximum - minimum)


def _robust_normalize(values: np.ndarray, *, low_percentile: float = LOW_PERCENTILE, high_percentile: float = HIGH_PERCENTILE) -> np.ndarray:
    lower = float(np.percentile(values, low_percentile))
    upper = float(np.percentile(values, high_percentile))
    if upper - lower < 1e-8:
        return np.zeros_like(values)
    clipped = np.clip(values, lower, upper)
    return (clipped - lower) / (upper - lower)


def _build_band_masks(frequencies: np.ndarray) -> list[np.ndarray]:
    masks: list[np.ndarray] = []
    for index, band in enumerate(BAND_DEFINITIONS):
        start_hz = float(band["start_hz"])
        end_hz = float(band["end_hz"])
        if index == len(BAND_DEFINITIONS) - 1:
            mask = (frequencies >= start_hz) & (frequencies <= end_hz)
        else:
            mask = (frequencies >= start_hz) & (frequencies < end_hz)
        masks.append(mask)
    return masks


def _normalized_deltas(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    deltas = np.diff(values, prepend=values[0])
    rising = np.clip(deltas, 0.0, None)
    falling = np.clip(-deltas, 0.0, None)
    return _normalize(rising), _normalize(falling)


def extract_fft_bands(paths: SongPaths) -> dict:
    try:
        from essentia.standard import FrameGenerator, MonoLoader, Spectrum, Windowing
    except ImportError as exc:
        raise DependencyError("essentia is required for FFT band extraction") from exc

    sample_rate = 44100
    frame_size = 4096
    hop_size = int(sample_rate * 0.05)
    interval_ms = 50
    audio = MonoLoader(filename=str(paths.song_path), sampleRate=sample_rate)()
    if len(audio) == 0:
        raise AnalysisError("No audio samples were available for FFT band extraction")

    windowing = Windowing(type="hann")
    spectrum = Spectrum(size=frame_size)
    frequencies = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    band_masks = _build_band_masks(frequencies)
    high_band_indices = [index for index, band in enumerate(BAND_DEFINITIONS) if str(band["id"]) in HIGH_BAND_IDS]

    raw_levels: list[list[float]] = []
    for frame in FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True):
        magnitude = np.asarray(spectrum(windowing(frame)), dtype=float)
        raw_levels.append([float(magnitude[mask].sum()) if np.any(mask) else 0.0 for mask in band_masks])

    if not raw_levels:
        raise AnalysisError("No FFT band frames were extracted from the source song")

    raw_matrix = np.asarray(raw_levels, dtype=float)
    # Use power-domain energy to improve stability under broadband loudness swings.
    power_matrix = np.maximum(raw_matrix, 0.0) ** 2
    log_power_matrix = 10.0 * np.log10(np.maximum(power_matrix, EPSILON))
    normalized_matrix = np.column_stack([
        _robust_normalize(log_power_matrix[:, index])
        for index in range(log_power_matrix.shape[1])
    ])

    total_power = np.sum(power_matrix, axis=1)
    high_band_power = np.sum(power_matrix[:, high_band_indices], axis=1) if high_band_indices else np.zeros_like(total_power)
    brightness_ratio = np.where(total_power > EPSILON, high_band_power / total_power, 0.0)
    transient_strength, dropout_strength = _normalized_deltas(total_power)

    frames = [
        {
            "frame_index": frame_index,
            "time": round((frame_index * hop_size) / sample_rate, 6),
            "levels": [round(float(level), 6) for level in normalized_matrix[frame_index].tolist()],
            "brightness_ratio": round(float(brightness_ratio[frame_index]), 6),
            "transient_strength": round(float(transient_strength[frame_index]), 6),
            "dropout_strength": round(float(dropout_strength[frame_index]), 6),
        }
        for frame_index in range(normalized_matrix.shape[0])
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": GeneratedFrom(source_song_path=str(paths.song_path), engine="essentia+numpy.fft_bands"),
        "bands": [dict(band) for band in BAND_DEFINITIONS],
        "frames": frames,
        "metadata": {
            "interval_ms": interval_ms,
            "sample_rate": sample_rate,
            "frame_size": frame_size,
            "hop_size": hop_size,
            "window": "hann",
            "total_frames": len(frames),
            "duration": round(len(audio) / sample_rate, 6),
            "normalization_scope": "per-song-per-band-log-power-percentile",
            "normalization_percentiles": [LOW_PERCENTILE, HIGH_PERCENTILE],
            "derived_frame_fields": ["brightness_ratio", "transient_strength", "dropout_strength"],
        },
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("essentia", "fft_bands.json"), payload)
    return payload