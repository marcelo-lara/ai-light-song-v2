"""v3.4 item 3 — phase-3 `contest-section-function`.

A synthetic published `sections.json` / `loudness.json` / `arrangement_state.json`
written straight into a tempfile song dir (no pipeline run), mirroring
tests/test_arrangement_state_publish.py.

- a quiet `chorus` before a loud `verse` is flagged `function_status:
  "contested"` + `contested_by: "energy"` (label kept, never flipped);
- a loud `chorus` is not flagged;
- the publisher writes the two fields ONLY on flagged rows, and the
  `sections.json` `field_sources` header stays valid (and byte-identical when
  nothing is contested).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.models import PRODUCERS
from analyzer.paths import SongPaths
from analyzer.stages.section_function import contest_section_function

SOURCE_ORDER = ["mix", "bass", "drums", "harmonic", "vocals"]

SECTION_KEYS = (
    "section_id", "start", "end", "label", "description", "function",
    "function_confidence", "function_status", "same_label_as", "confidence",
    "key", "chord_progression",
)

SECTIONS_FIELD_SOURCES = {
    "section_id": "allin1", "start": "allin1", "end": "allin1",
    "label": "human", "description": "human", "function": "allin1",
    "function_confidence": "allin1", "function_status": "allin1",
    "same_label_as": "allin1", "confidence": "allin1",
    "key": "harmonic", "chord_progression": "harmonic",
}


def _section(section_id: str, start: float, end: float, function: str,
             fconf: float = 0.5) -> dict:
    return {
        "section_id": section_id, "start": start, "end": end,
        "label": f"{section_id} {function.title()} ({fconf:.2f})",
        "description": "x", "function": function, "function_confidence": fconf,
        "function_status": "known", "same_label_as": None, "confidence": fconf,
        "key": None, "chord_progression": None,
    }


def _frames(spans: list[tuple[float, float, float, float]]) -> list[dict]:
    """`spans` = [(start, end, mix_rms, drums_rms), ...]; one frame every 0.5 s."""
    frames: list[dict] = []
    for start, end, mix, drums in spans:
        t = start + 0.25
        while t < end:
            values = [mix, 0.05, drums, 0.05, 0.05]
            frames.append({"time": round(t, 3), "values": values,
                           "normalized_values": values})
            t += 0.5
    return frames


def _run(sections: list[dict], frames: list[dict]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = SongPaths(song_path=root / "songs" / "_test_song.mp3",
                          analysis_root=root / "analysis")
        paths.artifact().mkdir(parents=True, exist_ok=True)
        paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)

        paths.sections_output_path.write_text(json.dumps({
            "field_sources": dict(SECTIONS_FIELD_SOURCES),
            "sections": sections,
        }))
        paths.loudness_output_path.write_text(json.dumps({
            "schema_version": "3.0", "song_name": "_test_song",
            "field_sources": {"time": "essentia", "values": "essentia",
                              "normalized_values": "essentia"},
            "metadata": {"sample_rate": 44100, "duration": frames[-1]["time"] + 0.5,
                         "normalization_scope": "x", "source_order": SOURCE_ORDER,
                         "interval_ms": 20, "total_frames": len(frames)},
            "sources": [{"id": s, "label": s, "kind": "mix" if s == "mix" else "stem"}
                        for s in SOURCE_ORDER],
            "frames": frames,
        }))
        paths.arrangement_state_output_path.write_text(json.dumps({
            "schema_version": "3.0", "song_name": "_test_song",
            "field_sources": {}, "stems": ["bass", "drums", "harmonic", "vocals"],
            "blocks": [{"start_s": 0.0, "end_s": 999.0,
                        "playing": ["bass", "drums", "harmonic", "vocals"],
                        "entered": [], "left": [], "margin_db": None,
                        "confidence": None}],
        }))

        artifact = contest_section_function(paths)
        published = json.loads(paths.sections_output_path.read_text())
        return {"artifact": artifact, "published": published,
                "before": json.loads(json.dumps({
                    "field_sources": dict(SECTIONS_FIELD_SOURCES),
                    "sections": sections,
                }))}


class ContestFlagsQuietChorus(unittest.TestCase):
    def setUp(self) -> None:
        # chorus 0-10 with near-silent drums; verse 10-20 with loud drums.
        sections = [
            _section("section-001", 0.0, 10.0, "chorus"),
            _section("section-002", 10.0, 20.0, "verse"),
        ]
        frames = _frames([(0.0, 10.0, 0.10, 0.001), (10.0, 20.0, 0.10, 0.05)])
        self.out = _run(sections, frames)

    def test_artifact_marks_the_chorus_contested(self) -> None:
        rows = {r["section_id"]: r for r in self.out["artifact"]["sections"]}
        self.assertTrue(rows["section-001"]["contested"])
        self.assertEqual(rows["section-001"]["contested_by"], "energy")
        self.assertFalse(rows["section-002"]["contested"])
        self.assertIsNone(rows["section-002"]["contested_by"])
        self.assertIsNone(rows["section-002"]["margin"])  # last section

    def test_published_row_keeps_label_and_gains_two_fields(self) -> None:
        rows = {r["section_id"]: r for r in self.out["published"]["sections"]}
        contested = rows["section-001"]
        self.assertEqual(contested["function"], "chorus")           # label kept
        self.assertEqual(contested["function_confidence"], 0.5)     # untouched
        self.assertEqual(contested["function_status"], "contested")
        self.assertEqual(contested["contested_by"], "energy")
        # the unflagged row is byte-identical to before.
        self.assertEqual(rows["section-002"], self.out["before"]["sections"][1])
        self.assertNotIn("contested_by", rows["section-002"])

    def test_field_sources_header_records_the_producer(self) -> None:
        header = self.out["published"]["field_sources"]
        self.assertEqual(header["function_status"], "section_function")
        self.assertEqual(header["contested_by"], "section_function")
        self.assertIn(header["contested_by"], PRODUCERS)
        # every emitted key is covered.
        for row in self.out["published"]["sections"]:
            self.assertLessEqual(set(row), set(header))


class ContestLeavesLoudChorusAlone(unittest.TestCase):
    def setUp(self) -> None:
        sections = [
            _section("section-001", 0.0, 10.0, "chorus"),
            _section("section-002", 10.0, 20.0, "verse"),
        ]
        frames = _frames([(0.0, 10.0, 0.15, 0.05), (10.0, 20.0, 0.05, 0.001)])
        self.out = _run(sections, frames)

    def test_nothing_contested(self) -> None:
        for r in self.out["artifact"]["sections"]:
            self.assertFalse(r["contested"])

    def test_published_sections_byte_identical(self) -> None:
        self.assertEqual(self.out["published"]["sections"],
                         self.out["before"]["sections"])
        self.assertEqual(self.out["published"]["field_sources"],
                         self.out["before"]["field_sources"])


class ContestIsConservative(unittest.TestCase):
    def test_high_confidence_label_not_contested(self) -> None:
        sections = [
            _section("section-001", 0.0, 10.0, "chorus", fconf=0.95),
            _section("section-002", 10.0, 20.0, "verse"),
        ]
        frames = _frames([(0.0, 10.0, 0.10, 0.001), (10.0, 20.0, 0.10, 0.05)])
        out = _run(sections, frames)
        self.assertFalse(out["artifact"]["sections"][0]["contested"])

    def test_next_section_inst_is_out_of_scope(self) -> None:
        sections = [
            _section("section-001", 0.0, 10.0, "chorus"),
            _section("section-002", 10.0, 20.0, "inst"),
        ]
        frames = _frames([(0.0, 10.0, 0.10, 0.001), (10.0, 20.0, 0.10, 0.05)])
        out = _run(sections, frames)
        self.assertFalse(out["artifact"]["sections"][0]["contested"])


if __name__ == "__main__":
    unittest.main()
