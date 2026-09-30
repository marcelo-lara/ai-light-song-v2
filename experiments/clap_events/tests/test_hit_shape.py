"""Unit tests for the shared `drum_hit_shape.hit_shape` band math, using a
synthetic drums stem — no audio fixture needed."""
from __future__ import annotations

import numpy as np

from experiments.drum_hit_shape import DrumsStem, hit_shape


def _tone_stem(freq_hz: float, sr: int = 44100, seconds: float = 0.5) -> DrumsStem:
    t = np.arange(int(sr * seconds)) / sr
    y = np.sin(2 * np.pi * freq_hz * t)
    return DrumsStem(song="synthetic", y=y, sr=sr)


def test_pure_tone_in_noise_band_reads_high_noise_share():
    stem = _tone_stem(3000.0)
    shape = hit_shape(stem, 0.0)
    assert shape is not None
    assert shape.noise_share > 0.9
    assert shape.body_share < 0.05


def test_pure_tone_in_body_band_reads_high_body_share():
    stem = _tone_stem(250.0)
    shape = hit_shape(stem, 0.0)
    assert shape is not None
    assert shape.body_share > 0.9
    assert shape.noise_share < 0.05


def test_pure_tone_in_low_band_reads_high_low_share():
    stem = _tone_stem(60.0)
    shape = hit_shape(stem, 0.0)
    assert shape is not None
    assert shape.low_share > 0.9


def test_window_past_end_of_stem_returns_none():
    stem = _tone_stem(100.0, seconds=0.05)
    assert hit_shape(stem, 0.0) is None
