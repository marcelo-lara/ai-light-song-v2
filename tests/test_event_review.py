from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.event_review import apply_event_overrides, generate_event_review


class EventReviewTests(unittest.TestCase):
    def test_apply_event_overrides_relabels_and_confirms(self) -> None:
        machine_payload = {
            "schema_version": "1.0",
            "song_name": "Example Song",
            "generated_from": {"source_song_path": "/data/songs/example.mp3"},
            "review_status": "machine",
            "notes": "machine",
            "threshold_profile": "default",
            "metadata": {},
            "events": [
                {
                    "id": "machine_drop_001",
                    "type": "drop",
                    "created_by": "analyzer_event_classifier",
                    "start_time": 1.0,
                    "end_time": 2.0,
                    "confidence": 0.8,
                    "intensity": 0.9,
                    "evidence": {"summary": "summary", "source_windows": [], "metrics": [], "reasons": ["reason"], "rule_names": ["rule"]},
                    "notes": "note",
                }
            ],
        }
        overrides_payload = {
            "operations": [
                {"event_id": "machine_drop_001", "action": "relabel", "type": "drop_punch", "note": "Prefer punch."},
                {"event_id": "machine_drop_001", "action": "confirm", "note": "Confirmed."},
            ]
        }
        merged = apply_event_overrides(machine_payload, overrides_payload)
        self.assertEqual(merged["events"][0]["type"], "drop_punch")
        self.assertEqual(merged["events"][0]["human_override"]["status"], "confirmed")
        self.assertEqual(merged["events"][0]["created_by"], "analyzer_event_classifier")

    def test_generate_event_review_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            machine_payload = {
                "schema_version": "1.0",
                "song_name": "Example Song",
                "generated_from": {"source_song_path": str(paths.song_path)},
                "review_status": "machine",
                "notes": "machine",
                "threshold_profile": "default",
                "metadata": {},
                "events": [
                    {
                        "id": "machine_hook_phrase_001",
                        "type": "hook_phrase",
                        "created_by": "analyzer_phrase_classifier",
                        "start_time": 1.0,
                        "end_time": 2.0,
                        "confidence": 0.61,
                        "intensity": 0.7,
                        "evidence": {"summary": "summary", "source_windows": [], "metrics": [], "reasons": ["reason"], "rule_names": ["rule"]},
                        "notes": "note",
                        "candidates": [{"type": "hook_phrase", "confidence": 0.6, "notes": "top"}, {"type": "anthem_call", "confidence": 0.55, "notes": "alt"}],
                    }
                ],
            }
            result = generate_event_review(paths, machine_payload)
            self.assertEqual(Path(result["review_json"]), paths.review_json_path)
            self.assertEqual(Path(result["review_md"]), paths.review_md_path)
            self.assertEqual(Path(result["overrides"]), paths.overrides_path)
            self.assertTrue(paths.review_json_path.exists())
            self.assertTrue(paths.review_md_path.exists())
            self.assertTrue(paths.overrides_path.exists())
            self.assertIn(str(paths.song_validation_dir), result["review_json"])

            payload = json.loads(paths.review_json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["generated_from"]["dependencies"]["overrides_file"], str(paths.overrides_path))


if __name__ == "__main__":
    unittest.main()