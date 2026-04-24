from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from analyzer.event_ml_models import EVENT_TYPES, Event1DCNN, parse_contextual_features
from analyzer.paths import SongPaths
from analyzer.stages.event_ml import generate_ml_events


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")


def _write_contextual_features(path: Path) -> None:
    rows = []
    for frame in range(40):
        rows.append(
            {
                "time_s": round(frame * 0.1, 6),
                "normalized": {
                    "energy_score": 0.8 if 10 <= frame <= 20 else 0.2,
                    "onset_density": 0.7 if 10 <= frame <= 20 else 0.2,
                    "spectral_flux": 0.75 if 10 <= frame <= 20 else 0.2,
                },
                "derived": {
                    "bass_att": 0.9 if 10 <= frame <= 20 else 0.2,
                    "bass_att_lma": 0.7,
                    "spectral_flux_lma": 0.6,
                },
                "rolling_2": {"energy_peak": 0.8},
                "rolling_5": {"energy_peak": 0.85},
                "source_refs": {},
            }
        )

    _write_json(
        path,
        {
            "schema_version": "1.0",
            "metadata": {"grid_resolution_s": 0.1, "grid_size": len(rows)},
            "feature_catalog": {"normalized": ["energy_score", "onset_density", "spectral_flux"]},
            "features": rows,
        },
    )


def _write_identifier_hints(path: Path) -> None:
    _write_json(
        path,
        {
            "events": [
                {
                    "id": "event_drop_001",
                    "identifier": "drop",
                    "time_s": 1.5,
                    "start_s": 1.2,
                    "end_s": 2.0,
                    "audit": {
                        "alignment_score": 0.9,
                        "mismatch_flag": False,
                        "support": {"bass_ratio": 1.2, "flux_ratio": 1.25},
                    },
                }
            ]
        },
    )


class EventMlStageTests(unittest.TestCase):
    def test_generate_ml_events_writes_penalty_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )

            contextual_path = paths.artifact("event_inference", "contextual_features.json")
            hints_path = paths.artifact("energy_summary", "hints.json")
            _write_contextual_features(contextual_path)
            _write_identifier_hints(hints_path)

            tensor, _, _ = parse_contextual_features(contextual_path)
            model = Event1DCNN(num_features=tensor.shape[0], num_classes=len(EVENT_TYPES))
            with torch.no_grad():
                for parameter in model.parameters():
                    parameter.zero_()
                drop_index = EVENT_TYPES.index("drop")
                model.fc_head[-1].bias[drop_index] = 6.0

            model_dir = root / "models" / "event_classifier"
            model_dir.mkdir(parents=True, exist_ok=True)
            model_path = model_dir / "1d_cnn_v1.pth"
            penalty_metadata_path = model_dir / "penalty_logic_metadata.json"
            torch.save(model.state_dict(), model_path)

            with patch("analyzer.stages.event_ml.MODEL_DIR", model_dir), patch(
                "analyzer.stages.event_ml.MODEL_PATH", model_path
            ), patch("analyzer.stages.event_ml.PENALTY_METADATA_PATH", penalty_metadata_path):
                payload = generate_ml_events(paths)

            self.assertTrue(payload["events"], "Expected at least one ML event")
            self.assertTrue(any(event["type"] == "drop" for event in payload["events"]))
            self.assertTrue(paths.artifact("event_inference", "saliency_explanations.json").exists())
            self.assertTrue(paths.artifact("event_inference", "penalty_timeline.json").exists())
            self.assertTrue(penalty_metadata_path.exists())


if __name__ == "__main__":
    unittest.main()
