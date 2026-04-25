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
from analyzer.stages.fft_bands import extract_fft_bands


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class _FakeMonoLoader:
    def __init__(self, *, filename: str, sampleRate: int) -> None:
        del filename
        self.sample_rate = sampleRate

    def __call__(self) -> np.ndarray:
        duration_seconds = 0.2
        sample_count = int(self.sample_rate * duration_seconds)
        return np.linspace(-1.0, 1.0, sample_count, dtype=np.float32)


def _fake_frame_generator(audio: np.ndarray, *, frameSize: int, hopSize: int, startFromZero: bool):
    del startFromZero
    if len(audio) < frameSize:
        padded = np.zeros(frameSize, dtype=np.float32)
        padded[: len(audio)] = audio
        yield padded
        return
    for start in range(0, len(audio) - frameSize + 1, hopSize):
        yield audio[start : start + frameSize]


class _FakeWindowing:
    def __init__(self, *, type: str) -> None:
        del type

    def __call__(self, frame: np.ndarray) -> np.ndarray:
        return frame


class _FakeSpectrum:
    def __init__(self, *, size: int) -> None:
        self.size = size

    def __call__(self, frame: np.ndarray) -> np.ndarray:
        del frame
        values = np.zeros((self.size // 2) + 1, dtype=np.float32)
        values[2] = 2.0
        values[8] = 5.0
        values[18] = 7.0
        values[55] = 11.0
        values[130] = 13.0
        values[400] = 17.0
        values[900] = 19.0
        return values


class FftBandsTests(unittest.TestCase):
    def test_extract_fft_bands_writes_expected_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            song_path = root / "songs" / "Example Song.mp3"
            song_path.parent.mkdir(parents=True, exist_ok=True)
            song_path.write_bytes(b"fake-mp3")
            paths = SongPaths(
                song_path=song_path,
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            fake_standard = types.ModuleType("essentia.standard")
            fake_standard.MonoLoader = _FakeMonoLoader
            fake_standard.FrameGenerator = _fake_frame_generator
            fake_standard.Windowing = _FakeWindowing
            fake_standard.Spectrum = _FakeSpectrum

            fake_essentia = types.ModuleType("essentia")
            fake_essentia.standard = fake_standard

            with patch.dict(sys.modules, {"essentia": fake_essentia, "essentia.standard": fake_standard}):
                payload = extract_fft_bands(paths)

            written = _read_json(paths.artifact("essentia", "fft_bands.json"))

        self.assertEqual(payload["song_name"], "Example Song")
        self.assertEqual(written["metadata"]["interval_ms"], 50)
        self.assertEqual(written["metadata"]["hop_size"], 2205)
        self.assertEqual(written["metadata"]["window"], "hann")
        self.assertEqual(len(written["bands"]), 7)
        self.assertEqual([band["id"] for band in written["bands"]], ["sub", "bass", "low_mid", "mid", "upper_mid", "presence", "brilliance"])
        self.assertGreaterEqual(written["metadata"]["total_frames"], 1)
        self.assertEqual(written["generated_from"]["engine"], "essentia+numpy.fft_bands")
        self.assertEqual(len(written["frames"][0]["levels"]), 7)
        self.assertEqual(written["frames"][0]["time"], 0.0)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in written["frames"][0]["levels"]))
        self.assertIn("brightness_ratio", written["frames"][0])
        self.assertIn("transient_strength", written["frames"][0])
        self.assertIn("dropout_strength", written["frames"][0])
        self.assertTrue(0.0 <= written["frames"][0]["brightness_ratio"] <= 1.0)
        self.assertTrue(0.0 <= written["frames"][0]["transient_strength"] <= 1.0)
        self.assertTrue(0.0 <= written["frames"][0]["dropout_strength"] <= 1.0)
        self.assertEqual(
            written["metadata"]["normalization_scope"],
            "per-song-per-band-log-power-percentile",
        )
        self.assertEqual(written["metadata"]["normalization_percentiles"], [5.0, 95.0])