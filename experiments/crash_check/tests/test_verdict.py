from __future__ import annotations

from experiments.crash_check import verdict
from experiments.drum_hit_shape import is_stream_continuation


def _crash(cont, decay):
    return verdict.CrashFeatures(time=0.0, is_stream_continuation=cont, decay_ratio=decay)


def test_isolated_decaying_hit_is_kept():
    assert verdict.keep(_crash(cont=False, decay=0.02))


def test_stream_continuation_is_rejected_even_with_good_decay():
    assert not verdict.keep(_crash(cont=True, decay=0.02))


def test_non_decaying_hit_is_rejected_even_when_isolated():
    assert not verdict.keep(_crash(cont=False, decay=0.6))


def test_missing_decay_ratio_is_rejected():
    assert not verdict.keep(_crash(cont=False, decay=None))


def test_is_stream_continuation_matches_one_and_two_beat_multiples():
    beat = 0.462
    assert is_stream_continuation(0.0, beat, beat)
    assert is_stream_continuation(0.0, 2 * beat, beat)
    assert not is_stream_continuation(0.0, 4 * beat, beat)  # Rapture's isolated 3-hit case


def test_is_stream_continuation_first_hit_of_a_run_is_never_flagged():
    assert not is_stream_continuation(None, 10.0, 0.462)
