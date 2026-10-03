"""v3.11 item 21 — `version-check` stage: duration (> 5 s) and BPM (> 3 %,
half/double equal) mismatch between the pre-analysis hint and info.json."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.exceptions import AnalysisError
from analyzer.paths import SongPaths
from analyzer.stages import version_check as vc


def _hint(duration=None, bpm=None):
    return {"track": {"version_duration_s": duration}, "genre": {"bpm": bpm}, "schema_version": "1.1"}


INFO = {"duration": 232.41, "bpm": 126.05}


class ComputeTests(unittest.TestCase):
    def check(self, hint):
        return vc.compute_version_check(hint, INFO, "s")

    def test_known_mismatch_songs_flag(self):
        # corpus values: Titanium, Only this moment, Queen of Kings, Underworld
        for hint_dur, dur in ((245, 232.41), (221, 228.22), (160, 146.4), (265, 258.95)):
            r = vc.compute_version_check(_hint(hint_dur), {"duration": dur, "bpm": 120}, "s")
            self.assertTrue(r["version_mismatch"], hint_dur)

    def test_matching_song_does_not_flag(self):
        r = self.check(_hint(234, 126))
        self.assertFalse(r["version_mismatch"])
        self.assertEqual(r["duration_delta_s"], 1.59)

    def test_null_duration_and_bpm_are_not_a_mismatch(self):
        r = self.check(_hint(None, None))
        self.assertEqual(r, {"version_mismatch": False, "duration_delta_s": None, "bpm_delta_pct": None})

    def test_half_and_double_time_bpm_do_not_flag(self):
        self.assertFalse(self.check(_hint(None, 63.0))["version_mismatch"])
        self.assertFalse(self.check(_hint(None, 252.0))["version_mismatch"])

    def test_bpm_off_flags_and_limits_are_strict(self):
        self.assertTrue(self.check(_hint(None, 140))["version_mismatch"])
        self.assertFalse(vc.compute_version_check(_hint(105.0), {"duration": 100.0, "bpm": 100}, "s")["version_mismatch"])

    def test_bad_hint_raises(self):
        with self.assertRaises(AnalysisError):
            vc.compute_version_check({"track": None}, INFO, "s")


class PublishTests(unittest.TestCase):
    def test_missing_hint_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_paths(Path(tmp))
            self.assertIsNone(vc.publish_version_check(paths))
            self.assertFalse(paths.reference("pre-analysis", "verdict.json").exists())

    def test_writes_block_and_preserves_other_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_paths(Path(tmp))
            paths.info_output_path.parent.mkdir(parents=True, exist_ok=True)
            paths.info_output_path.write_text(json.dumps(INFO))
            pre = paths.reference("pre-analysis")
            pre.mkdir(parents=True)
            (pre / "structure.json").write_text(json.dumps(_hint(245, 126)))
            (pre / "verdict.json").write_text(json.dumps({"verdicts": {"drops": "confirmed"}}))
            vc.publish_version_check(paths)
            out = json.loads((pre / "verdict.json").read_text())
            self.assertTrue(out["version_check"]["version_mismatch"])
            self.assertEqual(out["verdicts"], {"drops": "confirmed"})
            first = (pre / "verdict.json").read_bytes()
            vc.publish_version_check(paths)
            self.assertEqual(first, (pre / "verdict.json").read_bytes())

    def test_hint_without_info_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _make_paths(Path(tmp))
            pre = paths.reference("pre-analysis")
            pre.mkdir(parents=True)
            (pre / "structure.json").write_text(json.dumps(_hint(245, 126)))
            with self.assertRaises(AnalysisError):
                vc.publish_version_check(paths)


def _make_paths(root: Path) -> SongPaths:
    return SongPaths(song_path=root / "S.mp3", analysis_root=root / "analysis")


if __name__ == "__main__":
    unittest.main()
