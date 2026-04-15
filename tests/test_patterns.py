from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.patterns import extract_chord_patterns


def _build_timing(bar_chords: list[str]) -> dict:
    beats: list[dict[str, object]] = []
    bars: list[dict[str, object]] = []
    beat_time = 0.0
    for bar_number in range(1, len(bar_chords) + 1):
        bar_start = beat_time
        for beat_in_bar in range(1, 5):
            beats.append(
                {
                    "index": len(beats) + 1,
                    "time": round(beat_time, 6),
                    "bar": bar_number,
                    "beat_in_bar": beat_in_bar,
                    "type": "downbeat" if beat_in_bar == 1 else "beat",
                }
            )
            beat_time += 0.5
        bars.append(
            {
                "bar": bar_number,
                "start_s": round(bar_start, 6),
                "end_s": round(beat_time, 6),
            }
        )

    return {
        "beats": beats,
        "bars": bars,
        "bpm": 120.0,
        "duration": round(beat_time, 6),
    }


def _build_harmonic(bar_chords: list[str]) -> dict:
    chords: list[dict[str, object]] = []
    for bar_index, chord in enumerate(bar_chords):
        start_s = round(bar_index * 2.0, 6)
        chords.append(
            {
                "time": start_s,
                "end_s": round(start_s + 2.0, 6),
                "bar": bar_index + 1,
                "beat": 1,
                "chord": chord,
                "confidence": 1.0,
            }
        )
    return {"chords": chords}


class PatternMiningTests(unittest.TestCase):
    def test_extract_chord_patterns_prefers_repeated_24_bar_phrase_over_internal_4_bar_loop(self) -> None:
        phrase = ["C#", "D#", "Fm", "D#"] * 6
        bar_chords = phrase + phrase

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            payload = extract_chord_patterns(paths, _build_timing(bar_chords), _build_harmonic(bar_chords))

        self.assertEqual(payload["settings"]["max_pattern_bars"], 24)
        self.assertEqual(payload["pattern_count"], 1)
        self.assertEqual(payload["patterns"][0]["bar_count"], 4)
        self.assertEqual(payload["patterns"][0]["occurrence_count"], 12)
        self.assertEqual(payload["patterns"][0]["sequence"], "C#|D#|Fm|D#")
        self.assertEqual(payload["patterns"][0]["collapsed_sequence"], "C#→D#→Fm→D#")
        self.assertEqual(payload["patterns"][0]["bar_sequence"], "|".join(phrase))
        self.assertEqual(
            [occurrence["start_bar"] for occurrence in payload["patterns"][0]["occurrences"]],
            [1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45],
        )
        self.assertEqual(payload["patterns"][0]["occurrences"][0]["sequence"], "C#|D#|Fm|D#")
        self.assertEqual(payload["patterns"][0]["occurrences"][0]["collapsed_sequence"], "C#→D#→Fm→D#")
        self.assertEqual(payload["patterns"][0]["occurrences"][0]["bar_sequence"], "C#|D#|Fm|D#")
