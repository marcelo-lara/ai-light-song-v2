from __future__ import annotations

from experiments.kick_check import verdict


def _kick(low, noise, attack, threshold=0.05):
    return verdict.KickFeatures(time=0.0, low_share=low, noise_share=noise,
                                 attack=attack, attack_threshold=threshold)


def test_real_drop_kick_is_kept():
    # measured shape: low ~0.99, noise ~0, attack ratio 17-150x baseline
    assert verdict.keep(_kick(low=0.99, noise=0.0002, attack=1.0, threshold=0.05))


def test_sustained_pad_with_kick_shape_but_no_attack_is_rejected():
    # measured on Rapture's Breakdown: low_share high, noise low, but attack
    # ratio 0.8-3.0x — below any reasonable song-relative baseline
    assert not verdict.keep(_kick(low=0.97, noise=0.01, attack=0.02, threshold=0.05))


def test_hat_or_crash_bleed_is_rejected_on_noise_alone():
    assert not verdict.keep(_kick(low=0.9, noise=0.6, attack=1.0, threshold=0.05))


def test_weak_low_share_is_rejected():
    assert not verdict.keep(_kick(low=0.2, noise=0.02, attack=1.0, threshold=0.05))
