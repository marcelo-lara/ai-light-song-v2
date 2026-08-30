from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.event_timeline import export_event_timeline


class EventTimelineTests(unittest.TestCase):
    def test_export_event_timeline_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "_test_song.mp3",
                analysis_root=root / "analysis",
            )
            paths.song_output_dir.mkdir(parents=True, exist_ok=True)
            merged_payload = {
                "events": [
                    {
                        "id": "machine_drop_explode_001",
                        "type": "drop_explode",
                        "created_by": "analyzer_event_classifier",
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "confidence": 0.9,
                        "intensity": 0.95,
                        "notes": "Explosive release.",
                        "evidence": {"summary": "Strong accent and release."},
                    }
                ]
            }
            result = export_event_timeline(paths, merged_payload)
            self.assertEqual(Path(result["timeline_json"]), paths.timeline_output_path)
            self.assertEqual(Path(result["timeline_md"]), paths.timeline_md_path)
            self.assertTrue(paths.timeline_output_path.exists())
            self.assertTrue(paths.timeline_md_path.exists())

            payload = json.loads(paths.timeline_output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["events"][0]["created_by"], "analyzer_event_classifier")
            self.assertEqual(payload["generated_from"]["dependencies"]["review_file"], str(paths.review_json_path))
            self.assertEqual(payload["generated_from"]["dependencies"]["overrides_file"], str(paths.overrides_path))


    def _payload(self, events):
        return {"events": [{"created_by": "analyzer_rule_engine", "notes": "n",
                            "evidence": {"summary": "s"}, "confidence": 0.8, **e} for e in events]}

    def test_build_drop_post_drop_folds_into_one_composite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
            paths.song_output_dir.mkdir(parents=True, exist_ok=True)
            payload = self._payload([
                {"id": "b1", "type": "build", "start_time": 20.0, "end_time": 24.0, "intensity": 0.5},
                {"id": "d1", "type": "drop", "start_time": 24.5, "end_time": 25.0, "intensity": 0.95},
                {"id": "p1", "type": "post_drop", "start_time": 25.0, "end_time": 30.0, "intensity": 0.7},
                {"id": "g1", "type": "groove_loop", "start_time": 40.0, "end_time": 50.0, "intensity": 0.6},
            ])
            export_event_timeline(paths, payload)
            events = json.loads(paths.timeline_output_path.read_text())["events"]
            composites = [e for e in events if e.get("composite")]
            self.assertEqual(len(composites), 1)
            composite = composites[0]
            self.assertEqual(composite["start_time"], 20.0)
            self.assertEqual(composite["end_time"], 30.0)
            phase_names = [p["phase"] for p in composite["phases"]]
            self.assertEqual(phase_names, ["build", "tension", "impact", "release"])
            # members are gone as standalone rows
            standalone_ids = {e["id"] for e in events}
            self.assertNotIn("b1", standalone_ids)
            self.assertIn("g1", standalone_ids)

    def test_layer_events_dropped_and_intensity_is_type_banded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
            paths.song_output_dir.mkdir(parents=True, exist_ok=True)
            payload = self._payload([
                {"id": "l1", "type": "layer_add", "start_time": 5.0, "end_time": 5.5, "intensity": 1.0},
                {"id": "l2", "type": "layer_remove", "start_time": 9.0, "end_time": 9.5, "intensity": 1.0},
                {"id": "a1", "type": "atmospheric_plateau", "start_time": 12.0, "end_time": 20.0, "intensity": 1.0},
            ])
            export_event_timeline(paths, payload)
            events = json.loads(paths.timeline_output_path.read_text())["events"]
            types = {e["type"] for e in events}
            self.assertNotIn("layer_add", types)
            self.assertNotIn("layer_remove", types)
            # raw intensity 1.0 for an atmospheric_plateau maps into its low band, not 1.0
            plateau = next(e for e in events if e["type"] == "atmospheric_plateau")
            self.assertLessEqual(plateau["intensity"], 0.30)

    def test_build_without_drop_folds_into_composite_with_no_impact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
            paths.song_output_dir.mkdir(parents=True, exist_ok=True)
            payload = self._payload([
                {"id": "b1", "type": "build", "start_time": 20.0, "end_time": 24.0, "intensity": 0.5},
                {"id": "f1", "type": "fake_drop", "start_time": 25.0, "end_time": 26.0, "intensity": 0.4},
            ])
            export_event_timeline(paths, payload)
            events = json.loads(paths.timeline_output_path.read_text())["events"]
            composites = [e for e in events if e.get("composite")]
            self.assertEqual(len(composites), 1)
            phase_names = [p["phase"] for p in composites[0]["phases"]]
            self.assertNotIn("impact", phase_names)
            self.assertNotIn("release", phase_names)
            self.assertIn("build", phase_names)


if __name__ == "__main__":
    unittest.main()