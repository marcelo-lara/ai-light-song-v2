from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.event_ml_train import discover_labeled_songs, infer_event_types_from_hint, train_event_classifier


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_contextual_features(path: Path, hotspot_start: int, hotspot_end: int) -> None:
    rows = []
    for frame_index in range(320):
        signal = 1.0 if hotspot_start <= frame_index <= hotspot_end else 0.0
        rows.append(
            {
                "time_s": round(frame_index * 0.1, 6),
                "normalized": {"energy_score": signal, "vocal_presence": signal / 2.0},
                "derived": {"energy_delta": signal, "accent_intensity": signal},
                "rolling": {
                    "local": {"energy_mean": signal},
                    "phrasal": {"energy_mean": signal},
                    "structural": {"energy_mean": signal},
                },
            }
        )
    _write_json(
        path,
        {
            "schema_version": "1.0",
            "metadata": {"grid_resolution_s": 0.1, "grid_size": len(rows)},
            "feature_catalog": {"normalized": ["energy_score", "vocal_presence"]},
            "features": rows,
        },
    )


class EventMlTrainTests(unittest.TestCase):
    def test_infer_event_types_from_hint_uses_contract_and_keyword_rules(self) -> None:
        hint = {
            "title": "Build up",
            "summary": "Female vocal solo rises into a drop with snare tension.",
        }

        labels = infer_event_types_from_hint(hint)

        self.assertIn("build", labels)
        self.assertIn("drop", labels)
        self.assertIn("vocal_spotlight", labels)
        self.assertIn("percussion_break", labels)

    def test_train_event_classifier_exports_weights_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference_root = root / "reference"
            artifacts_root = root / "artifacts"
            output_dir = root / "models" / "event_classifier"

            for song_name, hotspot, title in (
                ("Cinderella - Ella Lee", (70, 110), "Build"),
                ("What a Feeling - Courtney Storm", (120, 150), "Female vocal"),
                ("ayuni", (180, 210), "Hook pattern build tension"),
            ):
                _write_contextual_features(
                    artifacts_root / song_name / "event_inference" / "contextual_features.json",
                    hotspot_start=hotspot[0],
                    hotspot_end=hotspot[1],
                )
                _write_json(
                    reference_root / song_name / "human" / "human_hints.json",
                    {
                        "song_name": song_name,
                        "human_hints": [
                            {
                                "id": f"hint-{song_name}",
                                "title": title,
                                "start_time": hotspot[0] * 0.1,
                                "end_time": hotspot[1] * 0.1,
                                "summary": "Synthetic labeled region for Story 6.2 tests.",
                                "lighting_hint": "",
                            }
                        ],
                    },
                )

            self.assertEqual(
                discover_labeled_songs(reference_root, artifacts_root),
                ["Cinderella - Ella Lee", "What a Feeling - Courtney Storm", "ayuni"],
            )

            metadata = train_event_classifier(
                songs_root=reference_root,
                artifacts_root=artifacts_root,
                output_dir=output_dir,
                epochs=2,
                batch_size=4,
                threshold=0.4,
                random_seed=3,
                enforce_promotion_gate=False,
            )

            self.assertTrue((output_dir / "1d_cnn_v1.pth").exists())
            self.assertTrue((output_dir / "metadata.json").exists())
            self.assertEqual(metadata["songs"]["validation"], ["ayuni"])
            self.assertEqual(metadata["dataset"]["num_features"], 7)
            self.assertIn("precision", metadata["training"]["best_validation_metrics"])
            self.assertEqual(metadata["artifacts"]["weights_path"], str(output_dir / "1d_cnn_v1.pth"))


if __name__ == "__main__":
    unittest.main()