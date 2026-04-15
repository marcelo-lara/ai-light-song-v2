from __future__ import annotations

import unittest

from analyzer.event_contracts import (
    EventContractError,
    canonical_event_types,
    normalize_event_type,
    validate_event_payload,
    validate_song_event_payload,
)


def _sample_event(event_type: str = "drop") -> dict:
    return {
        "id": "evt_001",
        "type": event_type,
        "start_time": 12.0,
        "end_time": 16.0,
        "confidence": 0.92,
        "intensity": 0.88,
        "notes": "Primary release window.",
        "source_layers": ["energy", "sections", "event_features"],
        "evidence": {
            "summary": "Energy and bass activation jump together at the section boundary.",
            "source_windows": [
                {
                    "layer": "energy",
                    "start_time": 11.5,
                    "end_time": 16.0,
                    "ref": "accent_window_03",
                    "metric_names": ["loudness_delta", "bass_energy_delta"]
                }
            ],
            "metrics": [
                {
                    "name": "loudness_delta",
                    "value": 7.4,
                    "threshold": 6.0,
                    "comparator": ">=",
                    "source_layer": "event_features"
                }
            ],
            "reasons": ["Section boundary aligns with release onset."],
            "rule_names": ["drop_energy_release"],
        },
    }


class EventContractsTests(unittest.TestCase):
    def test_canonical_seed_contains_expected_events(self) -> None:
        event_types = canonical_event_types()
        self.assertEqual(len(event_types), 25)
        self.assertIn("drop", event_types)
        self.assertIn("hook_phrase", event_types)
        self.assertIn("vocal_tail", event_types)
        self.assertIn("percussion_break", event_types)

    def test_normalize_event_type_accepts_aliases(self) -> None:
        self.assertEqual(normalize_event_type("build-up"), "build")
        self.assertEqual(normalize_event_type("fake out"), "fake_drop")

    def test_validate_event_payload_normalizes_aliases(self) -> None:
        event = validate_event_payload(_sample_event("explosive_drop"))
        self.assertEqual(event["type"], "drop_explode")

    def test_validate_event_payload_rejects_unknown_types(self) -> None:
        with self.assertRaises(EventContractError):
            validate_event_payload(_sample_event("laser_scream"))

    def test_validate_event_payload_rejects_empty_evidence(self) -> None:
        event = _sample_event()
        event["evidence"] = {}
        with self.assertRaises(EventContractError):
            validate_event_payload(event)

    def test_validate_song_event_payload_accepts_collection(self) -> None:
        payload = {
            "schema_version": "1.0",
            "song_name": "Example Song",
            "generated_from": {"source_song_path": "/data/songs/example.mp3"},
            "events": [_sample_event()],
            "review_status": "machine",
            "notes": "Initial detection pass.",
        }
        validated = validate_song_event_payload(payload)
        self.assertEqual(validated["events"][0]["type"], "drop")


if __name__ == "__main__":
    unittest.main()