"""Candidate onset generation — never omnizart's events (its `snare`/`hat`
bleed already fills a sparse break with 46 false hits on one song's break
alone; see README). Two onset detectors, unioned:

- **broadband**: `librosa.onset.onset_detect` on the raw drums stem — finds
  anything loud enough to look like an attack in the full mix.
- **band-limited (1-6 kHz)**: the same detector run on a bandpass-filtered
  copy restricted to `drum_hit_shape.NOISE_BAND_HZ`. A soft clap can sit
  under a louder low-end hit in the broadband envelope but still show a
  clear onset once everything below 1 kHz is removed — this is what recovers
  `Gabry Ponte - Tutta L'Italia`'s bars 22-25 claps (see README; bars 20-21
  are the one case this still misses, and that is documented as a limitation
  rather than tuned around).

Duplicates within `MERGE_TOL_S` across the two detectors are merged (keep the
earlier time). This module only proposes *candidates* — `verdict.py` decides
which ones are shaped like a clap.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt

from experiments.drum_hit_shape import NOISE_BAND_HZ, DrumsStem

MERGE_TOL_S = 0.03
HOP_LENGTH = 256


def _broadband_onsets(stem: DrumsStem) -> np.ndarray:
    import librosa

    frames = librosa.onset.onset_detect(
        y=stem.y, sr=stem.sr, units="samples", backtrack=True, hop_length=HOP_LENGTH,
    )
    return frames / stem.sr


def _band_limited_onsets(stem: DrumsStem) -> np.ndarray:
    import librosa

    sos = butter(4, list(NOISE_BAND_HZ), btype="bandpass", fs=stem.sr, output="sos")
    y_band = sosfiltfilt(sos, stem.y)
    env = librosa.onset.onset_strength(y=y_band, sr=stem.sr, hop_length=HOP_LENGTH)
    frames = librosa.onset.onset_detect(
        onset_envelope=env, sr=stem.sr, hop_length=HOP_LENGTH, backtrack=True,
    )
    return frames * HOP_LENGTH / stem.sr


def onset_candidates(stem: DrumsStem) -> list[float]:
    times = sorted(set(_broadband_onsets(stem).tolist()) | set(_band_limited_onsets(stem).tolist()))
    merged: list[float] = []
    for t in times:
        if merged and t - merged[-1] <= MERGE_TOL_S:
            continue
        merged.append(t)
    return merged
