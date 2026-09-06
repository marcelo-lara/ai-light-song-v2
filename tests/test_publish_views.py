"""v3.1 item 5 — top-level genre.json is a published fused view of the
artifacts/ original: no host paths, a field_sources header covering every
emitted field."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.models import PRODUCERS
from analyzer.paths import SongPaths
from analyzer.stages.ui_data import build_ui_data

GENRE_ARTIFACT = {
    "schema_version": "3.0",
    "song_name": "_test_song",
    "generated_from": {"source_song_path": "/data/songs/_test_song.mp3", "engine": "x"},
    "genres": ["electronic", "dance"],
    "confidence": 0.38,
    "top_predictions": [
        {"label": "electronic", "confidence": 0.38},
        {"label": "dance", "confidence": 0.23},
    ],
    "guidance": ["advisory only"],
}


def _setup(tmp: str) -> SongPaths:
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
    paths.artifact("genre.json").write_text(json.dumps(GENRE_ARTIFACT))
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def _no_data_paths(obj) -> bool:
    if isinstance(obj, str):
        return not obj.startswith("/data/")
    if isinstance(obj, dict):
        return all(_no_data_paths(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_data_paths(v) for v in obj)
    return True


class GenrePublishTests(unittest.TestCase):
    def test_top_level_genre_is_a_clean_fused_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp)
            build_ui_data(paths)
            payload = json.loads(paths.genre_output_path.read_text())
        self.assertEqual(payload["genres"], ["electronic", "dance"])
        self.assertEqual(payload["confidence"], 0.38)
        self.assertTrue(_no_data_paths(payload))
        self.assertNotIn("generated_from", payload)
        header = payload["field_sources"]
        for key in ("genres", "confidence", "top_predictions", "guidance"):
            self.assertIn(key, header)
            self.assertIn(header[key], PRODUCERS)


if __name__ == "__main__":
    unittest.main()
