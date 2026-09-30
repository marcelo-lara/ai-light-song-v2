"""kick keep/reject rule.

Two joint gates, both measured on `Rapture - Nadia Ali` (see README):

1. **Spectral shape** — `low_share >= LOW_MIN` (sub/low body) and
   `noise_share <= NOISE_MAX` (no 1-6 kHz noise, ruling out a hat/crash
   bleeding into the kick label).
2. **Attack** — `attack >= ATTACK_FACTOR * song_p75`, the kick register's own
   percussive-onset strength (`drum_hit_shape.attack_envelope`), relative to
   *this song's own* 75th-percentile attack strength (per-song relative
   normalisation, never an absolute constant — songs differ in mix level).
   This is what tells a genuine kick transient from a sustained sub-bass pad
   that shares the same `low_share`: on `Rapture`'s Breakdown, omnizart's
   "kick" events sit on a held pad with attack ratios of 0.8-3.0x a quiet
   pre-onset baseline; the Drop's real kicks measure 17-150x.

A hit keeps its `kick` label only if both gates pass.
"""
from __future__ import annotations

from dataclasses import dataclass

from experiments.drum_hit_shape import HitShape

LOW_MIN = 0.75
NOISE_MAX = 0.10
ATTACK_FACTOR = 0.5  # x the song's own 75th-percentile low-band attack strength


@dataclass(frozen=True)
class KickFeatures:
    time: float
    low_share: float
    noise_share: float
    attack: float
    attack_threshold: float


def keep(features: KickFeatures) -> bool:
    return (
        features.low_share >= LOW_MIN
        and features.noise_share <= NOISE_MAX
        and features.attack >= features.attack_threshold
    )
