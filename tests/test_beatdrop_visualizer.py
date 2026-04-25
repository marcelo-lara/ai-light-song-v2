from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from analyzer.io import ensure_directory, write_json
from analyzer.paths import SongPaths
from analyzer.stages.beatdrop_visualizer import generate_beatdrop_visual_plan


class BeatdropVisualizerTests(unittest.TestCase):
    def test_generate_beatdrop_visual_plan_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = SongPaths(
                song_path=root / "songs" / "Example Song.mp3",
                artifacts_root=root / "artifacts",
                reference_root=root / "reference",
                output_root=root / "output",
                stems_root=root / "stems",
            )
            ensure_directory(paths.song_path.parent)
            paths.song_path.write_text("", encoding="utf-8")

            write_json(
                paths.artifact("essentia", "beats.json"),
                {
                    "beats": [
                        {"index": 1, "time": 0.0, "bar": 1, "beat_in_bar": 1, "type": "downbeat"},
                        {"index": 2, "time": 1.0, "bar": 1, "beat_in_bar": 2, "type": "beat"},
                    ]
                },
            )
            write_json(
                paths.artifact("essentia", "fft_bands.json"),
                {
                    "bands": [
                        {"id": "bass", "label": "Bass"},
                        {"id": "mid", "label": "Mid"},
                        {"id": "presence", "label": "Presence"},
                    ],
                    "frames": [
                        {"time": 0.0, "levels": [0.2, 0.2, 0.2]},
                        {"time": 0.5, "levels": [0.9, 0.5, 0.3]},
                        {"time": 1.0, "levels": [0.15, 0.1, 0.08]},
                    ],
                },
            )
            write_json(
                paths.artifact("section_segmentation", "sections.json"),
                {
                    "sections": [
                        {"section_id": "section-001", "start": 0.0, "end": 0.95, "section_character": "breath_space"},
                        {"section_id": "section-002", "start": 0.95, "end": 1.8, "section_character": "focal_lift"},
                    ]
                },
            )
            write_json(
                paths.artifact("layer_c_energy.json"),
                {
                    "section_energy": [
                        {"section_id": "section-001", "mean": 0.2},
                        {"section_id": "section-002", "mean": 0.8},
                    ]
                },
            )
            write_json(
                paths.artifact("lighting_events.json"),
                {
                    "lighting_events": [
                        {"event_type": "accent", "time": 1.0},
                    ]
                },
            )
            write_json(
                paths.artifact("music_feature_layers.json"),
                {
                    "lighting_context": {
                        "cue_anchors": [
                            {"id": "anchor_section-001_start", "time_s": 0.0, "anchor_type": "section_start", "section_id": "section-001"},
                            {"id": "anchor_section-002_start", "time_s": 0.95, "anchor_type": "section_start", "section_id": "section-002"},
                        ]
                    }
                },
            )
            write_json(
                paths.timeline_output_path,
                {
                    "events": [
                        {"id": "evt_1", "type": "drop", "start_time": 0.95, "end_time": 1.2}
                    ]
                },
            )

            payload = generate_beatdrop_visual_plan(paths)

            self.assertEqual(payload["song_name"], "Example Song")
            self.assertEqual(len(payload["preset_windows"]), 2)
            self.assertEqual(len(payload["transitions"]), 1)
            self.assertTrue(paths.beatdrop_visual_plan_output_path.exists())
            self.assertTrue(paths.beatdrop_visual_plan_md_output_path.exists())
            self.assertTrue(payload["preset_windows"][0]["candidate_presets"])
            self.assertIn(payload["transitions"][0]["transition_mode"], {"hard_cut", "soft_blend"})


if __name__ == "__main__":
    unittest.main()
