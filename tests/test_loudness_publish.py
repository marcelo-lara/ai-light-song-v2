"""v3.1 item 7 — top-level loudness.json is artifacts/essentia/rms_loudness.json
decimated 10 ms -> 20 ms by AVERAGING pairs (not dropping frames), with the
host-path `path` field stripped from every stem source."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.ui_data import build_ui_data


def _rms_artifact(n_frames: int) -> dict:
    frames = []
    for i in range(n_frames):
        t = round(0.005 + i * 0.010, 4)
        frames.append({
            "frame_index": i,
            "start_s": round(i * 0.010, 4),
            "end_s": round((i + 1) * 0.010, 4),
            "time": t,
            "values": [round(0.01 * i, 6), round(0.02 * i, 6)],
            "normalized_values": [round(0.03 * i, 6), round(0.04 * i, 6)],
            "history": {"peak_5s": [0.0, 0.0]},
        })
    return {
        "schema_version": "3.0",
        "song_name": "_test_song",
        "generated_from": {"source_song_path": "/data/songs/_test_song.mp3"},
        "sources": [
            {"id": "mix", "label": "Mix", "path": "/data/songs/_test_song.mp3", "kind": "mix"},
            {"id": "bass", "label": "Bass", "path": "/data/analysis/x/artifacts/stems/bass.wav", "kind": "stem"},
        ],
        "metadata": {
            "sample_rate": 44100, "window_ms": 10, "window_size": 441,
            "duration": round(n_frames * 0.010, 6), "total_frames": n_frames,
            "normalization_scope": "per-song-per-source-peak-rms",
            "source_order": ["mix", "bass"], "interval_ms": 10,
        },
        "frames": frames,
    }


def _setup(tmp: str, n_frames: int) -> SongPaths:
    root = Path(tmp)
    paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
    paths.artifact("essentia").mkdir(parents=True)
    paths.artifact("essentia", "beats.json").write_text(json.dumps(
        {"beats": [{"time": 0.0, "index": 1, "bar": 1, "beat_in_bar": 1, "type": "downbeat"}]}))
    paths.artifact("layer_a_harmonic.json").write_text(json.dumps({"chords": []}))
    paths.artifact("section_segmentation").mkdir(parents=True, exist_ok=True)
    paths.artifact("section_segmentation", "sections.json").write_text(json.dumps({"sections": [
        {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro",
         "function_confidence": 0.9, "function_status": "known", "same_label_as": None, "confidence": 0.9},
    ]}))
    paths.artifact("genre.json").write_text(json.dumps(
        {"genres": ["x"], "confidence": 0.5, "top_predictions": [], "guidance": []}))
    paths.artifact("symbolic_transcription").mkdir(parents=True, exist_ok=True)
    paths.artifact("symbolic_transcription", "drum_events.json").write_text(json.dumps(
        {"summary": {}, "supported_event_types": [], "events": []}))
    paths.artifact("essentia", "rms_loudness.json").write_text(json.dumps(_rms_artifact(n_frames)))
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


class LoudnessPublishTests(unittest.TestCase):
    def _publish(self, n_frames: int) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, n_frames)
            build_ui_data(paths)
            return json.loads(paths.loudness_output_path.read_text())

    def test_odd_and_even_frame_counts_halve_within_one_frame(self) -> None:
        for n in (10, 19401, 4001):
            payload = self._publish(n)
            frames = payload["frames"]
            self.assertLessEqual(abs(len(frames) - n / 2), 1)
            self.assertEqual(payload["metadata"]["interval_ms"], 20)
            self.assertEqual(payload["metadata"]["total_frames"], len(frames))

    def test_successive_frame_times_are_20ms_apart(self) -> None:
        for n in (2000, 19401):  # even and odd source-frame counts
            frames = self._publish(n)["frames"]
            for a, b in zip(frames, frames[1:]):
                self.assertAlmostEqual(b["time"] - a["time"], 0.020, delta=0.001)

    def test_no_path_key_and_no_data_prefixed_string_anywhere(self) -> None:
        payload = self._publish(200)
        all_strings = list(_strings(payload))
        self.assertNotIn("path", all_strings)
        self.assertFalse([s for s in all_strings if s.startswith("/data/")])
        self.assertEqual(
            [set(s) for s in payload["sources"]][0], {"id", "label", "kind"})

    def test_pair_averaging_keeps_the_mean_not_a_dropped_frame(self) -> None:
        # artifact frame i values = [0.01*i, 0.02*i]; pair (0,1) -> mean [0.005, 0.01]
        frames = self._publish(10)["frames"]
        self.assertAlmostEqual(frames[0]["values"][0], 0.005, places=6)
        self.assertAlmostEqual(frames[0]["values"][1], 0.010, places=6)


if __name__ == "__main__":
    unittest.main()
