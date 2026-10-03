"""v3.12 item 32 — `light-changes` stage and its two measurement stages
(`detect-kick-attacks`, `extract-harmonic-spectrum`). Ported experiment tests on synthetic
fixtures, plus the half-beat point-time refinement."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfilt, sosfiltfilt

from analyzer.paths import SongPaths
from analyzer.pipeline import STAGE_PIPELINE_IDS
from analyzer.stages import harmonic_spectrum as hs
from analyzer.stages import kick_attacks as ka
from analyzer.stages import light_changes as lc

SR = 44100
BEAT = 0.5


# ------------------------------------------------------------------ fixtures --

def bar(i, *, mix=0.05, low=0.8, high=0.5, bright=0.5, hits=(4, 2, 8), dur=2.0, entered=(), left=()):
    bands = [low, low, 0.6, 0.6, high, high, high]
    return {
        "bar": i + 1, "beat_index": i * 4, "start_s": i * 2.0, "end_s": i * 2.0 + dur, "beats_in_bar": 4,
        "irregular": False,
        "loud_rms": {"mix": mix, "bass": mix / 2, "drums": mix / 3, "harmonic": mix, "vocals": mix / 4},
        "bands": {s: list(bands) for s in ("mix", "bass", "drums", "harmonic", "vocals")},
        "brightness": bright, "transient_mean": 0.01, "transient_std": 0.02,
        "kick": hits[0], "snare": hits[1], "hat": hits[2], "vocals_cover": 1.0,
        "entered": list(entered), "left": list(left),
    }


def _jitter(n, seed=0):
    r = np.random.default_rng(seed)
    return [bar(i, mix=0.05 + r.normal(0, 0.001), bright=0.5 + r.normal(0, 0.01),
                high=0.5 + r.normal(0, 0.01), low=0.8 + r.normal(0, 0.01),
                hits=(4 + int(r.integers(0, 2)), 2, 8 + int(r.integers(0, 2)))) for i in range(n)]


def _beats(n_bars):
    return [{"time": (b * 4 + k) * BEAT, "bar": b + 1, "beat": k + 1, "type": "beat", "downbeat_confidence": None}
            for b in range(n_bars) for k in range(4)]


def _half(i, state_post):
    """One half-beat row; `state_post` selects the break state (sub gone, dark, no hits)."""
    low, high, bright, mix, hits = (0.2, 0.2, 0.2, 0.03, 0) if state_post else (0.8, 0.5, 0.5, 0.05, 1)
    bands = [low, low, 0.6, 0.6, high, high, high]
    return {"bar": i // 8 + 1, "beat": (i % 8) // 2 + 1, "half": i % 2, "start_s": i * BEAT / 2, "end_s": (i + 1) * BEAT / 2,
            "loud_rms": {"mix": mix}, "bands_mix": bands, "brightness": bright, "transient_mean": 0.01,
            "transient_std": 0.02, "kick": hits, "snare": 0, "hat": hits, "kick_attacks": hits, "kick_present": False}


def _halves(n_bars, step_row):
    return [_half(i, i >= step_row) for i in range(n_bars * 8)]


def _break_bars(n=40, at=20):
    bars = _jitter(n)
    for i in range(at, n):
        bars[i] = bar(i, mix=0.03, low=0.2, high=0.2, bright=0.2, hits=(0, 0, 2))
    return bars


def _no_sweep(n):
    return [{"median": {"hl": None}, "dropout": False} for _ in range(n)], [None] * n


# ------------------------------------------------------------ stage registry --

class RegistryTests(unittest.TestCase):
    def test_stage_ids(self):
        self.assertEqual(STAGE_PIPELINE_IDS["light-changes"], "3.3")
        self.assertEqual(STAGE_PIPELINE_IDS["detect-kick-attacks"], "2.6")
        self.assertEqual(STAGE_PIPELINE_IDS["extract-harmonic-spectrum"], "1.5")


# ---------------------------------------------------------- bar windows/means --

class BarTableTests(unittest.TestCase):
    def _b(self, spec):
        out, t = [], 0.0
        for b, n in spec:
            for k in range(n):
                out.append({"time": t, "bar": b, "beat": k + 1})
                t += 0.5
        return out

    def test_bar_windows_flag_slipped_bar_and_never_repair(self):
        bars, halves = lc.build_windows(self._b([(1, 4), (2, 4), (3, 1), (4, 4), (5, 4)]))
        self.assertEqual([b["beats_in_bar"] for b in bars], [4, 4, 1, 4, 4])
        self.assertEqual([b["irregular"] for b in bars], [False, False, True, False, False])
        self.assertEqual(bars[2]["end_s"] - bars[2]["start_s"], 0.5)
        self.assertEqual([b["beat_index"] for b in bars], [0, 4, 8, 9, 13])
        self.assertEqual(len(halves), 2 * 17)

    def test_last_window_ends_one_median_beat_after_last_beat(self):
        bars, _ = lc.build_windows(self._b([(1, 4), (2, 4)]))
        self.assertEqual(bars[-1]["end_s"], 4.0)

    def test_frame_means_window_semantics(self):
        times = np.array([0.0, 0.1, 0.2, 0.3, 0.4])
        out = lc._frame_means(times, np.array([1.0, 2.0, 3.0, 4.0, 5.0]), np.array([[0.0, 0.2], [0.2, 0.5], [9.0, 10.0]]))
        self.assertEqual(out[0], 1.5)
        self.assertEqual(out[1], 4.0)
        self.assertTrue(np.isnan(out[2]))

    def test_cover_unions_overlapping_spans(self):
        self.assertEqual(lc._cover([(0, 2), (1, 3)], 0, 4), 0.75)
        self.assertEqual(lc._cover([], 0, 4), 0.0)

    def test_kick_columns(self):
        ev = [{"time": 0.1, "confidence": 0.8, "echo_of": None}, {"time": 0.6, "confidence": 0.7, "echo_of": None}]
        self.assertEqual(ka.window_counts(ev, 0.0, 2.0, min(ka.BAR_MIN_ATTACKS, 4)), (2, True))
        self.assertEqual(ka.window_counts(ev, 0.0, 0.25, ka.HALF_MIN_ATTACKS), (1, True))
        self.assertEqual(ka.window_counts(ev, 0.0, 0.5, min(ka.BAR_MIN_ATTACKS, 1)), (1, True))


# ------------------------------------------------------------------ detector --

class DetectorTests(unittest.TestCase):
    def test_steady_song_yields_no_points(self):
        self.assertEqual(lc.detect(_jitter(40), None), [])

    def test_step_change_fires_once_then_new_state_is_not_reflagged(self):
        pts = lc.detect(_break_bars(), None)
        self.assertEqual([p["bar"] for p in pts], [21])
        self.assertIn(pts[0]["role"], ("break", "gap"))

    def test_drop_after_break_is_labelled_drop(self):
        bars = _jitter(40)
        for i in range(10, 20):
            bars[i] = bar(i, mix=0.03, low=0.1, high=0.3, bright=0.3, hits=(0, 0, 1))
        for i in range(20, 40):
            bars[i] = bar(i, mix=0.08, low=0.95, high=0.7, bright=0.6, hits=(6, 3, 10))
        pts = {p["bar"]: p for p in lc.detect(bars, None)}
        self.assertEqual(pts[21]["role"], "drop")

    def test_one_bar_gap_is_labelled_gap(self):
        bars = _jitter(30)
        bars[15] = bar(15, mix=0.01, low=0.1, high=0.1, bright=0.3, hits=(0, 0, 0))
        self.assertEqual({p["bar"]: p for p in lc.detect(bars, None)}[16]["role"], "gap")

    def test_unclaimed_change_is_unknown_not_a_guess(self):
        bars = [bar(i) for i in range(30)]
        bars[15] = {**bar(15), "entered": ["a", "b", "c", "d", "e", "f", "g"], "vocals_cover": 0.0}   # arrangement + vocals only
        for i in range(16, 30):
            bars[i] = {**bar(i), "vocals_cover": 0.0}
        pts = lc.detect(bars, None)
        self.assertEqual([(p["bar"], p["role"]) for p in pts], [(16, "unknown")])

    def test_short_window_is_merged_so_the_point_lands_where_the_slip_starts(self):
        bars = _jitter(30)
        for i in range(16, 30):
            bars[i] = bar(i, mix=0.03, low=0.2, high=0.2, bright=0.2, hits=(0, 0, 2))
        bars[16]["end_s"] = bars[16]["start_s"] + 0.5
        bars[16]["irregular"] = True
        pts = lc.detect(bars, None)
        self.assertEqual(pts[0]["bar"], 17)
        self.assertEqual(pts[0]["time_s"], bars[16]["start_s"])
        self.assertTrue(pts[0]["irregular_bar"])

    def test_texture_novelty_is_one_sided(self):
        self.assertEqual(lc.detect(_jitter(30), [0.9] * 15 + [0.0] * 15), [])


# ---------------------------------------------------------- point time (beat) --

class PointTimeTests(unittest.TestCase):
    def _points(self, step_row, n=40, at=20):
        bars = _break_bars(n, at)
        slopes, states = _no_sweep(n)
        return lc.build_points(bars, _halves(n, step_row), None, slopes, states, _beats(n))

    def test_half_beat_refinement_moves_a_point_one_beat_before_the_bar_edge(self):
        # bar index 20 starts at half-beat row 160; the break is audible from row 158 (beat 4 of the previous bar)
        edge = self._points(160)
        early = self._points(158)
        self.assertEqual([p["bar_edge_offset_beats"] for p in edge], [0])
        self.assertEqual(edge[0]["bar"], 21)
        self.assertEqual(edge[0]["time"], 80 * BEAT)
        self.assertEqual([p["bar_edge_offset_beats"] for p in early], [-1])
        self.assertEqual(early[0]["bar"], 20)
        self.assertEqual(early[0]["beat"], 4)
        self.assertEqual(early[0]["time"], 79 * BEAT)
        self.assertEqual(early[0]["bar_edge_time"], 80 * BEAT)

    def test_off_beat_onset_snaps_to_the_beat_that_contains_it(self):
        pts = self._points(159)    # the "and" of beat 4: floored to that beat, never later than the onset
        self.assertEqual(pts[0]["time"], 79 * BEAT)

    def test_point_is_always_on_a_beat_of_the_grid(self):
        times = {b["time"] for b in _beats(40)}
        for row in (156, 158, 159, 160, 161, 162, 164):
            for p in self._points(row):
                self.assertIn(p["time"], times)
                self.assertLessEqual(abs(p["bar_edge_offset_beats"]), 1)

    def test_no_halfbeat_signal_keeps_the_bar_edge(self):
        n = 40
        bars = _break_bars(n)
        slopes, states = _no_sweep(n)
        flat = [_half(i, False) for i in range(n * 8)]
        pts = lc.build_points(bars, flat, None, slopes, states, _beats(n))
        self.assertEqual([p["bar_edge_offset_beats"] for p in pts], [0])

    def test_confidence_is_null_and_role_never_invented(self):
        for p in self._points(160):
            self.assertIsNone(p["confidence"])
            self.assertIn(p["role"], lc.ROLES + ("unknown",))


# -------------------------------------------------------------------- sweeps --

def _slopes(hl, states):
    return [{"median": {"hl": v}, "dropout": False} for v in hl], states


class SweepOnsetTests(unittest.TestCase):
    def test_final_climb_start_inside_a_long_run(self):
        hl = [-8.5, -6.4, -5.2, -5.0, -4.4, -5.4, -3.2, 0.6, 0.9, 5.0]    # Armin 50..59: opening 51..58
        st = [None] + ["opening"] * 8 + [None]
        on = lc.sweep_onsets(*_slopes(hl, st))
        self.assertEqual([(o["i"], o["end_i"], o["direction"]) for o in on], [(5, 8, "opening")])
        self.assertAlmostEqual(on[0]["rise_db"], 6.3, places=2)

    def test_short_or_shallow_climb_makes_no_onset(self):
        hl = [-12.0, -11.9, -11.4, -11.8]                     # Medicine-like: the ascent ends with a fall
        self.assertEqual(lc.sweep_onsets(*_slopes(hl, ["opening"] * 4)), [])

    def test_closing_is_the_mirror(self):
        hl = [5.0, 4.0, 0.0, -4.0, -8.0]
        on = lc.sweep_onsets(*_slopes(hl, ["closing"] * 5))
        self.assertEqual([(o["i"], o["direction"]) for o in on], [(0, "closing")])

    def test_sweep_point_is_added_when_no_step_fires_and_merged_when_one_does(self):
        n = 30
        bars = _jitter(n)
        hl = [-10.0] * 10 + [-10.0, -9.0, -6.0, -3.0, 0.0] + [0.0] * 15
        st = [None] * 11 + ["opening"] * 4 + [None] * 15
        slopes, states = _slopes(hl, st)
        halves = [_half(i, False) for i in range(n * 8)]
        pts = lc.build_points(bars, halves, None, slopes, states, _beats(n))
        self.assertEqual([(p["source"], p["role"], p["bar"]) for p in pts], [("sweep", "build", 12)])
        self.assertIsNone(pts[0]["score"])
        self.assertEqual(pts[0]["sweep"]["direction"], "opening")
        # a step at the same bar absorbs the sweep point instead of duplicating it
        bars2 = _break_bars(n, 11)
        pts2 = lc.build_points(bars2, [_half(i, i >= 88) for i in range(n * 8)], None, slopes, states, _beats(n))
        self.assertEqual([p["source"] for p in pts2], ["step"])
        self.assertEqual(pts2[0]["sweep"]["direction"], "opening")


def _audio(cutoffs, level=None, bar_len=4 * BEAT):
    rng = np.random.default_rng(0)
    t = np.arange(int(bar_len * hs.SR)) / hs.SR
    parts = []
    for i, fc in enumerate(cutoffs):
        noise = sosfilt(butter(4, fc, btype="low", fs=hs.SR, output="sos"), rng.standard_normal(len(t)))
        b = 0.3 * np.sin(2 * np.pi * 150 * t) + 0.1 * noise / max(np.abs(noise).max(), 1e-9) * 3
        parts.append(b * (1.0 if level is None else level[i]))
    return np.concatenate(parts)


def _states(y, n_bars):
    beats = _beats(n_bars)
    beat_t = np.array([b["time"] for b in beats])
    times, power, centres, _ = hs.log_spectrogram(y, hs.SR)
    rows = hs.half_beat_rows(times, power, centres, beat_t)
    json_rows = [hs._json_row(r) for r in rows]
    slopes, states = lc.sweep_columns(json_rows, beats, n_bars)
    return slopes, states


class SweepStateTests(unittest.TestCase):
    def test_rising_cutoff_is_opening_and_flat_is_not(self):
        _, st = _states(_audio(list(np.geomspace(400, 9000, 12)) + [9000] * 4), 16)
        self.assertGreaterEqual(st[3:11].count("opening"), 6)
        self.assertNotIn("closing", st)
        _, flat = _states(_audio([3000] * 16), 16)
        self.assertTrue(all(s is None for s in flat))

    def test_falling_cutoff_is_closing(self):
        _, st = _states(_audio(list(np.geomspace(9000, 400, 12)) + [400] * 4), 16)
        self.assertGreaterEqual(st[3:11].count("closing"), 6)
        self.assertNotIn("opening", st)

    def test_dropout_bar_ends_the_run(self):
        cut = list(np.geomspace(400, 9000, 8)) + [9000] * 8
        sl, st = _states(_audio(cut, [1.0] * 8 + [0.02] + [1.0] * 7), 16)
        self.assertTrue(sl[8]["dropout"])
        self.assertIsNone(st[8])
        self.assertTrue(all(s is None for s in st[8:]))
        runs = lc.runs_of(st)
        self.assertTrue(runs and runs[0][2] == "opening" and runs[0][1] <= 7)

    def test_resonant_peak_found_and_sharper_than_noise(self):
        t = np.arange(hs.SR) / hs.SR
        rng = np.random.default_rng(1)
        _, p1, c1, _ = hs.log_spectrogram(rng.standard_normal(hs.SR) * 0.05 + np.sin(2 * np.pi * 1500 * t), hs.SR)
        _, p2, c2, _ = hs.log_spectrogram(rng.standard_normal(hs.SR), hs.SR)
        a = hs.window_features(p1[:, 5:30].mean(axis=1), c1)
        b = hs.window_features(p2[:, 5:30].mean(axis=1), c2)
        self.assertTrue(1200 < a["peak_hz"] < 1900 and a["sharpness"] > b["sharpness"] + 5)

    def test_mismatched_spectrum_raises(self):
        from analyzer.exceptions import AnalysisError
        with self.assertRaises(AnalysisError):
            lc.sweep_columns([], _beats(4), 4)


# --------------------------------------------------------------- kick attacks --

def _kick(amp=1.0, click=1.0, dur=0.35):
    t = np.arange(int(dur * SR)) / SR
    f = 50 + 70 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.09)
    burst = np.random.default_rng(1).standard_normal(int(0.006 * SR)) * np.hanning(int(0.006 * SR))
    burst = sosfiltfilt(butter(4, [2000, 5000], btype="bandpass", fs=SR, output="sos"), burst)
    click_sig = np.zeros_like(t)
    click_sig[:len(burst)] = burst / np.abs(burst).max()
    return amp * (body + 0.4 * click * click_sig)


def _mix(length_s, events, floor=1e-3):
    y = np.random.default_rng(0).standard_normal(int(length_s * SR)) * floor
    for t, sig in events:
        a = int(t * SR)
        y[a:a + len(sig)] += sig[: len(y) - a]
    return y


def _detect(y, beat_times, beat_len=0.5):
    return ka.detect(y, SR, np.array(beat_times), beat_len, [])


class KickAttackTests(unittest.TestCase):
    def test_synthetic_kick_fires_once_per_hit_on_the_hit(self):
        times = [0.5, 1.0, 1.5, 2.0]
        ev = _detect(_mix(3.0, [(t, _kick()) for t in times]), times)
        self.assertEqual(len(ev), 4)
        self.assertTrue(all(e["echo_of"] is None and e["on_grid"] for e in ev))
        self.assertTrue(all(abs(e["time"] - t) < 0.03 for e, t in zip(ev, times)))

    def test_sustained_bass_note_never_fires(self):
        t = np.arange(int(4 * SR)) / SR
        held = 0.5 * np.sin(2 * np.pi * 60 * t) * np.minimum(t / 0.3, 1.0)
        self.assertEqual(_detect(held + np.random.default_rng(0).standard_normal(len(t)) * 1e-3, [0.5, 1.0, 1.5, 2.0]), [])

    def test_bass_hit_without_click_is_not_a_kick(self):
        t = np.arange(int(0.4 * SR)) / SR
        note = np.sin(2 * np.pi * 55 * t) * np.exp(-t / 0.2) * np.minimum(t / 0.008, 1.0)
        self.assertEqual(_detect(_mix(3.0, [(0.5, note), (1.5, note)]), [0.5, 1.0, 1.5, 2.0]), [])

    def test_delay_echo_is_labelled_echo_not_kick(self):
        times = [0.5, 1.2, 1.9, 2.6]
        evs = [(t, _kick()) for t in times] + [(t + 0.1875, _kick(amp=0.45)) for t in times]
        ev = _detect(_mix(3.5, evs), times, beat_len=0.7)
        kicks = [e for e in ev if e["echo_of"] is None]
        echoes = [e for e in ev if e["echo_of"] is not None]
        self.assertEqual((len(kicks), len(echoes)), (4, 4))
        self.assertEqual(sorted(e["echo_of"] for e in echoes), sorted(k["time"] for k in kicks))
        self.assertTrue(all(e["confidence"] <= 0.2 for e in echoes))

    def test_off_grid_attack_kept_at_low_confidence_and_untrusted_grid_not_penalised(self):
        y = _mix(3.0, [(0.5, _kick()), (1.17, _kick())])
        ev = _detect(y, [0.5, 1.0, 1.5, 2.0])
        self.assertEqual([e["on_grid"] for e in ev], [True, False])
        self.assertLess(ev[1]["confidence"], 0.5 * ev[0]["confidence"])
        ev2 = ka.detect(y, SR, np.array([0.5, 1.0, 1.5, 2.0]), 0.5, [(0.0, 3.0)])
        self.assertTrue(all(e["grid"] == "untrusted" for e in ev2))
        self.assertGreater(ev2[1]["confidence"], ev[1]["confidence"])

    def test_window_counts_and_presence_rule(self):
        ev = [{"time": 1.0, "confidence": 0.8, "echo_of": None}, {"time": 1.5, "confidence": 0.1, "echo_of": None},
              {"time": 1.6, "confidence": 0.9, "echo_of": 1.5}, {"time": 2.98, "confidence": 0.7, "echo_of": None}]
        self.assertEqual(ka.window_counts(ev, 0.9, 2.0, 2), (2, False))
        self.assertEqual(ka.window_counts(ev, 0.9, 2.0, 1), (2, True))
        self.assertEqual(ka.window_counts(ev, 3.0, 3.5, 1), (1, True))


# ------------------------------------------------------------- stage, on disk --

class StageOnDiskTests(unittest.TestCase):
    def test_missing_inputs_raise_and_nothing_is_written(self):
        from analyzer.exceptions import AnalysisError
        with tempfile.TemporaryDirectory() as tmp:
            paths = SongPaths(song_path=Path(tmp) / "s.mp3", analysis_root=Path(tmp) / "analysis")
            with self.assertRaises(AnalysisError):
                lc.build_light_changes(paths)
            self.assertFalse(paths.artifact("light_changes", "light_changes.json").exists())


if __name__ == "__main__":
    unittest.main()
