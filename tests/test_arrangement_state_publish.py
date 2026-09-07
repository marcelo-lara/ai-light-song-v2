"""v3.2 item 2 — top-level arrangement_state.json is a fused view of
artifacts/arrangement_state.json: every block emitted in order, a monotone
`margin_db`-derived `confidence`, a `null` confidence on the leading block, a
field_sources header covering every row key, no host paths.

Same construction as tests/test_loudness_publish.py — a synthetic artifact
written straight into a tempfile song dir, no pipeline run.
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from analyzer.models import PRODUCERS
from analyzer.paths import SongPaths
from analyzer.stages.ui_data import publish_arrangement_state

STEMS = ["bass", "drums", "harmonic", "vocals"]

ARTIFACT = {
    "schema_version": "3.0",
    "generated_from": {"engine": "analyzer.stages.arrangement_state", "reads": "loudness.json"},
    "stems": STEMS,
    "blocks": [
        {"start_s": 0.0, "end_s": 10.0, "playing": STEMS,
         "entered": [], "left": [], "margin_db": None},
        {"start_s": 10.0, "end_s": 20.0, "playing": ["bass", "drums", "harmonic"],
         "entered": [], "left": ["vocals"], "margin_db": 1.0},
        {"start_s": 20.0, "end_s": 30.0, "playing": STEMS,
         "entered": ["vocals"], "left": [], "margin_db": 6.0},
        {"start_s": 30.0, "end_s": 40.0, "playing": ["bass", "drums"],
         "entered": [], "left": ["harmonic", "vocals"], "margin_db": 12.0},
    ],
}


def _no_data_paths(obj) -> bool:
    if isinstance(obj, str):
        return not obj.startswith("/data/")
    if isinstance(obj, dict):
        return all(_no_data_paths(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_data_paths(v) for v in obj)
    return True


def _publish(artifact: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
        paths.artifact().mkdir(parents=True, exist_ok=True)
        paths.artifact("arrangement_state.json").write_text(json.dumps(artifact))
        paths.arrangement_state_output_path.parent.mkdir(parents=True, exist_ok=True)
        out = publish_arrangement_state(paths)
        assert out == str(paths.arrangement_state_output_path)
        return json.loads(paths.arrangement_state_output_path.read_text())


ROW_KEYS = ("start_s", "end_s", "playing", "entered", "left", "margin_db", "confidence")


class ArrangementStatePublishTests(unittest.TestCase):
    def test_every_block_emitted_in_order(self) -> None:
        payload = _publish(ARTIFACT)
        self.assertEqual(len(payload["blocks"]), len(ARTIFACT["blocks"]))
        self.assertEqual(
            [b["start_s"] for b in payload["blocks"]],
            [b["start_s"] for b in ARTIFACT["blocks"]],
        )
        for row in payload["blocks"]:
            self.assertEqual(set(row), set(ROW_KEYS))

    def test_confidence_is_monotone_non_decreasing_in_margin_db(self) -> None:
        payload = _publish(ARTIFACT)
        numeric = [b["confidence"] for b in payload["blocks"] if b["margin_db"] is not None]
        self.assertEqual(numeric, sorted(numeric))
        self.assertTrue(all(0.0 <= c <= 1.0 for c in numeric))

    def test_leading_block_has_null_margin_and_null_confidence(self) -> None:
        payload = _publish(ARTIFACT)
        lead = payload["blocks"][0]
        self.assertIsNone(lead["margin_db"])
        self.assertIsNone(lead["confidence"])

    def test_confidence_formula(self) -> None:
        payload = _publish(ARTIFACT)
        by_margin = {b["margin_db"]: b["confidence"] for b in payload["blocks"]}
        self.assertEqual(by_margin[6.0], round(1 - math.exp(-1), 3))
        self.assertEqual(by_margin[6.0], 0.632)

    def test_field_sources_covers_every_row_key(self) -> None:
        header = _publish(ARTIFACT)["field_sources"]
        for key in ROW_KEYS:
            self.assertIn(key, header)
            self.assertEqual(header[key], "arrangement_state")
            self.assertIn(header[key], PRODUCERS)

    def test_payload_shape(self) -> None:
        payload = _publish(ARTIFACT)
        self.assertEqual(payload["stems"], STEMS)
        self.assertEqual(payload["schema_version"], "3.0")
        self.assertEqual(payload["song_name"], "_test_song")

    def test_no_data_paths(self) -> None:
        self.assertTrue(_no_data_paths(_publish(ARTIFACT)))

    def test_empty_blocks_still_validates(self) -> None:
        payload = _publish({**ARTIFACT, "blocks": []})
        self.assertEqual(payload["blocks"], [])
        for key in ROW_KEYS:
            self.assertEqual(payload["field_sources"][key], "arrangement_state")


if __name__ == "__main__":
    unittest.main()
