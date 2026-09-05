from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from analyzer.exceptions import AnalysisError
from analyzer.paths import SongPaths
from analyzer.stages import segmentation
from analyzer.stages.segmentation import (
    HARMONIX_LABELS,
    MUSICAL_LABELS,
    _entropy_confidence,
    _function_confidence_for_span,
    _label_posterior,
    _labelling_status,
    _phrase_rows,
    merge_equal_labelled_runs,
    segment_sections,
)


class _FakeSegment:
    def __init__(self, start: float, end: float, label: str) -> None:
        self.start = start
        self.end = end
        self.label = label


class _FakeResult:
    def __init__(self, segments: list[_FakeSegment], activations: dict[str, np.ndarray] | None) -> None:
        self.segments = segments
        self.activations = activations


def _uniform_activations(n_frames: int, dominant_index: int | None = None, dominant_share: float = 0.9) -> dict[str, np.ndarray]:
    """A (10, T) softmax-like activation matrix over HARMONIX_LABELS, plus a
    `(T,)` `downbeat` stream this stage never reads (item 8 owns it) but
    `analyzer.allin1_cache` requires to be present. If `dominant_index` is
    given, that label carries `dominant_share` of the mass on every frame;
    otherwise mass is split evenly across the musical labels."""
    matrix = np.zeros((len(HARMONIX_LABELS), n_frames), dtype=np.float32)
    musical_indices = [i for i, label in enumerate(HARMONIX_LABELS) if label in MUSICAL_LABELS]
    if dominant_index is not None:
        remainder = (1.0 - dominant_share) / (len(musical_indices) - 1)
        for i in musical_indices:
            matrix[i, :] = dominant_share if i == dominant_index else remainder
    else:
        share = 1.0 / len(musical_indices)
        for i in musical_indices:
            matrix[i, :] = share
    return {"label": matrix, "downbeat": np.zeros(n_frames, dtype=np.float32)}


class MergeEqualLabelledRunsTests(unittest.TestCase):
    def test_merges_consecutive_equal_labelled_phrases(self) -> None:
        phrase_rows = [
            {"function": "chorus", "start": 0.0, "end": 8.0},
            {"function": "chorus", "start": 8.0, "end": 16.0},
            {"function": "verse", "start": 16.0, "end": 24.0},
        ]
        runs = merge_equal_labelled_runs(phrase_rows)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0], {"function": "chorus", "start": 0.0, "end": 16.0})
        self.assertEqual(runs[1], {"function": "verse", "start": 16.0, "end": 24.0})

    def test_does_not_merge_across_a_gap(self) -> None:
        phrase_rows = [
            {"function": "chorus", "start": 0.0, "end": 8.0},
            {"function": "chorus", "start": 9.0, "end": 16.0},
        ]
        runs = merge_equal_labelled_runs(phrase_rows)
        self.assertEqual(len(runs), 2)

    def test_phrase_rows_drops_sentinels(self) -> None:
        result = _FakeResult(
            segments=[
                _FakeSegment(0.0, 0.0, "start"),
                _FakeSegment(0.0, 8.0, "intro"),
                _FakeSegment(8.0, 8.0, "end"),
            ],
            activations=None,
        )
        rows = _phrase_rows(result)
        self.assertEqual([row["function"] for row in rows], ["intro"])


class EntropyConfidenceTests(unittest.TestCase):
    def test_certain_posterior_yields_high_confidence(self) -> None:
        labels, posterior = _label_posterior(_uniform_activations(10, dominant_index=HARMONIX_LABELS.index("chorus"), dominant_share=0.999))
        confidence = _function_confidence_for_span(labels, posterior, 0.0, 0.1)
        self.assertGreater(confidence, 0.9)

    def test_flat_posterior_yields_zero_confidence(self) -> None:
        labels, posterior = _label_posterior(_uniform_activations(10, dominant_index=None))
        confidence = _entropy_confidence(posterior)
        self.assertAlmostEqual(confidence, 0.0, places=3)

    def test_confidence_is_bounded(self) -> None:
        labels, posterior = _label_posterior(_uniform_activations(5, dominant_index=HARMONIX_LABELS.index("verse"), dominant_share=0.6))
        confidence = _function_confidence_for_span(labels, posterior, 0.0, 0.05)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)


class LabellingStatusTests(unittest.TestCase):
    def test_known_when_labels_are_varied_and_balanced(self) -> None:
        sections = [
            {"function": "intro", "start": 0.0, "end": 10.0},
            {"function": "verse", "start": 10.0, "end": 20.0},
            {"function": "chorus", "start": 20.0, "end": 30.0},
        ]
        self.assertEqual(_labelling_status(sections, 30.0), "known")

    def test_unknown_when_fewer_than_three_distinct_labels(self) -> None:
        sections = [
            {"function": "verse", "start": 0.0, "end": 15.0},
            {"function": "chorus", "start": 15.0, "end": 30.0},
        ]
        self.assertEqual(_labelling_status(sections, 30.0), "unknown")

    def test_unknown_when_one_label_dominates(self) -> None:
        sections = [
            {"function": "inst", "start": 0.0, "end": 28.0},
            {"function": "verse", "start": 28.0, "end": 29.0},
            {"function": "chorus", "start": 29.0, "end": 30.0},
        ]
        self.assertEqual(_labelling_status(sections, 30.0), "unknown")

    def test_known_when_dominant_label_share_is_exactly_at_threshold(self) -> None:
        sections = [
            {"function": "inst", "start": 0.0, "end": 27.0},
            {"function": "verse", "start": 27.0, "end": 29.0},
            {"function": "chorus", "start": 29.0, "end": 30.0},
        ]
        self.assertEqual(_labelling_status(sections, 30.0), "known")

    def test_unknown_when_no_sections(self) -> None:
        self.assertEqual(_labelling_status([], 30.0), "unknown")


def _install_fake_allin1(result: _FakeResult) -> MagicMock:
    fake_module = types.ModuleType("allin1")
    analyze_mock = MagicMock(return_value=result)
    fake_module.analyze = analyze_mock  # type: ignore[attr-defined]
    sys.modules["allin1"] = fake_module
    return analyze_mock


class SegmentSectionsTests(unittest.TestCase):
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

    def test_same_label_as_points_to_first_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            timing = {"bars": [{"bar": 1, "start_s": 0.0, "end_s": 30.0}]}
            segments = [
                _FakeSegment(0.0, 8.0, "intro"),
                _FakeSegment(8.0, 16.0, "verse"),
                _FakeSegment(16.0, 24.0, "chorus"),
                _FakeSegment(24.0, 30.0, "chorus"),
            ]
            n_frames = int(30.0 * segmentation.ACTIVATION_RATE_HZ)
            result = _FakeResult(segments=segments, activations=_uniform_activations(n_frames, dominant_index=HARMONIX_LABELS.index("chorus"), dominant_share=0.7))
            analyze_mock = _install_fake_allin1(result)

            payload = segment_sections(paths, stems, timing)

            sections = payload["sections"]
            self.assertEqual([s["function"] for s in sections], ["intro", "verse", "chorus"])
            self.assertIsNone(sections[0]["same_label_as"])
            self.assertIsNone(sections[1]["same_label_as"])
            self.assertIsNone(sections[2]["same_label_as"])
            analyze_mock.assert_called_once()
            _, kwargs = analyze_mock.call_args
            self.assertTrue(kwargs["include_activations"])

    def test_repeated_label_points_same_label_as_to_first_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            timing = {"bars": [{"bar": 1, "start_s": 0.0, "end_s": 32.0}]}
            segments = [
                _FakeSegment(0.0, 8.0, "verse"),
                _FakeSegment(8.0, 16.0, "chorus"),
                _FakeSegment(16.0, 24.0, "verse"),
                _FakeSegment(24.0, 32.0, "chorus"),
            ]
            n_frames = int(32.0 * segmentation.ACTIVATION_RATE_HZ)
            result = _FakeResult(segments=segments, activations=_uniform_activations(n_frames, dominant_index=None))
            _install_fake_allin1(result)

            payload = segment_sections(paths, stems, timing)
            sections = {s["section_id"]: s for s in payload["sections"]}
            ordered = payload["sections"]
            self.assertEqual([s["function"] for s in ordered], ["verse", "chorus", "verse", "chorus"])
            self.assertIsNone(ordered[0]["same_label_as"])
            self.assertIsNone(ordered[1]["same_label_as"])
            self.assertEqual(ordered[2]["same_label_as"], ordered[0]["section_id"])
            self.assertEqual(ordered[3]["same_label_as"], ordered[1]["section_id"])

    def test_seeds_from_pipeline_stems_not_allin1s_own_demix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            timing = {"bars": [{"bar": 1, "start_s": 0.0, "end_s": 8.0}]}
            segments = [_FakeSegment(0.0, 8.0, "intro")]
            n_frames = int(8.0 * segmentation.ACTIVATION_RATE_HZ)
            result = _FakeResult(segments=segments, activations=_uniform_activations(n_frames, dominant_index=None))
            analyze_mock = _install_fake_allin1(result)

            with patch("analyzer.allin1_cache.DEMIX_DIR", Path(tmp) / "demix"):
                segment_sections(paths, stems, timing)
                linked_other = Path(tmp) / "demix" / "htdemucs" / paths.song_path.stem / "other.wav"
                linked_vocals = Path(tmp) / "demix" / "htdemucs" / paths.song_path.stem / "vocals.wav"
                self.assertTrue(linked_other.is_symlink())
                self.assertEqual(Path(linked_other.readlink()), Path(stems["harmonic"]))
                self.assertTrue(linked_vocals.is_symlink())
                self.assertEqual(Path(linked_vocals.readlink()), Path(stems["vocals"]))
            analyze_mock.assert_called_once()

    def test_raises_when_allin1_returns_no_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            timing = {"bars": [{"bar": 1, "start_s": 0.0, "end_s": 8.0}]}
            result = _FakeResult(segments=[], activations=None)
            _install_fake_allin1(result)
            with self.assertRaises(AnalysisError):
                segment_sections(paths, stems, timing)

    def test_degenerate_song_marks_every_row_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths, stems = self._make_paths_and_stems(tmp)
            timing = {"bars": [{"bar": 1, "start_s": 0.0, "end_s": 60.0}]}
            segments = [_FakeSegment(0.0, 60.0, "inst")]
            n_frames = int(60.0 * segmentation.ACTIVATION_RATE_HZ)
            result = _FakeResult(segments=segments, activations=_uniform_activations(n_frames, dominant_index=HARMONIX_LABELS.index("inst"), dominant_share=0.95))
            _install_fake_allin1(result)

            payload = segment_sections(paths, stems, timing)
            self.assertTrue(all(s["function_status"] == "unknown" for s in payload["sections"]))
            # Boundaries stay as measured — only the name is untrusted.
            self.assertEqual(payload["sections"][0]["start"], 0.0)
            self.assertEqual(payload["sections"][0]["end"], 60.0)


if __name__ == "__main__":
    unittest.main()
