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
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
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


if __name__ == "__main__":
    unittest.main()