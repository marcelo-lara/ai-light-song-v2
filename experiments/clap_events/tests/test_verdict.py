from __future__ import annotations

from experiments.drum_hit_shape import HitShape
from experiments.clap_events import verdict


def _shape(noise, body):
    return HitShape(time=0.0, noise_share=noise, body_share=body, low_share=0.0, bright_share=0.0)


def test_queen_of_kings_break_clap_is_a_clap():
    assert verdict.is_clap(_shape(0.73, 0.0002))


def test_rejected_machine_hit_is_not_a_clap():
    # measured on Queen of Kings 97.309s: noise 0.100 fails NOISE_MIN outright
    assert not verdict.is_clap(_shape(0.100, 0.112))


def test_drop_backbeat_is_not_a_clap():
    assert not verdict.is_clap(_shape(0.02, 0.25))


def test_high_noise_high_body_is_not_a_clap():
    # noise alone is not sufficient — body must also be low
    assert not verdict.is_clap(_shape(0.80, 0.30))


def test_confidence_is_zero_at_threshold():
    assert verdict.confidence(_shape(verdict.NOISE_MIN, verdict.BODY_MAX)) == 0.0


def test_confidence_is_high_for_a_clean_clap():
    assert verdict.confidence(_shape(0.90, 0.0)) > 0.7
