from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyzer.paths import SongPaths
from analyzer.stages.event_benchmark import benchmark_event_outputs


class EventBenchmarkTests(unittest.TestCase):
    def test_benchmark_event_outputs_matches_reviewed_annotation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            annotation_dir = root / "benchmark_annotations"
            annotation_dir.mkdir(parents=True, exist_ok=True)
            annotation_file = annotation_dir / "Example Song.json"
            annotation_file.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "song_name": "Example Song",
                        "annotation_status": "reviewed",
                        "events": [
                            {"type": "drop_punch", "start_time": 1.0, "end_time": 2.0}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            merged_payload = {
                "events": [
                    {"id": "evt_001", "type": "drop_punch", "start_time": 1.1, "end_time": 2.0}
                ]
            }
            with patch("analyzer.stages.event_benchmark._annotation_path", return_value=annotation_file):
                report = benchmark_event_outputs(paths, merged_payload, {"genres": ["festival_edm"]})
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["matched"], 1)


if __name__ == "__main__":
    unittest.main()