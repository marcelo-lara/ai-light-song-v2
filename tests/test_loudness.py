from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from analyzer.paths import SongPaths
from analyzer.stages.loudness import extract_mix_stem_loudness


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _step_audio(sample_rate: int, amplitude: float) -> np.ndarray:
    quiet = np.zeros(int(sample_rate * 0.1), dtype=np.float32)
    active = np.full(int(sample_rate * 0.13), amplitude, dtype=np.float32)
    return np.concatenate([quiet, active])


class _FakeMonoLoader:
    def __init__(self, *, filename: str, sampleRate: int) -> None:
        self.filename = filename
        self.sample_rate = sampleRate

    def __call__(self) -> np.ndarray:
        amplitudes = {
            "Example Song.mp3": 0.8,
            "bass.wav": 0.25,
            "drums.wav": 0.65,
            "harmonic.wav": 0.45,
            "vocals.wav": 0.35,
        }
        return _step_audio(self.sample_rate, amplitudes[Path(self.filename).name])


class LoudnessExtractionTests(unittest.TestCase):
    def test_extract_mix_stem_loudness_writes_rms_and_envelope_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            song_path = root / "songs" / "Example Song.mp3"
            song_path.parent.mkdir(parents=True, exist_ok=True)
            song_path.write_bytes(b"fake-mp3")
            stems_dir = root / "stems" / "Example Song"
            stems_dir.mkdir(parents=True, exist_ok=True)
            stems = {}
            for stem_name in ("bass", "drums", "harmonic", "vocals"):
                stem_path = stems_dir / f"{stem_name}.wav"
                stem_path.write_bytes(b"fake-wav")
                stems[stem_name] = str(stem_path)

            paths = SongPaths(
                song_path=song_path,
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            fake_standard = types.ModuleType("essentia.standard")
            fake_standard.MonoLoader = _FakeMonoLoader
            fake_essentia = types.ModuleType("essentia")
            fake_essentia.standard = fake_standard

            with patch.dict(sys.modules, {"essentia": fake_essentia, "essentia.standard": fake_standard}):
                payload = extract_mix_stem_loudness(paths, stems)

            rms_written = _read_json(paths.artifact("essentia", "rms_loudness.json"))
            envelope_written = _read_json(paths.artifact("essentia", "loudness_envelope.json"))

        self.assertEqual(payload["rms_loudness"]["generated_from"]["engine"], "essentia+numpy.rms_loudness")
        self.assertEqual(payload["loudness_envelope"]["generated_from"]["engine"], "essentia+numpy.loudness_envelope")
        self.assertEqual([source["id"] for source in rms_written["sources"]], ["mix", "bass", "drums", "harmonic", "vocals"])
        self.assertEqual(rms_written["metadata"]["interval_ms"], 10)
        self.assertEqual(rms_written["metadata"]["window_ms"], 10)
        self.assertEqual(rms_written["metadata"]["total_frames"], 23)
        self.assertEqual(envelope_written["metadata"]["window_ms"], 200)
        self.assertEqual(envelope_written["metadata"]["total_frames"], 2)
        self.assertEqual(len(rms_written["frames"][0]["values"]), 5)
        self.assertEqual(len(rms_written["frames"][0]["normalized_values"]), 5)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in rms_written["frames"][-1]["normalized_values"]))
        self.assertEqual(rms_written["frames"][0]["start_s"], 0.0)
        self.assertEqual(rms_written["frames"][0]["end_s"], 0.01)
        self.assertEqual(rms_written["frames"][0]["normalized_values"][0], 0.0)
        self.assertEqual(rms_written["frames"][-1]["normalized_values"][0], 1.0)
        self.assertGreater(rms_written["frames"][-1]["values"][0], rms_written["frames"][0]["values"][0])
