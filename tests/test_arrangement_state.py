"""Pins the ported `detect-arrangement-state` stage against a synthetic,
in-process `loudness.json` (no committed analysis data — same construction as
`tests/test_loudness_publish.py`).

Three behaviours carry the result:
  * a flip that does not hold for `HOLD_S` produces no block;
  * a flip that does hold is reported at the unsmoothed 250 ms edge, not the
    window centre;
  * a flip on the `mix` channel alone produces no block.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.arrangement_state import detect, detect_arrangement_state

STEMS = ["mix", "bass", "drums", "vocals", "harmonic"]
FRAME_DT = 0.020
PRESENT = 1.0
ABSENT = 0.001


def _loudness_doc(duration_s: float, present: Callable[[str, float], bool]) -> dict:
    n = int(round(duration_s / FRAME_DT))
    frames = []
    for i in range(n):
        t = round(i * FRAME_DT, 4)
        vals = [PRESENT if present(s, t) else ABSENT for s in STEMS]
        frames.append({"time": t, "values": vals, "normalized_values": vals})
    return {
        "schema_version": "3.0",
        "song_name": "_test_song",
        "metadata": {
            "source_order": STEMS,
            "duration": round(n * FRAME_DT, 6),
            "interval_ms": 20,
            "total_frames": n,
        },
        "frames": frames,
    }


def _run(present: Callable[[str, float], bool], duration_s: float = 30.0) -> tuple[dict, list, object]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
        paths.loudness_output_path.parent.mkdir(parents=True, exist_ok=True)
        paths.loudness_output_path.write_text(json.dumps(_loudness_doc(duration_s, present)))
        result = detect(paths)
        payload = detect_arrangement_state(paths)
        artifact = json.loads(paths.artifact("arrangement_state.json").read_text())
        return payload, artifact["blocks"], result


class ArrangementStateStageTests(unittest.TestCase):
    def test_brief_flip_below_hold_produces_no_block(self) -> None:
        # bass drops out for 0.5 s only — shorter than HOLD_S (1.5 s).
        def present(stem: str, t: float) -> bool:
            if stem == "bass":
                return not (10.0 <= t < 10.5)
            return True

        _, blocks, result = _run(present)
        self.assertEqual(result.changes, [])
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["start_s"], 0.0)
        self.assertIsNone(blocks[0]["margin_db"])

    def test_sustained_flip_reported_at_unsmoothed_edge(self) -> None:
        # drums enter at exactly t = 10.0 and stay.
        def present(stem: str, t: float) -> bool:
            if stem == "drums":
                return t >= 10.0
            return True

        payload, blocks, result = _run(present)
        self.assertEqual(len(result.changes), 1)
        change = result.changes[0]
        self.assertEqual(change.time, 10.0)  # window edge, not the 10.125 centre
        self.assertEqual(change.entered, ["drums"])
        self.assertEqual([b["start_s"] for b in blocks], [0.0, 10.0])
        self.assertIsNone(blocks[0]["margin_db"])
        self.assertIsInstance(blocks[1]["margin_db"], float)
        self.assertEqual(blocks[1]["entered"], ["drums"])
        self.assertEqual(payload["generated_from"]["reads"], "loudness.json")
        self.assertEqual(payload["schema_version"], "3.0")

    def test_mix_only_flip_produces_no_block(self) -> None:
        # the mix channel drops out for a sustained span; every real stem is
        # constant. The mix is a sum and must never trigger a change.
        def present(stem: str, t: float) -> bool:
            if stem == "mix":
                return not (10.0 <= t < 20.0)
            return True

        _, blocks, result = _run(present)
        self.assertEqual(result.changes, [])
        self.assertEqual(len(blocks), 1)


if __name__ == "__main__":
    unittest.main()
