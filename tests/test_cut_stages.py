"""v3.10 item 8 — the cut stages leave no trace: no stage id, no top-level
file, no `sections.json` field, and the operator's old `energy`/`tension`/
`rhythm` keys in `reference/human/segments.json` are ignored, never rewritten."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.pipeline import STAGE_PIPELINE_IDS
from analyzer.stages.ui_data import build_ui_data

REMOVED_STAGES = {
    "derive-energy-layer",
    "extract-energy-features",
    "contest-section-function",
    "section-clues",
    "classify-genre",
    "extract-hpcp-and-key",
}
REMOVED_TOP_LEVEL_FILES = ("genre.json",)
REMOVED_SECTION_FIELDS = {
    "key", "energy", "energy_confidence", "energy_source", "tension",
    "tension_confidence", "tension_source", "rhythm", "contested_by", "impact_alignment",
}
HUMAN_SEGMENTS = [
    {"start": 0.0, "end": 10.0, "label": "Intro", "energy": 2, "tension": 1, "rhythm": {"drums": "quarter"}},
]


def _setup(tmp: str) -> SongPaths:
    root = Path(tmp)
    paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
    paths.artifact("essentia").mkdir(parents=True)
    paths.artifact("essentia", "beats.json").write_text(json.dumps(
        {"bpm": 120.0, "beats": [{"time": 0.0, "index": 1, "bar": 1, "beat_in_bar": 1, "type": "downbeat"}]}))
    paths.artifact("section_segmentation").mkdir(parents=True)
    paths.artifact("section_segmentation", "sections.json").write_text(json.dumps({"sections": [
        {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro",
         "function_confidence": 0.9, "function_status": "known", "same_label_as": None, "confidence": 0.9},
    ]}))
    paths.artifact("symbolic_transcription").mkdir(parents=True)
    paths.artifact("symbolic_transcription", "drum_events.json").write_text(json.dumps({
        "summary": {"event_count": 0, "kick_count": 0, "snare_count": 0, "hat_count": 0, "unresolved_count": 0},
        "supported_event_types": ["kick", "snare", "hat", "unresolved"],
        "events": [],
    }))
    paths.artifact("essentia", "rms_loudness.json").write_text(json.dumps({
        "sources": [{"id": "mix", "label": "Mix", "path": "x.mp3", "kind": "mix"}],
        "metadata": {"sample_rate": 44100, "duration": 0.02, "normalization_scope": "x",
                     "source_order": ["mix"], "interval_ms": 10},
        "frames": [{"time": 0.005, "values": [0.1], "normalized_values": [0.2]}],
    }))
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    return paths


class CutStagesTests(unittest.TestCase):
    def test_removed_stage_ids_are_not_registered(self) -> None:
        self.assertFalse(REMOVED_STAGES & set(STAGE_PIPELINE_IDS))

    def test_publish_writes_none_of_the_removed_files_or_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp)
            human = paths.reference("human", "segments.json")
            human.parent.mkdir(parents=True)
            human.write_text(json.dumps(HUMAN_SEGMENTS))
            human_before = human.read_text()
            for tier in (False, True):
                if tier:
                    human.unlink()
                build_ui_data(paths)
                for name in REMOVED_TOP_LEVEL_FILES:
                    self.assertFalse((paths.song_output_dir / name).exists(), name)
                payload = json.loads(paths.sections_output_path.read_text())
                self.assertTrue(payload["sections"])
                for row in payload["sections"]:
                    self.assertFalse(REMOVED_SECTION_FIELDS & set(row), row)
                self.assertFalse(REMOVED_SECTION_FIELDS & set(payload["field_sources"]))
                if not tier:
                    self.assertEqual(human.read_text(), human_before)


if __name__ == "__main__":
    unittest.main()
