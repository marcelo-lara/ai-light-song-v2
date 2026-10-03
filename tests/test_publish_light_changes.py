"""v3.12 item 33 — `publish-light-changes`: `light_change` timeline rows and top-level
`bar_features.json`; the MCP loader's hard requirement for the new file."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from analyzer.exceptions import AnalysisError
from analyzer.paths import SongPaths
from analyzer.stages import publish_light_changes as plc

REPO = Path(__file__).resolve().parents[1]


def _bars():
    return [
        {"bar": i + 1, "start_s": i * 2.0, "end_s": i * 2.0 + 2.0, "irregular": i == 3,
         "brightness": 0.5 + i / 100, "transient_mean": 0.01, "transient_std": 0.02,
         "kick_present": i > 0, "sweep_state": "opening" if i == 2 else None}
        for i in range(6)
    ]


def _point(time, bar, role, edge):
    return {"time": time, "bar": bar, "beat": 1, "bar_edge_time": edge, "role": role, "confidence": None}


class PublishLightChangesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = SongPaths(root / "songs" / "S.mp3", root / "analysis")

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))

    def test_publish_end_to_end_is_idempotent(self):
        p = self.paths
        self._write(p.sections_output_path, {"sections": [{"section_id": "section-001", "start": 0.0, "end": 12.0}]})
        self._write(p.timeline_output_path, {"field_sources": {"type": "gestures", "start_time": "gestures",
                    "end_time": "gestures", "confidence": "gestures", "section_id": "sections"},
                    "events": [{"type": "impact", "start_time": 4.0, "end_time": 4.5, "confidence": 0.9,
                                "section_id": "section-001"}]})
        self._write(p.artifact("light_changes", "light_changes.json"), {"points": [_point(4.0, 3, "drop", 4.0)]})
        self._write(p.artifact("light_changes", "bar_features.json"), {"bars": _bars()})
        plc.publish_light_changes(p)
        first = p.timeline_output_path.read_text()
        plc.publish_light_changes(p)
        self.assertEqual(first, p.timeline_output_path.read_text())
        doc = json.loads(first)
        self.assertEqual([e["type"] for e in doc["events"]], ["light_change", "impact"])
        self.assertEqual(doc["field_sources"]["role"], "light_changes")
        self.assertIsNone(doc["events"][0]["confidence"])
        bf = json.loads(p.bar_features_output_path.read_text())
        self.assertNotIn("generated_from", bf)
        self.assertEqual(bf["field_sources"]["light_change_role"], "light_changes")
        self.assertEqual(len(bf["bars"]), 6)

    def test_missing_input_raises(self):
        with self.assertRaises(AnalysisError):
            plc.publish_light_changes(self.paths)

    def test_rows_and_bars(self):
        sections = [{"section_id": "section-001", "start": 0.0, "end": 5.0},
                    {"section_id": "section-002", "start": 6.0, "end": 12.0}]
        points = [_point(3.5, 2, "build", 4.0), _point(8.0, 5, "drop", 8.0), _point(5.5, 3, "fill", 6.0)]
        rows = plc.light_change_rows(points, sections)
        self.assertEqual(rows[0], {"type": "light_change", "role": "build", "start_time": 3.5,
                                   "end_time": 3.5, "confidence": None, "section_id": "section-001"})
        self.assertIsNone(rows[2]["section_id"])          # gap between sections: no guess
        bars = plc.bar_feature_rows(_bars(), points)
        self.assertEqual(set(bars[0]), {"bar", "start", "end", "irregular", "brightness",
                                        "transient_density", "kick_present", "sweep_state",
                                        "light_change_role"})
        self.assertEqual([b["light_change_role"] for b in bars], [None, "build", "fill", None, "drop", None])
        self.assertTrue(bars[3]["irregular"])
        self.assertEqual(bars[0]["transient_density"], 0.01)

    def test_missing_column_raises(self):
        bad = _bars()
        del bad[1]["kick_present"]
        with self.assertRaises(AnalysisError):
            plc.bar_feature_rows(bad, [])

    def test_point_outside_every_bar_raises(self):
        with self.assertRaises(AnalysisError):
            plc.bar_feature_rows(_bars(), [_point(99.0, 1, "drop", 99.0)])


class LoaderRequiresBarFeaturesTests(unittest.TestCase):
    def test_missing_bar_features_names_the_file(self):
        sys.path.insert(0, str(REPO / "mcp"))
        try:
            import loaders
        finally:
            sys.path.pop(0)
        self.assertIn("bar_features.json", loaders.REQUIRED_TOP_LEVEL_FILES)
        self.assertEqual(len(loaders.REQUIRED_TOP_LEVEL_FILES), 10)
        with tempfile.TemporaryDirectory() as tmp:
            song = Path(tmp) / "P - S"
            song.mkdir()
            for f in loaders.REQUIRED_TOP_LEVEL_FILES:
                if f != "bar_features.json":
                    (song / f).write_text(json.dumps({}))
            with self.assertRaises(loaders.MissingTopLevelFileError) as cm:
                loaders.resolve_song_dir("P - S", root=Path(tmp))
            self.assertIn("bar_features.json", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
