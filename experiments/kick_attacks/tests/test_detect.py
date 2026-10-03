import numpy as np

from experiments.kick_attacks import detect, present

SR = 44100


def _kick(amp=1.0, click=1.0, dur=0.35):
    t = np.arange(int(dur * SR)) / SR
    f = 50 + 70 * np.exp(-t / 0.03)                       # 120 -> 50 Hz drop
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.09)
    rng = np.random.default_rng(1)
    click_sig = np.zeros_like(t)
    n = int(0.006 * SR)
    burst = rng.standard_normal(n) * np.hanning(n)
    from scipy.signal import butter, sosfiltfilt
    burst = sosfiltfilt(butter(4, [2000, 5000], btype="bandpass", fs=SR, output="sos"), burst)
    click_sig[:n] = burst / np.abs(burst).max()
    return amp * (body + 0.4 * click * click_sig)


def _mix(length_s, events, floor=1e-3):
    y = np.random.default_rng(0).standard_normal(int(length_s * SR)) * floor
    for t, sig in events:
        a = int(t * SR)
        y[a:a + len(sig)] += sig[: len(y) - a]
    return y


def _detect(y, beat_times, beat_len=0.5):
    return detect.detect(y, SR, np.array(beat_times), beat_len, [])


def test_synthetic_kick_fires_once_per_hit_on_the_hit():
    times = [0.5, 1.0, 1.5, 2.0]
    y = _mix(3.0, [(t, _kick()) for t in times])
    ev = _detect(y, times)
    assert len(ev) == 4
    assert all(e["echo_of"] is None and e["on_grid"] for e in ev)
    assert all(abs(e["time"] - t) < 0.03 for e, t in zip(ev, times))


def test_sustained_bass_note_never_fires():
    t = np.arange(int(4 * SR)) / SR
    held = 0.5 * np.sin(2 * np.pi * 60 * t) * np.minimum(t / 0.3, 1.0)   # 300 ms fade-in, then held
    y = held + np.random.default_rng(0).standard_normal(len(t)) * 1e-3
    assert _detect(y, [0.5, 1.0, 1.5, 2.0]) == []


def test_bass_hit_without_click_is_not_a_kick():
    t = np.arange(int(0.4 * SR)) / SR
    note = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.2) * np.minimum(t / 0.008, 1.0)  # steep low rise (8 ms ramp), no click, no pitch drop
    y = _mix(3.0, [(0.5, note), (1.5, note)])
    assert _detect(y, [0.5, 1.0, 1.5, 2.0]) == []


def test_delay_echo_is_labelled_echo_not_kick():
    times = [0.5, 1.2, 1.9, 2.6]
    delay = 0.1875
    evs = [(t, _kick()) for t in times] + [(t + delay, _kick(amp=0.45)) for t in times]
    y = _mix(3.5, evs)
    ev = _detect(y, times, beat_len=0.7)
    kicks = [e for e in ev if e["echo_of"] is None]
    echoes = [e for e in ev if e["echo_of"] is not None]
    assert len(kicks) == 4 and len(echoes) == 4
    assert sorted(e["echo_of"] for e in echoes) == sorted(k["time"] for k in kicks)
    assert all(e["confidence"] <= 0.2 for e in echoes)


def test_off_grid_attack_is_kept_at_low_confidence_and_untrusted_grid_is_not_penalised():
    y = _mix(3.0, [(0.5, _kick()), (1.0 + 0.17, _kick())])                # 0.34 beat off the beat
    ev = _detect(y, [0.5, 1.0, 1.5, 2.0])
    assert len(ev) == 2 and [e["on_grid"] for e in ev] == [True, False]
    assert ev[1]["confidence"] < 0.5 * ev[0]["confidence"]
    ev2 = detect.detect(y, SR, np.array([0.5, 1.0, 1.5, 2.0]), 0.5, [(0.0, 3.0)])
    assert all(e["grid"] == "untrusted" for e in ev2)
    assert ev2[1]["confidence"] > ev[1]["confidence"]


def test_window_counts_and_presence_rule():
    ev = [{"time": 1.0, "confidence": 0.8, "echo_of": None},
          {"time": 1.5, "confidence": 0.1, "echo_of": None},
          {"time": 1.6, "confidence": 0.9, "echo_of": 1.5},
          {"time": 2.98, "confidence": 0.7, "echo_of": None}]               # 20 ms early for the beat at 3.0
    assert present.window_counts(ev, 0.9, 2.0, 2) == (2, False)             # echo excluded; one confident only
    assert present.window_counts(ev, 0.9, 2.0, 1) == (2, True)
    assert present.window_counts(ev, 3.0, 3.5, 1) == (1, True)              # early onset binned with its beat
