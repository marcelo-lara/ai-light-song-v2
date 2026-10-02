from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

import numpy as np

from analyzer.io import read_json
from analyzer.paths import SongPaths
from analyzer.stages import gestures
from analyzer.stages.gestures import (
    PHASE_NAMES,
    assemble_gestures,
    build_gestures,
    detect_impacts,
    detect_pre_drop_gaps,
    detect_ramps,
    detect_reverse_cymbal,
    detect_section_transitions,
    detect_snare_roll,
    detect_stem_entry_impacts,
    _drum_hit_indices,
)

# Retired Epic-5 boilerplate strings that must never leak into a projected
# `summary` (plan v3.0 item 9 checklist item 5).
_FORBIDDEN_BOILERPLATE = (
    "Arrangement appears to gain material at this beat.",
    "Arrangement appears to strip back at this beat.",
    "Breakdown candidates are merged across adjacent negative-delta beats.",
)


def _beats(n_bars: int, bar_len: float = 2.0, beats_per_bar: int = 4) -> list[dict]:
    beats: list[dict] = []
    index = 1
    for bar in range(1, n_bars + 1):
        for beat_in_bar in range(1, beats_per_bar + 1):
            time = (bar - 1) * bar_len + (beat_in_bar - 1) * (bar_len / beats_per_bar)
            beats.append({
                "index": index,
                "time": round(time, 6),
                "bar": bar,
                "beat_in_bar": beat_in_bar,
                "type": "downbeat" if beat_in_bar == 1 else "beat",
                "confidence": None,
            })
            index += 1
    return beats


class NoAudioReadTests(unittest.TestCase):
    """Phase 3 ("relate") never opens the audio."""

    def test_module_imports_no_audio_libraries(self) -> None:
        source = Path(gestures.__file__).read_text()
        tree = ast.parse(source)
        forbidden = {"librosa", "soundfile", "audioread", "essentia", "pydub"}
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & forbidden, f"gestures.py must not import audio libraries, found {imported & forbidden}")

    def test_song_path_used_only_for_provenance_strings(self) -> None:
        source = Path(gestures.__file__).read_text()
        # `paths.song_path` may only ever be wrapped in `str(...)` for the
        # generated_from block -- never opened, read, or passed to a decoder.
        for line in source.splitlines():
            if "song_path" in line and "paths.song_path" in line:
                self.assertIn("str(paths.song_path)", line)


class DetectRampsTests(unittest.TestCase):
    def test_detects_a_rising_riser(self) -> None:
        times = np.arange(0.0, 20.0, 0.1)
        levels = np.zeros((len(times), 7))
        # High bands ramp from 0.1 to 0.9 across the whole span.
        ramp = np.linspace(0.1, 0.9, len(times))
        for idx in (4, 5, 6):
            levels[:, idx] = ramp
        beats = _beats(n_bars=10, bar_len=2.0)
        risers = detect_ramps(levels, times, beats, kind="riser")
        self.assertTrue(risers, "expected at least one riser candidate")
        for r in risers:
            self.assertEqual(r["type"], "riser")
            self.assertGreater(r["confidence"], 0.0)
            self.assertGreaterEqual(r["intensity"], 0.0)
            self.assertLessEqual(r["intensity"], 1.0)

    def test_flat_energy_detects_no_riser(self) -> None:
        times = np.arange(0.0, 20.0, 0.1)
        levels = np.full((len(times), 7), 0.3)
        beats = _beats(n_bars=10, bar_len=2.0)
        self.assertEqual(detect_ramps(levels, times, beats, kind="riser"), [])


class DetectImpactsTests(unittest.TestCase):
    def test_detects_simultaneous_sub_and_transient_spike(self) -> None:
        times = np.arange(0.0, 10.0, 0.05)
        levels = np.full((len(times), 7), 0.2)
        transient = np.zeros(len(times))
        impact_index = len(times) // 2
        levels[impact_index - 1 : impact_index + 2, 0] = 0.95  # sub band spike
        transient[impact_index] = 1.0
        beats = _beats(n_bars=10, bar_len=1.0)
        impacts = detect_impacts(levels, times, transient, beats)
        self.assertEqual(len(impacts), 1)
        self.assertAlmostEqual(impacts[0]["start"], float(times[impact_index]), places=2)
        self.assertGreater(impacts[0]["confidence"], 0.0)

    def test_slow_rise_transient_starts_before_its_peak(self) -> None:
        """v3.9 item 4 -- `start` is the onset (walked back from the peak
        while the transient stays above its own threshold), never the peak
        itself; `peak_time` keeps the old instant."""
        times = np.arange(0.0, 10.0, 0.05)
        levels = np.full((len(times), 7), 0.2)
        transient = np.zeros(len(times))
        peak_index = len(times) // 2
        # A ramp into the peak: five frames rising from 0.1 to 1.0, all
        # strictly above the song's ~0 threshold (almost every other frame is
        # exactly zero), so the walk-back should cross every one of them.
        ramp = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
        for offset, value in enumerate(ramp):
            transient[peak_index - len(ramp) + 1 + offset] = value
        levels[peak_index - 3 : peak_index + 3, 0] = 0.95  # sub band spike
        beats = _beats(n_bars=10, bar_len=1.0)
        impacts = detect_impacts(levels, times, transient, beats)
        self.assertEqual(len(impacts), 1)
        impact = impacts[0]
        self.assertAlmostEqual(impact["peak_time"], float(times[peak_index]), places=2)
        self.assertLess(impact["start"], impact["peak_time"])
        # The walk-back found the ramp's own first (lowest) frame.
        self.assertAlmostEqual(impact["start"], float(times[peak_index - len(ramp) + 1]), places=2)

    def test_transient_without_sub_energy_is_not_an_impact(self) -> None:
        times = np.arange(0.0, 10.0, 0.05)
        levels = np.full((len(times), 7), 0.2)
        # Sub band is elevated everywhere EXCEPT right at the transient, so the
        # song's own 70th-percentile threshold is not cleared there.
        levels[:, 0] = 0.9
        impact_index = len(times) // 2
        levels[impact_index - 2 : impact_index + 3, 0] = 0.05
        transient = np.zeros(len(times))
        transient[impact_index] = 1.0
        beats = _beats(n_bars=10, bar_len=1.0)
        self.assertEqual(detect_impacts(levels, times, transient, beats), [])


def _rms_loudness(bass: np.ndarray, drums: np.ndarray, dt: float = 0.01) -> dict:
    times = np.arange(len(bass)) * dt
    return {
        "sources": [{"id": "bass"}, {"id": "drums"}],
        "frames": [
            {"time": round(float(t), 6), "values": [float(b), float(d)]}
            for t, b, d in zip(times, bass, drums)
        ],
    }


class DetectStemEntryImpactsTests(unittest.TestCase):
    """v3.9 item 4 -- a published section boundary where bass+drums both
    enter gets its own impact, even without a supporting transient."""

    def test_simultaneous_stem_entry_at_boundary_with_no_transient_impact(self) -> None:
        n = 2000  # 20s at 10ms frames
        bass = np.where(np.arange(n) * 0.01 < 10.0, 0.01, 1.0)
        drums = bass.copy()
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)  # beat_len 0.5s, bar_len 2.0s
        sections = [{"start": 0.0}, {"start": 10.0}]
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [])
        self.assertEqual(len(impacts), 1)
        self.assertAlmostEqual(impacts[0]["start"], 10.0, delta=0.1)
        self.assertEqual(impacts[0]["type"], "impact")
        self.assertIn("stem entry", impacts[0]["evidence"])

    def test_existing_impact_nearby_is_corrected_not_duplicated(self) -> None:
        n = 2000
        bass = np.where(np.arange(n) * 0.01 < 10.0, 0.01, 1.0)
        drums = bass.copy()
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        sections = [{"start": 0.0}, {"start": 10.0}]
        # A transient-detector impact placed 0.15s late (within the dedup
        # floor of the boundary, so it counts as "already covers this drop"
        # -- but beyond the correction epsilon of the true onset), so the
        # more precisely anchored stem onset corrects it in place rather than
        # adding a second impact for the same event.
        stale = {"start": 10.15, "end": 10.15, "confidence": 0.5, "intensity": 0.5, "evidence": "transient=0.2"}
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [stale])
        self.assertEqual(impacts, [])
        self.assertAlmostEqual(stale["start"], 10.0, delta=0.1)
        self.assertEqual(stale["peak_time"], 10.15)

    def test_existing_impact_within_dedup_floor_is_left_alone(self) -> None:
        n = 2000
        bass = np.where(np.arange(n) * 0.01 < 10.0, 0.01, 1.0)
        drums = bass.copy()
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        sections = [{"start": 0.0}, {"start": 10.0}]
        already_right = {"start": 10.02, "end": 10.02, "confidence": 0.9, "intensity": 0.9, "evidence": "transient=0.9"}
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [already_right])
        self.assertEqual(impacts, [])
        self.assertEqual(already_right["start"], 10.02)
        self.assertNotIn("peak_time", already_right)

    def test_pickup_with_a_recovering_trough_is_not_moved(self) -> None:
        """v3.9 item 4 follow-up -- "stems entered first" is not enough on
        its own: a bass pickup + drum-fill hit ahead of the real downbeat
        (Queen of Kings' 48.555s before its operator-reviewed 48.70s drop)
        also clears the sustain check. Distinguish it by shape: the raw
        drums value dips to a real trough between the pickup and the
        existing impact, then climbs back up again -- a separate, later hit
        -- so the existing impact must be left untouched."""
        n = 2000
        t = np.arange(n) * 0.01
        bass = np.where(t < 10.0, 0.01, 1.0)
        # Pickup (0.6, onset) -> a trough well below 60% of it (0.2) -> the
        # real, later hit (1.0) the existing impact already sits on.
        drums = np.where(t < 10.0, 0.01, np.where(t < 10.1, 0.6, np.where(t < 10.15, 0.2, 1.0)))
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        sections = [{"start": 0.0}, {"start": 10.0}]
        existing = {"start": 10.2, "end": 10.2, "confidence": 0.9, "intensity": 0.9, "evidence": "transient=0.9"}
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [existing])
        self.assertEqual(impacts, [])
        self.assertEqual(existing["start"], 10.2)
        self.assertNotIn("peak_time", existing)

    def test_monotonic_attack_with_no_trough_is_moved(self) -> None:
        """v3.9 item 4 follow-up, the Rapture-shaped counterpart -- an onset
        below its own hit's peak (a normal attack envelope, not a separate
        pickup) never dips into a real trough on the way there, so the
        existing impact IS corrected to it."""
        n = 2000
        t = np.arange(n) * 0.01
        bass = np.where(t < 10.0, 0.01, 1.0)
        # Onset at 0.51, easing up to its own hit's plateau at 0.9 -- never
        # dips below 60% of the onset value on the way.
        drums = np.where(t < 10.0, 0.01, np.where(t < 10.05, 0.51, 0.9))
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        sections = [{"start": 0.0}, {"start": 10.0}]
        existing = {"start": 10.15, "end": 10.15, "confidence": 0.9, "intensity": 0.9, "evidence": "transient=0.9"}
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [existing])
        self.assertEqual(impacts, [])
        self.assertAlmostEqual(existing["start"], 10.0, delta=0.05)
        self.assertEqual(existing["peak_time"], 10.15)

    def test_onset_too_far_from_its_own_boundary_emits_nothing(self) -> None:
        """v3.9 item 4 follow-up -- an onset does not belong to a boundary
        just because that boundary's search window happened to reach it
        (Queen of Kings' 48.555s onset, searched from the 46.82s boundary
        1.735s away, really belongs to the 48.72s boundary 0.165s away).
        Here the found onset is over a bar from its boundary -- emit
        nothing, never attribute it here."""
        n = 2000
        t = np.arange(n) * 0.01
        # A weak-but-real crossing plateau just inside the boundary's own
        # +-1-bar search window, then a dip, then the actual hit -- more
        # than a bar past the boundary.
        bass = np.where(t < 10.3, 0.01, np.where(t < 11.7, 0.5, np.where(t < 12.4, 0.05, 1.0)))
        drums = np.where(t < 10.3, 0.01, np.where(t < 11.7, 0.5, np.where(t < 12.4, 0.05, 1.0)))
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)  # bar_len 2.0s; onset ~12.4 is 2.4s past the boundary
        sections = [{"start": 0.0}, {"start": 10.0}]
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [])
        self.assertEqual(impacts, [])

    def test_two_overlapping_boundaries_do_not_duplicate_one_hit(self) -> None:
        """v3.9 item 4 follow-up -- bar-spaced boundaries have overlapping
        +-1-bar search windows, so more than one can independently
        rediscover the same real hit. The dedup floor applies against EVERY
        existing impact, not only ones near the boundary being processed:
        the earlier boundary's own scan must not add a duplicate for a hit
        an existing impact (destined to be corrected by the later boundary)
        already covers."""
        n = 2500
        t = np.arange(n) * 0.01
        bass = np.where(t < 11.85, 0.01, 1.0)
        drums = np.where(t < 11.85, 0.01, 1.0)
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        sections = [{"start": 0.0}, {"start": 10.0}, {"start": 11.9}]
        existing = {"start": 11.95, "end": 11.95, "confidence": 0.9, "intensity": 0.9, "evidence": "transient=0.9"}
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [existing])
        self.assertEqual(impacts, [])
        self.assertAlmostEqual(existing["start"], 11.85, delta=0.05)

    def _sparse_kick_drums(self, n: int, first_kick: float, last_kick: float, beat_len: float = 0.5) -> np.ndarray:
        """One 50 ms kick per beat from `first_kick` to `last_kick`, near
        silence between (the Charli-VonDutch shape)."""
        t = np.arange(n) * 0.01
        drums = np.full(n, 0.005)
        k = first_kick
        while k <= last_kick:
            drums[(t >= k) & (t < k + 0.05)] = 1.0
            k += beat_len
        return drums

    def test_sparse_short_kicks_one_per_beat_are_present(self) -> None:
        """v3.10 item 3 -- ~50 ms kicks one per beat are drums presence:
        every kick is a hit, and a 1-beat rolling mean of them stays below
        the 0.40x on-threshold that used to gate them out."""
        n = 3000
        drums = self._sparse_kick_drums(n, 10.0, 28.0)
        p95 = float(np.percentile(drums, 95))
        hits = _drum_hit_indices(drums, gestures._DRUMS_LED_HIT_RATIO * p95, min_gap=12)
        hit_times = hits * 0.01
        self.assertEqual(len(hits), 37)
        self.assertTrue(np.all(np.abs(np.diff(hit_times) - 0.5) < 0.02))
        smooth = gestures._centered_moving_average(drums, 50)
        self.assertLess(float(smooth[1500]), gestures._STEM_ENTRY_ON_RATIO * p95)

    def test_drums_led_entry_with_bass_one_beat_late_gives_one_impact_at_the_drums_onset(self) -> None:
        n = 3000
        t = np.arange(n) * 0.01
        drums = self._sparse_kick_drums(n, 10.0, 28.0)
        bass = np.where(t < 10.5, 0.005, 1.0)  # a beat after the first kick
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        sections = [{"start": 0.0}, {"start": 9.9}]
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [])
        self.assertEqual(len(impacts), 1)
        self.assertAlmostEqual(impacts[0]["start"], 10.0, delta=0.03)
        self.assertIn("drums-led", impacts[0]["evidence"])
        self.assertEqual(impacts[0]["confidence"], gestures._DRUMS_LED_FALLBACK_CONFIDENCE)

    def test_pickup_hit_then_trough_then_groove_gives_one_impact_at_the_groove(self) -> None:
        """A lone pickup, a 3-beat trough, then the real groove: the pickup
        must not borrow the groove's hits for its density."""
        n = 3000
        t = np.arange(n) * 0.01
        drums = self._sparse_kick_drums(n, 11.5, 28.0)  # groove from 11.5s
        drums[(t >= 10.0) & (t < 10.05)] = 1.0  # pickup 1.5s (3 beats) earlier
        bass = np.where(t < 12.0, 0.005, 1.0)  # a beat after the groove
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        impacts = detect_stem_entry_impacts(rms_loudness, beats, [{"start": 0.0}, {"start": 11.4}], [])
        self.assertEqual(len(impacts), 1)
        self.assertAlmostEqual(impacts[0]["start"], 11.5, delta=0.03)

    def test_drums_only_with_no_bass_following_is_not_an_entry(self) -> None:
        n = 3000
        drums = self._sparse_kick_drums(n, 10.0, 28.0)
        bass = np.full(n, 0.005)
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        self.assertEqual(detect_stem_entry_impacts(rms_loudness, beats, [{"start": 0.0}, {"start": 9.9}], []), [])

    def test_drums_led_entry_over_a_continuing_groove_is_not_an_entry(self) -> None:
        n = 3000
        t = np.arange(n) * 0.01
        drums = self._sparse_kick_drums(n, 4.0, 28.0)  # kicks already running before the boundary
        bass = np.where(t < 10.5, 0.005, 1.0)
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        self.assertEqual(detect_stem_entry_impacts(rms_loudness, beats, [{"start": 0.0}, {"start": 9.9}], []), [])

    def test_riser_before_the_hit_does_not_pull_the_onset_early(self) -> None:
        n = 2000
        t = np.arange(n) * 0.01
        # A slow bass riser from 8s-10s that never clears the on-threshold on
        # its own, then a real, simultaneous bass+drums entry at 10s.
        bass = np.where(t < 8.0, 0.01, np.where(t < 10.0, 0.01 + (t - 8.0) / 2.0 * 0.34, 1.0))
        drums = np.where(t < 10.0, 0.01, 1.0)
        rms_loudness = _rms_loudness(bass, drums)
        beats = _beats(n_bars=40, bar_len=2.0)
        sections = [{"start": 0.0}, {"start": 10.0}]
        impacts = detect_stem_entry_impacts(rms_loudness, beats, sections, [])
        self.assertEqual(len(impacts), 1)
        self.assertAlmostEqual(impacts[0]["start"], 10.0, delta=0.1)
        self.assertGreater(impacts[0]["start"], 9.5)


class DetectSnareRollTests(unittest.TestCase):
    def test_doubling_onset_density_is_a_roll(self) -> None:
        beats = _beats(n_bars=6, bar_len=2.0)
        # bars 1-2: sparse (3 hits/bar); bars 3-4: doubled (7-8 hits/bar).
        drum_events = []
        for bar, count in ((1, 3), (2, 3), (3, 7), (4, 8)):
            bar_start = (bar - 1) * 2.0
            for i in range(count):
                drum_events.append({"time": bar_start + i * (2.0 / (count + 1)), "event_type": "snare"})
        rolls = detect_snare_roll(drum_events, beats)
        self.assertTrue(rolls, "expected a detected snare roll")
        self.assertEqual(rolls[0]["type"], "snare_roll")

    def test_steady_density_is_not_a_roll(self) -> None:
        beats = _beats(n_bars=6, bar_len=2.0)
        drum_events = []
        for bar in range(1, 6):
            bar_start = (bar - 1) * 2.0
            for i in range(3):
                drum_events.append({"time": bar_start + i * 0.5, "event_type": "hat"})
        self.assertEqual(detect_snare_roll(drum_events, beats), [])


class DetectPreDropGapTests(unittest.TestCase):
    def test_dropout_spike_before_impact_is_a_gap(self) -> None:
        times = np.arange(0.0, 10.0, 0.05)
        dropout = np.full(len(times), 0.05)
        impact_time = 8.0
        idx = np.where((times >= impact_time - 1.5) & (times < impact_time))[0]
        dropout[idx] = 0.95
        impacts = [{"start": impact_time, "end": impact_time, "confidence": 0.9, "intensity": 0.9, "evidence": "x"}]
        beats = _beats(n_bars=10, bar_len=1.0)
        gaps = detect_pre_drop_gaps(times, dropout, impacts, beats)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["type"], "pre_drop_gap")
        self.assertLessEqual(gaps[0]["end"], impact_time + 1e-6)


class AssembleGesturesTests(unittest.TestCase):
    def test_assembles_impact_build_and_release_phases(self) -> None:
        beats = _beats(n_bars=20, bar_len=2.0)
        impact = {"start": 30.0, "end": 30.0, "confidence": 0.9, "intensity": 0.9, "evidence": "impact evidence"}
        riser = {"type": "riser", "start": 22.0, "end": 29.9, "confidence": 0.7, "intensity": 0.6, "evidence": "riser evidence"}
        rms_times = np.arange(0.0, 40.0, 0.1)
        rms_mix = np.where(rms_times < 30.0, 0.2, 0.6)  # loud plateau after the impact
        gestures_out = assemble_gestures([impact], [riser], [], [], [], beats, rms_times, rms_mix)
        self.assertEqual(len(gestures_out), 1)
        phases = gestures_out[0]["phases"]
        self.assertIn("impact", phases)
        self.assertIn("build", phases)
        self.assertIn("release", phases)
        # No pre-drop gap / reverse cymbal was supplied, so tension is absent
        # rather than guessed (no silent fallbacks — never guess to keep a run green).
        self.assertNotIn("tension", phases)

    def test_no_supporting_primitive_means_absent_not_guessed(self) -> None:
        beats = _beats(n_bars=10, bar_len=2.0)
        impact = {"start": 10.0, "end": 10.0, "confidence": 0.8, "intensity": 0.8, "evidence": "impact evidence"}
        gestures_out = assemble_gestures([impact], [], [], [], [], beats, np.array([]), None)
        phases = gestures_out[0]["phases"]
        self.assertEqual(set(phases.keys()), {"impact"})

    def test_assemble_gestures_assigns_shared_gesture_id(self) -> None:
        beats = _beats(n_bars=30, bar_len=2.0)
        impacts = [
            {"start": 30.0, "end": 30.0, "confidence": 0.9, "intensity": 0.9, "evidence": "impact a"},
            {"start": 50.0, "end": 50.0, "confidence": 0.9, "intensity": 0.9, "evidence": "impact b"},
        ]
        risers = [
            {"type": "riser", "start": 22.0, "end": 29.9, "confidence": 0.7, "intensity": 0.6, "evidence": "riser a"},
            {"type": "riser", "start": 42.0, "end": 49.9, "confidence": 0.7, "intensity": 0.6, "evidence": "riser b"},
        ]
        rms_times = np.arange(0.0, 60.0, 0.1)
        rms_mix = np.full(rms_times.shape, 0.2)
        gestures_out = assemble_gestures(impacts, risers, [], [], [], beats, rms_times, rms_mix)
        self.assertEqual(len(gestures_out), 2)
        ids = [g["gesture_id"] for g in gestures_out]
        self.assertEqual(ids, ["gesture-001", "gesture-002"])
        for g in gestures_out:
            self.assertRegex(g["gesture_id"], r"^gesture-\d{3}$")


class DetectSectionTransitionsTests(unittest.TestCase):
    def test_one_transition_per_boundary(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 30.0, "function": "intro", "function_status": "known", "confidence": 0.9},
            {"section_id": "section-002", "start": 30.0, "end": 60.0, "function": "verse", "function_status": "known", "confidence": 0.6},
            {"section_id": "section-003", "start": 60.0, "end": 90.0, "function": "chorus", "function_status": "known", "confidence": 0.8},
        ]
        transitions = detect_section_transitions(sections)
        self.assertEqual(len(transitions), 2)
        self.assertEqual(transitions[0]["type"], "intro → verse")
        self.assertEqual(transitions[1]["type"], "verse → chorus")
        self.assertEqual(transitions[0]["start_time"], 30.0)
        self.assertEqual(transitions[0]["confidence"], 0.6)
        for t in transitions:
            self.assertTrue(t["summary"])
            for boilerplate in _FORBIDDEN_BOILERPLATE:
                self.assertNotIn(boilerplate, t["summary"])


class BuildGesturesEndToEndTests(unittest.TestCase):
    def test_writes_flat_events_with_resolvable_sections_and_clean_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(song_path=root / "songs" / "_song.mp3", analysis_root=root / "analysis")

            beats = _beats(n_bars=20, bar_len=2.0)
            timing = {"beats": beats, "bars": [{"bar": b, "start_s": (b - 1) * 2.0, "end_s": b * 2.0} for b in range(1, 21)]}

            fft_times = np.arange(0.0, 40.0, 0.1)
            n = len(fft_times)
            levels = np.full((n, 7), 0.2)
            transient = np.zeros(n)
            dropout = np.zeros(n)
            impact_time = 30.0
            impact_idx = int(np.argmin(np.abs(fft_times - impact_time)))
            # Riser into the impact.
            riser_mask = (fft_times >= 22.0) & (fft_times < impact_time)
            ramp = np.linspace(0.1, 0.9, riser_mask.sum())
            for band in (4, 5, 6):
                levels[riser_mask, band] = ramp
            levels[impact_idx - 1 : impact_idx + 2, 0] = 0.95
            transient[impact_idx] = 1.0
            gap_mask = (fft_times >= impact_time - 1.5) & (fft_times < impact_time)
            dropout[gap_mask] = 0.9

            fft_bands = {
                "bands": [{"id": "sub"}, {"id": "bass"}, {"id": "low_mid"}, {"id": "mid"}, {"id": "upper_mid"}, {"id": "presence"}, {"id": "brilliance"}],
                "frames": [
                    {
                        "time": float(fft_times[i]),
                        "levels": levels[i].tolist(),
                        "transient_strength": float(transient[i]),
                        "dropout_strength": float(dropout[i]),
                    }
                    for i in range(n)
                ],
            }

            rms_times = np.arange(0.0, 40.0, 0.1)
            rms_mix = np.where(rms_times < impact_time, 0.2, 0.6)
            rms_loudness = {
                "sources": [{"id": "mix"}],
                "frames": [{"time": float(rms_times[i]), "values": [float(rms_mix[i])]} for i in range(len(rms_times))],
            }

            drum_events = {"events": []}

            sections_payload = {
                "sections": [
                    {"section_id": "section-001", "start": 0.0, "end": 20.0, "function": "verse", "function_status": "known", "confidence": 0.9},
                    {"section_id": "section-002", "start": 20.0, "end": 40.0, "function": "chorus", "function_status": "known", "confidence": 0.85},
                ]
            }

            payload = build_gestures(paths, fft_bands, rms_loudness, drum_events, timing, sections_payload)

            self.assertTrue(payload["events"], "expected at least one event")
            written = read_json(paths.timeline_output_path)
            self.assertEqual(written, payload)

            # v3.6 item 8 — `summary` (and section_name/evidence_summary/
            # provenance) is dropped from the top-level `payload`/`written`
            # view; the full event shape, including `summary`, lives in the
            # artifact this stage writes first.
            full_events = read_json(paths.artifact("gestures", "song_event_timeline.json"))["events"]
            self.assertEqual(len(full_events), len(payload["events"]))
            for event in full_events:
                self.assertTrue(event["summary"], "summary must be non-empty")
                for boilerplate in _FORBIDDEN_BOILERPLATE:
                    self.assertNotIn(boilerplate, event["summary"])

            section_ids = {s["section_id"] for s in sections_payload["sections"]}
            phase_types = set(PHASE_NAMES)
            for event in payload["events"]:
                self.assertNotIn("summary", event)
                if event["section_id"] is not None:
                    self.assertIn(event["section_id"], section_ids)
                self.assertTrue(
                    event["type"] in phase_types or " → " in event["type"],
                    f"unexpected event type {event['type']!r}",
                )

            # At least one phase event and one transition event were produced.
            self.assertTrue(any(e["type"] in phase_types for e in payload["events"]))
            self.assertTrue(any(" → " in e["type"] for e in payload["events"]))

    def test_build_gestures_marks_phase_rows_with_gesture_id_and_transition_rows_without(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(song_path=root / "songs" / "_song.mp3", analysis_root=root / "analysis")
            beats = _beats(n_bars=20, bar_len=2.0)
            timing = {"beats": beats, "bars": [{"bar": b, "start_s": (b - 1) * 2.0, "end_s": b * 2.0} for b in range(1, 21)]}
            fft_times = np.arange(0.0, 40.0, 0.1)
            n = len(fft_times)
            levels = np.full((n, 7), 0.2)
            transient = np.zeros(n)
            dropout = np.zeros(n)
            impact_time = 30.0
            impact_idx = int(np.argmin(np.abs(fft_times - impact_time)))
            riser_mask = (fft_times >= 22.0) & (fft_times < impact_time)
            ramp = np.linspace(0.1, 0.9, riser_mask.sum())
            for band in (4, 5, 6):
                levels[riser_mask, band] = ramp
            levels[impact_idx - 1 : impact_idx + 2, 0] = 0.95
            transient[impact_idx] = 1.0
            gap_mask = (fft_times >= impact_time - 1.5) & (fft_times < impact_time)
            dropout[gap_mask] = 0.9
            fft_bands = {
                "bands": [{"id": "sub"}, {"id": "bass"}, {"id": "low_mid"}, {"id": "mid"}, {"id": "upper_mid"}, {"id": "presence"}, {"id": "brilliance"}],
                "frames": [{"time": float(fft_times[i]), "levels": levels[i].tolist(), "transient_strength": float(transient[i]), "dropout_strength": float(dropout[i])} for i in range(n)],
            }
            rms_times = np.arange(0.0, 40.0, 0.1)
            rms_mix = np.where(rms_times < impact_time, 0.2, 0.6)
            rms_loudness = {"sources": [{"id": "mix"}], "frames": [{"time": float(rms_times[i]), "values": [float(rms_mix[i])]} for i in range(len(rms_times))]}
            drum_events = {"events": []}
            sections_payload = {"sections": [{"section_id": "section-001", "start": 0.0, "end": 20.0, "function": "verse", "function_status": "known", "confidence": 0.9}, {"section_id": "section-002", "start": 20.0, "end": 40.0, "function": "chorus", "function_status": "known", "confidence": 0.85}]}
            payload = build_gestures(paths, fft_bands, rms_loudness, drum_events, timing, sections_payload)
            phase_events = [e for e in payload["events"] if e["type"] in {"approach", "build", "tension", "impact", "release"}]
            transition_events = [e for e in payload["events"] if " → " in e["type"]]
            self.assertTrue(phase_events)
            self.assertTrue(transition_events)
            for event in phase_events:
                self.assertIn("gesture_id", event)
                self.assertRegex(event["gesture_id"], r"^gesture-\d{3}$")
            for event in transition_events:
                self.assertNotIn("gesture_id", event)

            # Grouping by gesture_id yields runs whose phase rows are
            # time-ordered and non-overlapping.
            by_gesture: dict[str, list[dict]] = {}
            for event in phase_events:
                by_gesture.setdefault(event["gesture_id"], []).append(event)
            for run in by_gesture.values():
                run_sorted = sorted(run, key=lambda e: e["start_time"])
                self.assertEqual(run, sorted(run, key=lambda e: (e["start_time"], e["end_time"])))
                for earlier, later in zip(run_sorted, run_sorted[1:]):
                    self.assertLessEqual(earlier["end_time"], later["start_time"] + 1e-6)


if __name__ == "__main__":
    unittest.main()
