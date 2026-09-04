"""Raw (pre-percentile) FFT band power, local auto-gain ratios, and accents.

Frame parameters match `src/analyzer/stages/fft_bands.py` exactly (44100 Hz,
4096-sample Hann frames, 50 ms hop) so the *only* difference from the incumbent
artifact is the normalisation — the ablation this experiment exists to run.
"""
from __future__ import annotations

from dataclasses import dataclass

import librosa
import numpy as np

SAMPLE_RATE = 44100
FRAME_SIZE = 4096
HOP_SIZE = int(SAMPLE_RATE * 0.05)  # 2205 samples = 50 ms, matches the incumbent
EPS = 1e-12

BAND_DEFINITIONS: tuple[dict, ...] = (
    {"id": "sub", "start_hz": 20.0, "end_hz": 60.0},
    {"id": "bass", "start_hz": 60.0, "end_hz": 150.0},
    {"id": "low_mid", "start_hz": 150.0, "end_hz": 400.0},
    {"id": "mid", "start_hz": 400.0, "end_hz": 1000.0},
    {"id": "upper_mid", "start_hz": 1000.0, "end_hz": 2500.0},
    {"id": "presence", "start_hz": 2500.0, "end_hz": 6000.0},
    {"id": "brilliance", "start_hz": 6000.0, "end_hz": 16000.0},
)
BAND_IDS = [b["id"] for b in BAND_DEFINITIONS]

# MilkDrop's three-band collapse.
THREE_BAND_GROUPS = {
    "bass": ["sub", "bass"],
    "mid": ["low_mid", "mid"],
    "treb": ["upper_mid", "presence", "brilliance"],
}


def _band_masks(frequencies: np.ndarray) -> list[np.ndarray]:
    masks = []
    for i, band in enumerate(BAND_DEFINITIONS):
        lo, hi = band["start_hz"], band["end_hz"]
        if i == len(BAND_DEFINITIONS) - 1:
            masks.append((frequencies >= lo) & (frequencies <= hi))
        else:
            masks.append((frequencies >= lo) & (frequencies < hi))
    return masks


@dataclass
class BandPower:
    times: np.ndarray       # (F,)
    power_7: np.ndarray     # (F, 7) — (sum |magnitude| in band)^2, matches incumbent's definition
    power_3: dict           # {"bass": (F,), "mid": (F,), "treb": (F,)}


def raw_band_power(audio_path: str) -> BandPower:
    y, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
    if len(y) == 0:
        return BandPower(times=np.array([]), power_7=np.zeros((0, 7)), power_3={k: np.array([]) for k in THREE_BAND_GROUPS})

    n_frames = 1 + max(0, (len(y) - FRAME_SIZE) // HOP_SIZE)
    window = np.hanning(FRAME_SIZE)
    freqs = np.fft.rfftfreq(FRAME_SIZE, d=1.0 / SAMPLE_RATE)
    masks = _band_masks(freqs)

    power = np.zeros((n_frames, len(BAND_DEFINITIONS)))
    times = np.zeros(n_frames)
    for i in range(n_frames):
        start = i * HOP_SIZE
        frame = y[start:start + FRAME_SIZE]
        if len(frame) < FRAME_SIZE:
            frame = np.pad(frame, (0, FRAME_SIZE - len(frame)))
        spectrum = np.abs(np.fft.rfft(frame * window))
        for b, mask in enumerate(masks):
            power[i, b] = float(spectrum[mask].sum()) ** 2 if mask.any() else 0.0
        times[i] = start / SAMPLE_RATE

    power_3 = {
        name: power[:, [BAND_IDS.index(b) for b in members]].sum(axis=1)
        for name, members in THREE_BAND_GROUPS.items()
    }
    return BandPower(times=times, power_7=power, power_3=power_3)


def running_mean(x: np.ndarray, window_frames: int) -> np.ndarray:
    """Centred box-filter running mean — the local auto-gain reference level."""
    if window_frames < 1 or len(x) == 0:
        return x.copy()
    half = window_frames // 2
    padded = np.pad(x, (half, half), mode="edge")
    csum = np.cumsum(np.insert(padded, 0, 0.0))
    out = (csum[window_frames:] - csum[:-window_frames]) / float(window_frames)
    return out[: len(x)]


def ema(x: np.ndarray, alpha: float) -> np.ndarray:
    """Exponential moving average — the damped ('_att') twin of a ratio curve."""
    if len(x) == 0:
        return x.copy()
    out = np.empty_like(x, dtype=float)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def local_ratio(power: np.ndarray, window_frames: int) -> np.ndarray:
    ref = running_mean(power, window_frames)
    return power / (ref + EPS)


def percentile_ratio(power: np.ndarray) -> np.ndarray:
    """The incumbent's normalisation, expressed on the same 0..~2 ratio scale
    for a fair ablation: whole-song 5th/95th percentile of log-power, min-max
    into [0, 2] so both curves are visually and numerically comparable."""
    log_power = 10.0 * np.log10(np.maximum(power, EPS))
    lo, hi = np.percentile(log_power, 5.0), np.percentile(log_power, 95.0)
    if hi - lo < 1e-8:
        return np.zeros_like(power)
    clipped = np.clip(log_power, lo, hi)
    return 2.0 * (clipped - lo) / (hi - lo)


def frames_per_second() -> float:
    return SAMPLE_RATE / HOP_SIZE
