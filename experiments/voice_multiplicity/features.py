"""Per-song voice multiplicity features from stereo vocal stem.

Measures stereo width and L-R correlation to detect whether the vocal is a solo
or multiple stacked voices. Per-song z-scored because absolute width is NOT
comparable across songs (measured: ayuni solo reads 2.1 while Queen of Kings
chorus reads 0.77).

`compute` re-derives everything from `data/analysis/**` and writes one
`cache/<song>.json`; `score` / `export` read only that cache, so the numbers
reproduce on a checkout with no audio.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import soundfile as sf

from . import paths

HOP_S = 0.05  # 50 ms frame hop
EPS = 1e-12


def compute_and_cache(song: str) -> dict:
    """Compute voice multiplicity features and cache to JSON.

    Returns dict with keys: song, sr, hop_s, times, mid_rms, width, corr,
    present, width_z, corr_z, multiplicity.
    """
    vocals_path = paths.vocals_stem_path(song)
    if not vocals_path.exists():
        raise FileNotFoundError(f"Vocals stem not found: {vocals_path}")

    # Read stereo vocal stem
    x, sr = sf.read(str(vocals_path), dtype="float32")  # shape (n, 2)
    L, R = x[:, 0], x[:, 1]
    mid = (L + R) / 2
    side = (L - R) / 2

    # Frame parameters
    hop = int(HOP_S * sr)
    n_frames = len(mid) // hop

    # Per-frame measurements
    mid_rms = np.zeros(n_frames, dtype=np.float32)
    side_rms = np.zeros(n_frames, dtype=np.float32)
    width = np.zeros(n_frames, dtype=np.float32)
    corr = np.zeros(n_frames, dtype=np.float32)
    times = np.zeros(n_frames, dtype=np.float32)

    for i in range(n_frames):
        a = i * hop
        b = (i + 1) * hop

        # 1. RMS values
        mid_rms[i] = np.sqrt(np.mean(mid[a:b] ** 2) + EPS)
        side_rms[i] = np.sqrt(np.mean(side[a:b] ** 2) + EPS)

        # 3. Width = side_rms / mid_rms
        width[i] = side_rms[i] / (mid_rms[i] + EPS * 10)

        # 4. Pearson correlation between L and R
        L_frame = L[a:b]
        R_frame = R[a:b]
        L_var = np.var(L_frame)
        R_var = np.var(R_frame)
        if L_var > 0 and R_var > 0:
            corr[i] = np.corrcoef(L_frame, R_frame)[0, 1]
        else:
            corr[i] = 1.0
        corr[i] = np.clip(corr[i], -1.0, 1.0)

        # Time for this frame
        times[i] = i * HOP_S

    # Presence gate: p90 of mid_rms
    p90 = np.percentile(mid_rms, 90)
    present = mid_rms >= 0.10 * p90

    # Per-song z-score normalization (only on present frames)
    width_z = np.full(n_frames, np.nan, dtype=np.float32)
    corr_z = np.full(n_frames, np.nan, dtype=np.float32)
    multiplicity = np.full(n_frames, np.nan, dtype=np.float32)

    if np.any(present):
        width_mean = np.mean(width[present])
        width_std = np.std(width[present])
        corr_mean = np.mean(corr[present])
        corr_std = np.std(corr[present])

        for i in range(n_frames):
            if present[i]:
                width_z[i] = (width[i] - width_mean) / (width_std + EPS)
                corr_z[i] = (corr[i] - corr_mean) / (corr_std + EPS)
                # Multiplicity: wide AND decorrelated => more voices
                multiplicity[i] = 0.5 * width_z[i] + 0.5 * (-corr_z[i])

    # Round floats to 6dp
    times = np.round(times, 3)
    mid_rms = np.round(mid_rms, 6)
    width = np.round(width, 6)
    corr = np.round(corr, 6)
    width_z = np.round(width_z, 6)
    corr_z = np.round(corr_z, 6)
    multiplicity = np.round(multiplicity, 6)

    payload = {
        "song": song,
        "sr": int(sr),
        "hop_s": HOP_S,
        "times": [float(t) for t in times],
        "mid_rms": [float(v) for v in mid_rms],
        "width": [float(v) for v in width],
        "corr": [float(v) for v in corr],
        "present": [bool(p) for p in present],
        "width_z": [float(v) if not np.isnan(v) else None for v in width_z],
        "corr_z": [float(v) if not np.isnan(v) else None for v in corr_z],
        "multiplicity": [float(v) if not np.isnan(v) else None for v in multiplicity],
    }

    # Write to cache
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    cache_path = paths.cache_path(song)
    cache_path.write_text(json.dumps(payload) + "\n")

    return payload


def load_cache(song: str) -> dict:
    """Load cached features from JSON."""
    cache_path = paths.cache_path(song)
    with open(cache_path) as f:
        return json.load(f)
