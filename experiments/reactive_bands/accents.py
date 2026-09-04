"""Discrete accents: instantaneous ratio spikes above its own damped twin.

The transferable core of MilkDrop's beat detection, snapped to the essentia
beat grid (measured good — CLAUDE.md) instead of re-deriving a beat estimate.
"""
from __future__ import annotations

import numpy as np


def find_accents(
    times: np.ndarray,
    ratio_inst: np.ndarray,
    ratio_att: np.ndarray,
    beats: list[dict],
    band: str,
    *,
    threshold: float = 2.0,
    min_gap_s: float = 0.15,
) -> list[dict]:
    """A local peak where ratio_inst exceeds ratio_att by `threshold` becomes
    an accent, snapped to the nearest beat. `strength` is the excess at the
    peak, useful as an `intensity` value downstream."""
    excess = ratio_inst - ratio_att
    above = excess >= threshold
    accents = []
    i = 0
    n = len(times)
    beat_times = np.array([b["time"] for b in beats]) if beats else np.array([])
    last_t = -1e9
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            peak_idx = i + int(np.argmax(excess[i:j]))
            t = float(times[peak_idx])
            if t - last_t >= min_gap_s:
                nearest_beat = None
                if len(beat_times):
                    bi = int(np.argmin(np.abs(beat_times - t)))
                    nearest_beat = beats[bi]
                accents.append({
                    "time": round(t, 3),
                    "band": band,
                    "strength": round(float(excess[peak_idx]), 4),
                    "beat": nearest_beat["beat"] if nearest_beat else None,
                    "bar": nearest_beat["bar"] if nearest_beat else None,
                    "beat_offset_s": round(t - nearest_beat["time"], 4) if nearest_beat else None,
                })
                last_t = t
            i = j
        else:
            i += 1
    return accents
