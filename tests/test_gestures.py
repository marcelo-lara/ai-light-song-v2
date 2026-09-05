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
    """Constitution §5.2: phase 3 ("relate") never opens the audio."""

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
        # rather than guessed (constitution §2).
        self.assertNotIn("tension", phases)

    def test_no_supporting_primitive_means_absent_not_guessed(self) -> None:
        beats = _beats(n_bars=10, bar_len=2.0)
        impact = {"start": 10.0, "end": 10.0, "confidence": 0.8, "intensity": 0.8, "evidence": "impact evidence"}
        gestures_out = assemble_gestures([impact], [], [], [], [], beats, np.array([]), None)
        phases = gestures_out[0]["phases"]
        self.assertEqual(set(phases.keys()), {"impact"})


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

            section_ids = {s["section_id"] for s in sections_payload["sections"]}
            phase_types = set(PHASE_NAMES)
            for event in payload["events"]:
                self.assertTrue(event["summary"], "summary must be non-empty")
                for boilerplate in _FORBIDDEN_BOILERPLATE:
                    self.assertNotIn(boilerplate, event["summary"])
                if event["section_id"] is not None:
                    self.assertIn(event["section_id"], section_ids)
                self.assertTrue(
                    event["type"] in phase_types or " → " in event["type"],
                    f"unexpected event type {event['type']!r}",
                )

            # At least one phase event and one transition event were produced.
            self.assertTrue(any(e["type"] in phase_types for e in payload["events"]))
            self.assertTrue(any(" → " in e["type"] for e in payload["events"]))


if __name__ == "__main__":
    unittest.main()
