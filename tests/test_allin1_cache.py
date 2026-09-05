from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from analyzer.allin1_cache import get_allin1_result
from analyzer.exceptions import AnalysisError
from analyzer.paths import SongPaths


class _FakeSegment:
    def __init__(self, start: float, end: float, label: str) -> None:
        self.start = start
        self.end = end
        self.label = label


class _FakeResult:
    def __init__(self, segments, activations) -> None:
        self.segments = segments
        self.activations = activations


def _install_fake_allin1(result: _FakeResult) -> MagicMock:
    fake_module = types.ModuleType("allin1")
    analyze_mock = MagicMock(return_value=result)
    fake_module.analyze = analyze_mock  # type: ignore[attr-defined]
    sys.modules["allin1"] = fake_module
    return analyze_mock


class Allin1CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._sys_modules_patch = patch.dict(sys.modules, {})
        self._sys_modules_patch.start()
        self.addCleanup(self._sys_modules_patch.stop)
        self.addCleanup(sys.modules.pop, "allin1", None)

    def _make_paths_and_stems(self, tmp: str) -> tuple[SongPaths, dict[str, str]]:
        root = Path(tmp)
        paths = SongPaths(song_path=root / "songs" / "song.mp3", analysis_root=root / "analysis")
        paths.song_path.parent.mkdir(parents=True, exist_ok=True)
        paths.song_path.write_bytes(b"fake-mp3")
        stems_dir = root / "stems"
        stems_dir.mkdir(parents=True, exist_ok=True)
        stems = {}
        for name in ("bass", "drums", "harmonic", "vocals"):
            stem_path = stems_dir / f"{name}.wav"
            stem_path.write_bytes(b"fake-wav")
            stems[name] = str(stem_path)
        return paths, stems

    def test_runs_model_once_and_persists_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            n_frames = 100
            result = _FakeResult(
                segments=[_FakeSegment(0.0, 1.0, "intro")],
                activations={
                    "downbeat": np.linspace(0.0, 1.0, n_frames, dtype=np.float32),
                    "label": np.zeros((10, n_frames), dtype=np.float32),
                },
            )
            analyze_mock = _install_fake_allin1(result)

            with patch("analyzer.allin1_cache.DEMIX_DIR", Path(tmp) / "demix"):
                cached_result, seeded = get_allin1_result(paths, stems)
                self.assertTrue(paths.artifact("allin1", "raw.json").exists())
                self.assertEqual(seeded, ["bass", "drums", "other", "vocals"])
                self.assertEqual(len(cached_result.segments), 1)
                self.assertEqual(cached_result.segments[0].label, "intro")
                self.assertEqual(cached_result.activations["downbeat"].shape, (n_frames,))
                self.assertEqual(cached_result.activations["label"].shape, (10, n_frames))
                analyze_mock.assert_called_once()

                # A second call in the same pass must not invoke the model again.
                get_allin1_result(paths, stems)
                analyze_mock.assert_called_once()

    def test_second_call_reads_cache_without_allin1_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            n_frames = 50
            result = _FakeResult(
                segments=[_FakeSegment(0.0, 2.0, "verse")],
                activations={
                    "downbeat": np.zeros(n_frames, dtype=np.float32),
                    "label": np.zeros((10, n_frames), dtype=np.float32),
                },
            )
            _install_fake_allin1(result)
            with patch("analyzer.allin1_cache.DEMIX_DIR", Path(tmp) / "demix"):
                get_allin1_result(paths, stems)

            # Simulate a later stage in the same or a later pipeline pass,
            # where allin1 is not even importable — the cache must be enough.
            sys.modules.pop("allin1", None)
            cached_result, _seeded = get_allin1_result(paths, stems)
            self.assertEqual(cached_result.segments[0].label, "verse")

    def test_raises_when_downbeat_activation_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            result = _FakeResult(
                segments=[_FakeSegment(0.0, 1.0, "intro")],
                activations={"label": np.zeros((10, 10), dtype=np.float32)},
            )
            _install_fake_allin1(result)
            with patch("analyzer.allin1_cache.DEMIX_DIR", Path(tmp) / "demix"):
                with self.assertRaises(AnalysisError):
                    get_allin1_result(paths, stems)


if __name__ == "__main__":
    unittest.main()
