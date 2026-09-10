from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from analyzer.exceptions import DependencyError
from analyzer.paths import SongPaths
from analyzer.stages.fft_bands import STEM_SOURCE_FILENAMES, extract_fft_bands


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_stems(paths: SongPaths, *, skip: set[str] | None = None) -> None:
    skip = skip or set()
    paths.stems_dir.mkdir(parents=True, exist_ok=True)
    for stem, filename in STEM_SOURCE_FILENAMES.items():
        if stem in skip:
            continue
        (paths.stems_dir / filename).write_bytes(b"fake-wav")


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


def _fake_essentia() -> dict:
    fake_standard = types.ModuleType("essentia.standard")
    fake_standard.MonoLoader = _FakeMonoLoader
    fake_standard.FrameGenerator = _fake_frame_generator
    fake_standard.Windowing = _FakeWindowing
    fake_standard.Spectrum = _FakeSpectrum
    fake_essentia = types.ModuleType("essentia")
    fake_essentia.standard = fake_standard
    return {"essentia": fake_essentia, "essentia.standard": fake_standard}


class FftBandsTests(unittest.TestCase):
    def test_extract_fft_bands_writes_expected_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            song_path = root / "songs" / "_test_song.mp3"
            song_path.parent.mkdir(parents=True, exist_ok=True)
            song_path.write_bytes(b"fake-mp3")
            paths = SongPaths(
                song_path=song_path,
                analysis_root=root / "analysis",
            )
            _write_stems(paths)

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

        self.assertEqual(payload["song_name"], "_test_song")
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
        self.assertNotIn("stem", written["metadata"])  # mix file unchanged

    def test_extract_fft_bands_writes_per_stem_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            song_path = root / "songs" / "_test_song.mp3"
            song_path.parent.mkdir(parents=True, exist_ok=True)
            song_path.write_bytes(b"fake-mp3")
            paths = SongPaths(song_path=song_path, analysis_root=root / "analysis")
            _write_stems(paths)

            with patch.dict(sys.modules, _fake_essentia()):
                extract_fft_bands(paths)

            mix = _read_json(paths.artifact("essentia", "fft_bands.json"))
            for stem in ("bass", "drums", "harmonic", "vocals"):
                stem_file = paths.artifact("essentia", f"fft_bands.{stem}.json")
                self.assertTrue(stem_file.exists(), f"missing {stem_file}")
                doc = _read_json(stem_file)
                self.assertEqual(doc["metadata"]["stem"], stem)
                self.assertEqual(len(doc["bands"]), len(mix["bands"]))
                self.assertEqual(doc["metadata"]["hop_size"], mix["metadata"]["hop_size"])
                self.assertEqual(doc["metadata"]["interval_ms"], mix["metadata"]["interval_ms"])
                self.assertEqual(doc["metadata"]["total_frames"], mix["metadata"]["total_frames"])
                self.assertEqual(len(doc["frames"][0]["levels"]), 7)

    def test_missing_stem_raises_dependency_error_and_writes_no_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            song_path = root / "songs" / "_test_song.mp3"
            song_path.parent.mkdir(parents=True, exist_ok=True)
            song_path.write_bytes(b"fake-mp3")
            paths = SongPaths(song_path=song_path, analysis_root=root / "analysis")
            _write_stems(paths, skip={"vocals"})

            with patch.dict(sys.modules, _fake_essentia()):
                with self.assertRaises(DependencyError) as ctx:
                    extract_fft_bands(paths)

            self.assertIn("vocals", str(ctx.exception))
            self.assertFalse(paths.artifact("essentia", "fft_bands.vocals.json").exists())