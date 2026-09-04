"""Compute-and-cache glue: raw band power per song/source, then ratio curves."""
from __future__ import annotations

import numpy as np

from . import bands, paths

WINDOW_CANDIDATES_S = (1.0, 2.0, 4.0, 8.0)  # "bar-length" resolved per-song in score.py
DEFAULT_WINDOW_S = 2.0
DEFAULT_DAMPING_TAU_S = 1.0  # EMA time-constant for the "_att" twin


def compute_and_cache(song: str, source: str) -> bands.BandPower:
    audio_path = paths.source_audio_path(song, source)
    bp = bands.raw_band_power(str(audio_path))
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    np.savez(
        paths.cache_path(song, source),
        times=bp.times,
        power_7=bp.power_7,
        **{f"power3_{k}": v for k, v in bp.power_3.items()},
    )
    return bp


def load_cache(song: str, source: str) -> bands.BandPower:
    data = np.load(paths.cache_path(song, source))
    power_3 = {k: data[f"power3_{k}"] for k in bands.THREE_BAND_GROUPS}
    return bands.BandPower(times=data["times"], power_7=data["power_7"], power_3=power_3)


def window_to_frames(window_s: float) -> int:
    fps = bands.frames_per_second()
    n = int(round(window_s * fps))
    return n + 1 if n % 2 == 0 else n


def ema_alpha_for_tau(tau_s: float) -> float:
    fps = bands.frames_per_second()
    # alpha such that the EMA's -3dB point is roughly at tau seconds.
    return 1.0 - np.exp(-1.0 / (tau_s * fps))


def ratios_for_band(power: np.ndarray, window_s: float = DEFAULT_WINDOW_S, tau_s: float = DEFAULT_DAMPING_TAU_S) -> tuple[np.ndarray, np.ndarray]:
    inst = bands.local_ratio(power, window_to_frames(window_s))
    att = bands.ema(inst, ema_alpha_for_tau(tau_s))
    return inst, att
