"""The clap shape test. Thresholds measured against `Queen of Kings -
Alessandra`'s break (see README for the full worked numbers):

  NOISE_MIN = 0.50   claps measured 0.65-0.84 (refinement's own hand-reviewed
                      range: 0.56-0.92)
  BODY_MAX  = 0.15   claps measured <=0.12; the rejected machine hit at
                      97.309 s measures 0.112 (spec: 0.28) and fails NOISE_MIN
                      (0.100 vs 0.50) regardless, so the exact BODY_MAX
                      margin does not carry that rejection alone.

A candidate is a clap iff both hold. `confidence` is the smaller of the two
thresholds' normalised margins (0 at the threshold, 1 at a perfect noise
burst) — never a display string, per CLAUDE.md.
"""
from __future__ import annotations

from experiments.drum_hit_shape import HitShape

NOISE_MIN = 0.50
BODY_MAX = 0.15


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def is_clap(shape: HitShape) -> bool:
    return shape.noise_share >= NOISE_MIN and shape.body_share <= BODY_MAX


def confidence(shape: HitShape) -> float:
    noise_margin = _clamp01((shape.noise_share - NOISE_MIN) / (1.0 - NOISE_MIN))
    body_margin = _clamp01((BODY_MAX - shape.body_share) / BODY_MAX) if BODY_MAX > 0 else 0.0
    return round(min(noise_margin, body_margin), 4)
