from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.ui_data import apply_section_function_contest, build_ui_data


def _setup(tmp: str, sections: list[dict]) -> SongPaths:
    root = Path(tmp)
    paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
    paths.artifact("essentia").mkdir(parents=True)
    paths.artifact("essentia", "beats.json").write_text(json.dumps({"beats": [{"time": 0.0, "index": 1, "bar": 1, "beat_in_bar": 1, "type": "downbeat"}]}))
    paths.artifact("layer_a_harmonic.json").write_text(json.dumps({"chords": []}))
    paths.artifact("section_segmentation").mkdir(parents=True, exist_ok=True)
    paths.artifact("section_segmentation", "sections.json").write_text(json.dumps({"sections": sections}))
    # v3.1 items 5-7 — build_ui_data now also publishes top-level views of these.
    paths.artifact("genre.json").write_text(json.dumps({
        "genres": ["electronic"], "confidence": 0.42,
        "top_predictions": [{"label": "electronic", "confidence": 0.42}],
        "guidance": ["advisory only"],
    }))
    paths.artifact("symbolic_transcription").mkdir(parents=True, exist_ok=True)
    paths.artifact("symbolic_transcription", "drum_events.json").write_text(json.dumps({
        "summary": {"event_count": 2, "kick_count": 1, "snare_count": 1, "hat_count": 0, "unresolved_count": 0},
        "supported_event_types": ["kick", "snare", "hat", "unresolved"],
        "events": [
            {"time": 0.5, "event_type": "kick", "confidence": None},
            {"time": 1.0, "event_type": "snare", "confidence": None},
        ],
    }))
    paths.artifact("essentia", "rms_loudness.json").write_text(json.dumps({
        "sources": [{"id": "mix", "label": "Mix", "path": "/data/x.mp3", "kind": "mix"}],
        "metadata": {"sample_rate": 44100, "duration": 0.04, "normalization_scope": "x",
                     "source_order": ["mix"], "interval_ms": 10},
        "frames": [
            {"time": 0.005, "values": [0.1], "normalized_values": [0.2]},
            {"time": 0.015, "values": [0.3], "normalized_values": [0.4]},
            {"time": 0.025, "values": [0.5], "normalized_values": [0.6]},
            {"time": 0.035, "values": [0.7], "normalized_values": [0.8]},
        ],
    }))
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    return paths


class SectionJoinTests(unittest.TestCase):
    def test_top_level_sections_carry_section_id_label_and_description(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro",
             "function_confidence": 0.9, "function_status": "known", "same_label_as": None,
             "confidence": 0.9},
            {"section_id": "section-002", "start": 10.0, "end": 20.0, "function": "chorus",
             "function_confidence": 0.4, "function_status": "known", "same_label_as": None,
             "confidence": 0.4},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            payload = json.loads(paths.sections_output_path.read_text())
            rows = payload["sections"]
        self.assertIn("field_sources", payload)
        self.assertEqual([r["section_id"] for r in rows], ["section-001", "section-002"])
        self.assertEqual(rows[0]["label"], "001 Intro (0.90)")
        self.assertEqual(rows[1]["label"], "002 Chorus (0.40)")
        self.assertIn("intro", rows[0]["description"])
        self.assertNotIn("section_character", rows[0])
        self.assertNotIn("form_role", rows[0])

    def test_unknown_function_status_marks_label_unverified(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "verse",
             "function_confidence": 0.2, "function_status": "unknown", "same_label_as": None,
             "confidence": 0.5},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            payload = json.loads(paths.sections_output_path.read_text())
            rows = payload["sections"]
        self.assertIn("field_sources", payload)
        self.assertIn("[unverified]", rows[0]["label"])
        self.assertIn("not trustworthy", rows[0]["description"])

    def test_every_row_carries_function_fields_and_matches_segmentation_order(self) -> None:
        seg_sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro",
             "function_confidence": 0.8, "function_status": "known", "same_label_as": None,
             "confidence": 0.8},
            {"section_id": "section-002", "start": 10.0, "end": 20.0, "function": "verse",
             "function_confidence": 0.6, "function_status": "known", "same_label_as": None,
             "confidence": 0.6},
            {"section_id": "section-003", "start": 20.0, "end": 30.0, "function": "verse",
             "function_confidence": 0.55, "function_status": "known", "same_label_as": "section-002",
             "confidence": 0.55},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, seg_sections)
            build_ui_data(paths)
            rows = json.loads(paths.sections_output_path.read_text())["sections"]
            seg = json.loads(
                paths.artifact("section_segmentation", "sections.json").read_text()
            )["sections"]
        for row in rows:
            self.assertIn("function", row)
            self.assertIn("function_status", row)
        # section_id sequence matches the segmentation artifact one-for-one.
        self.assertEqual(
            [r["section_id"] for r in rows], [s["section_id"] for s in seg]
        )
        self.assertEqual(rows[2]["function"], "verse")
        self.assertEqual(rows[2]["same_label_as"], "section-002")

    def test_degenerate_song_has_unknown_function_status_on_every_row(self) -> None:
        seg_sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": None,
             "function_confidence": None, "function_status": "unknown", "same_label_as": None,
             "confidence": 0.3},
            {"section_id": "section-002", "start": 10.0, "end": 20.0, "function": None,
             "function_confidence": None, "function_status": "unknown", "same_label_as": None,
             "confidence": 0.3},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, seg_sections)
            build_ui_data(paths)
            rows = json.loads(paths.sections_output_path.read_text())["sections"]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row["function_status"], "unknown")

    def test_section_function_contest_is_a_noop_without_the_artifact(self) -> None:
        # v3.4 item 3 — apply_section_function_contest runs after the phase-3
        # stage. With no artifacts/section_function_contest.json it must leave
        # sections.json byte-identical to build_ui_data's output.
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "chorus",
             "function_confidence": 0.5, "function_status": "known", "same_label_as": None,
             "confidence": 0.5},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            before = paths.sections_output_path.read_text()
            apply_section_function_contest(paths)
            after = paths.sections_output_path.read_text()
        self.assertEqual(before, after)
        payload = json.loads(after)
        self.assertNotIn("contested_by", payload["field_sources"])
        self.assertNotIn("contested_by", payload["sections"][0])

    def test_section_function_contest_flags_a_row_from_the_artifact(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "chorus",
             "function_confidence": 0.5, "function_status": "known", "same_label_as": None,
             "confidence": 0.5},
            {"section_id": "section-002", "start": 10.0, "end": 20.0, "function": "verse",
             "function_confidence": 0.8, "function_status": "known", "same_label_as": None,
             "confidence": 0.8},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            paths.artifact("section_function_contest.json").write_text(json.dumps({
                "schema_version": "3.0", "generated_from": {},
                "sections": [
                    {"section_id": "section-001", "function": "chorus", "contested": True,
                     "contested_by": "energy", "margin": 6.2},
                    {"section_id": "section-002", "function": "verse", "contested": False,
                     "contested_by": None, "margin": None},
                ],
            }))
            apply_section_function_contest(paths)
            payload = json.loads(paths.sections_output_path.read_text())
        rows = {r["section_id"]: r for r in payload["sections"]}
        self.assertEqual(rows["section-001"]["function_status"], "contested")
        self.assertEqual(rows["section-001"]["contested_by"], "energy")
        self.assertEqual(rows["section-001"]["function"], "chorus")
        self.assertNotIn("contested_by", rows["section-002"])
        self.assertEqual(payload["field_sources"]["function_status"], "section_function")
        self.assertEqual(payload["field_sources"]["contested_by"], "section_function")

    def test_missing_section_id_fails_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, [{"start": 0.0, "end": 10.0, "function": "intro"}])
            with self.assertRaises(ValueError):
                build_ui_data(paths)

    def test_duplicate_section_id_fails_loudly(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0},
            {"section_id": "section-001", "start": 10.0, "end": 20.0},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            with self.assertRaises(ValueError):
                build_ui_data(paths)

    def test_beats_and_sections_are_objects_with_field_sources_headers(self) -> None:
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro",
             "function_confidence": 0.9, "function_status": "known", "same_label_as": None,
             "confidence": 0.9},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            beats_payload = json.loads(paths.beats_output_path.read_text())
            sections_payload = json.loads(paths.sections_output_path.read_text())

        # Object shape, not a bare array.
        self.assertIsInstance(beats_payload, dict)
        self.assertIsInstance(sections_payload, dict)

        # The header covers every field each row emits.
        beat_row = beats_payload["beats"][0]
        self.assertLessEqual(set(beat_row), set(beats_payload["field_sources"]))
        section_row = sections_payload["sections"][0]
        self.assertLessEqual(set(section_row), set(sections_payload["field_sources"]))

        # The ambiguous `confidence` is gone from beats rows.
        self.assertNotIn("confidence", beat_row)
        self.assertIn("downbeat_confidence", beat_row)

    def test_human_segments_replace_allin1_boundaries_when_present(self) -> None:
        # v3.5 item 10 — reference/human/segments.json present: boundaries,
        # label, description and confidence come from it; function_confidence
        # / function_status / same_label_as are inherited from whichever
        # allin1 section overlaps most.
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 15.0, "function": "intro",
             "function_confidence": 0.9, "function_status": "known", "same_label_as": None,
             "confidence": 0.9},
            {"section_id": "section-002", "start": 15.0, "end": 30.0, "function": "chorus",
             "function_confidence": 0.7, "function_status": "known", "same_label_as": None,
             "confidence": 0.7},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            human_path = paths.reference("human", "segments.json")
            human_path.parent.mkdir(parents=True, exist_ok=True)
            human_path.write_text(json.dumps([
                {"start": 0.0, "end": 14.0, "label": "Intro"},
                {"start": 14.0, "end": 30.0, "label": "Chorus"},
            ]))
            build_ui_data(paths)
            payload = json.loads(paths.sections_output_path.read_text())
            rows = payload["sections"]

        self.assertEqual([r["section_id"] for r in rows], ["section-001", "section-002"])
        self.assertEqual(rows[0]["start"], 0.0)
        self.assertEqual(rows[0]["end"], 14.0)
        self.assertEqual(rows[1]["start"], 14.0)
        self.assertEqual(rows[1]["end"], 30.0)
        self.assertEqual(rows[0]["function"], "Intro")
        self.assertEqual(rows[1]["function"], "Chorus")
        # Boundary confidence is fixed at 0.8 for a human-drawn row, not
        # inherited from allin1.
        self.assertEqual(rows[0]["confidence"], 0.8)
        self.assertEqual(rows[1]["confidence"], 0.8)
        # function_confidence/function_status/same_label_as are inherited by
        # best time-overlap with the allin1 artifact, never invented.
        self.assertEqual(rows[0]["function_confidence"], 0.9)
        self.assertEqual(rows[1]["function_confidence"], 0.7)
        self.assertEqual(payload["field_sources"]["start"], "human")
        self.assertEqual(payload["field_sources"]["confidence"], "human")
        # function's own value is human-sourced (the human label text) when
        # the file exists; only its confidence/status/identity metadata stay
        # allin1's.
        self.assertEqual(payload["field_sources"]["function"], "human")
        self.assertEqual(payload["field_sources"]["function_confidence"], "allin1")
        self.assertEqual(payload["field_sources"]["key"], "harmonic")

    def test_sections_field_sources_default_to_allin1_without_human_file(self) -> None:
        # v3.5 item 10 — no reference/human/segments.json for this song: the
        # file-level default reverts to allin1 (previously hardcoded to
        # "human" even without a backing file).
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 10.0, "function": "intro",
             "function_confidence": 0.9, "function_status": "known", "same_label_as": None,
             "confidence": 0.9},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup(tmp, sections)
            build_ui_data(paths)
            payload = json.loads(paths.sections_output_path.read_text())
        self.assertEqual(payload["field_sources"]["label"], "allin1")
        self.assertEqual(payload["field_sources"]["description"], "allin1")
        self.assertEqual(payload["field_sources"]["start"], "allin1")
        self.assertEqual(payload["field_sources"]["confidence"], "allin1")
        self.assertEqual(payload["field_sources"]["function"], "allin1")


if __name__ == "__main__":
    unittest.main()
