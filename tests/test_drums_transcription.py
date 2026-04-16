from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyzer.paths import SongPaths
from analyzer.stages.drums import extract_drum_events


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_timing() -> dict:
    beats: list[dict[str, object]] = []
    bars: list[dict[str, object]] = []
    beat_time = 0.0
    for bar_number in range(1, 3):
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
        bars.append({"bar": bar_number, "start_s": round(bar_start, 6), "end_s": round(beat_time, 6)})
    return {"beats": beats, "bars": bars, "bpm": 120.0, "duration": beat_time}


class _FakeNote:
    def __init__(self, start: float, end: float, pitch: int, velocity: int) -> None:
        self.start = start
        self.end = end
        self.pitch = pitch
        self.velocity = velocity


class _FakeInstrument:
    def __init__(self, notes: list[_FakeNote]) -> None:
        self.notes = notes


class _FakeMidi:
    def __init__(self, notes: list[_FakeNote]) -> None:
        self.instruments = [_FakeInstrument(notes)]

    def write(self, path: str) -> None:
        Path(path).write_bytes(b"MThd")


class DrumTranscriptionTests(unittest.TestCase):
    def test_extract_drum_events_writes_omnizart_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            song_path = root / "songs" / "Example Song.mp3"
            song_path.parent.mkdir(parents=True, exist_ok=True)
            song_path.write_bytes(b"fake-mp3")
            drums_stem_path = root / "stems" / "Example Song" / "drums.wav"
            drums_stem_path.parent.mkdir(parents=True, exist_ok=True)
            drums_stem_path.write_bytes(b"fake-wav")

            paths = SongPaths(
                song_path=song_path,
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            timing = _build_timing()
            sections = {
                "sections": [
                    {
                        "section_id": "section-001",
                        "start": 0.0,
                        "end": 4.0,
                        "label": "intro",
                        "section_character": "intro",
                    }
                ]
            }
            fake_midi = _FakeMidi(
                [
                    _FakeNote(0.0, 0.1, 36, 112),
                    _FakeNote(0.5, 0.6, 38, 96),
                    _FakeNote(0.25, 0.35, 42, 84),
                    _FakeNote(0.75, 0.85, 49, 70),
                ]
            )

            class _Completed:
                stdout = ""

            def _fake_run(command: list[str], check: bool, capture_output: bool, text: bool) -> _Completed:
                del check
                del capture_output
                del text
                output_path = Path(command[-1])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"MThd")
                return _Completed()

            with patch("analyzer.stages.drums.resolve_omnizart_drum_model_path", return_value=(Path("/models/omnizart/drum_keras"), "package")), patch("analyzer.stages.drums.subprocess.run", side_effect=_fake_run), patch("pretty_midi.PrettyMIDI", return_value=fake_midi):
                payload = extract_drum_events(
                    paths,
                    stems={"drums": str(drums_stem_path)},
                    timing=timing,
                    sections_payload=sections,
                )

            output_path = paths.artifact("symbolic_transcription", "drum_events.json")
            written = _read_json(output_path)
            midi_exists = paths.artifact("symbolic_transcription", "omnizart", "drums.mid").exists()

        self.assertEqual(payload["generated_from"]["engine"], "audiohacking.omnizart.drum")
        self.assertEqual(written["summary"]["kick_count"], 1)
        self.assertEqual(written["summary"]["snare_count"], 1)
        self.assertEqual(written["summary"]["hat_count"], 1)
        self.assertEqual(written["summary"]["unresolved_count"], 1)
        self.assertEqual(written["generated_from"]["debug_sources"]["full_mix"], str(song_path))
        self.assertEqual(written["generated_from"]["debug_sources"]["drums_stem"], str(drums_stem_path))
        self.assertTrue(midi_exists)
        self.assertEqual(written["events"][0]["event_type"], "kick")
        self.assertEqual(written["events"][1]["event_type"], "hat")
        self.assertEqual(written["events"][3]["event_type"], "unresolved")


if __name__ == "__main__":
    unittest.main()