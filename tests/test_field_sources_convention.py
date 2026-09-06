"""v3.1 item 2 — the attribution convention.

Every top-level (delivery-surface) file carries a `field_sources` header whose
keys cover every field it emits, and every producer named — in a header or a
per-row `source` override — is in the closed vocabulary. Fusion reads generated
artifacts only: no publishing code path reads `reference/`.
"""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from analyzer.models import PRODUCERS, Producer, validate_field_sources
from analyzer.stages import ui_data


class ProducerVocabularyTests(unittest.TestCase):
    def test_closed_vocabulary_is_exactly_the_specified_set(self) -> None:
        self.assertEqual(
            PRODUCERS,
            {
                "essentia",
                "allin1",
                "harmonic",
                "omnizart",
                "demucs",
                "gestures",
                "genre",
                "human",
                "inference",
                "unknown",
            },
        )

    def test_unrecognised_producer_is_an_error_not_a_passthrough(self) -> None:
        with self.assertRaises(ValueError):
            validate_field_sources({"x": "moises"}, ["x"], file="test.json")

    def test_header_must_cover_every_emitted_field(self) -> None:
        with self.assertRaises(ValueError):
            validate_field_sources(
                {"a": Producer.ESSENTIA.value}, ["a", "b"], file="test.json"
            )

    def test_reserved_and_exempt_keys_need_no_entry(self) -> None:
        validate_field_sources(
            {"a": "essentia"},
            ["a", "schema_version", "generated_from", "song_name", "debug"],
            file="test.json",
            exempt=["debug"],
        )


class ReferenceGuardTests(unittest.TestCase):
    def test_fusion_stage_never_reads_reference(self) -> None:
        src = inspect.getsource(ui_data)
        self.assertNotIn(".reference(", src)
        self.assertNotIn("reference/", src)
        self.assertNotIn("read_reference", src)


class TopLevelFileHeaderTests(unittest.TestCase):
    """Each top-level file's producer that builds it calls `validate_field_sources`
    — so a missing key or an out-of-vocabulary producer fails the pipeline, not a
    downstream reader."""

    def test_every_publishing_module_validates_its_header(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        for rel in (
            "src/analyzer/stages/ui_data.py",       # beats.json, sections.json
            "src/analyzer/stages/gestures.py",      # song_event_timeline.json
            "src/analyzer/stages/hints.py",         # hints.json
            "src/analyzer/pipeline.py",             # info.json
        ):
            text = (repo / rel).read_text()
            self.assertIn("validate_field_sources", text, rel)


if __name__ == "__main__":
    unittest.main()
