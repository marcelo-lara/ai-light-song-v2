"""v3.11 item 22 — `hint-verdict` stage: per-field verdicts of the pre-analysis
hint against published sections / vocals / bpm (synthetic fixtures)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.exceptions import AnalysisError
from analyzer.paths import SongPaths
from analyzer.stages import hint_verdict as hv


def _ev(value):
    return {"value": value, "basis": "stated" if value is not None else None,
            "source": 0 if value is not None else None, "quote": "q" if value is not None else None}


def _hint(family="edm", drops=None, chorus_is_drop=None, has_build_ups=None, vocals=None, bpm=None, schema="1.1"):
    return {"schema_version": schema, "genre": {"family": family, "bpm": bpm}, "track": {},
            "shape": {"drops": _ev(drops), "chorus_is_drop": _ev(chorus_is_drop),
                      "has_build_ups": _ev(has_build_ups), "vocals": vocals}}


def _sections(funcs, length=10.0, status="known"):
    return {"sections": [{"section_id": f"section-{i + 1:03d}", "start": i * length, "end": (i + 1) * length,
                          "function": f, "function_status": status} for i, f in enumerate(funcs)]}


def _arr(phrases=(), blocks=()):
    return {"blocks": [{"start_s": a, "end_s": b, "playing": p} for a, b, p in blocks],
            "vocals_phrase": [{"start_s": a, "end_s": b} for a, b in phrases]}


def _loud(levels, length=10.0):
    frames = [{"time": i * length + t, "values": [lv, 0, 0, 0, 0]}
              for i, lv in enumerate(levels) for t in (1.0, 5.0)]
    return {"source_order": ["mix", "bass", "drums", "harmonic", "vocals"], "frames": frames}


VC_OK = {"version_mismatch": False, "duration_delta_s": 0.0, "bpm_delta_pct": 0.5}
INFO = {"duration": 100.0, "bpm": 126.0}


def run(hint, funcs, arr=None, loud=None, vc=VC_OK):
    n = len(funcs)
    return hv.compute_verdicts(hint, vc, _sections(funcs), arr or _arr(), loud or _loud([1.0] * n), INFO, "s")


class VerdictTests(unittest.TestCase):
    def test_drops_confirmed_with_drop_break_bridging(self):
        r = run(_hint(drops=1), ["Intro", "Drop", "Drop Break", "Drop", "Outro"])
        row = r["fields"]["drops"]
        self.assertEqual(row["verdict"], "confirmed")
        self.assertEqual(row["evidence"]["drop_runs"], 1)
        self.assertNotIn("start", json.dumps(row))

    def test_drops_refuted_when_none_found_or_zero_expected(self):
        self.assertEqual(run(_hint(drops=2), ["Intro", "Main", "Outro"])["fields"]["drops"]["verdict"], "refuted")
        self.assertEqual(run(_hint(drops=0), ["Intro", "Drop", "Outro"])["fields"]["drops"]["verdict"], "refuted")

    def test_drops_unresolved_on_count_difference_or_unknown_labels(self):
        self.assertEqual(run(_hint(drops=3), ["Drop", "Main", "Drop"])["fields"]["drops"]["verdict"], "unresolved")
        r = hv.compute_verdicts(_hint(drops=1), VC_OK, _sections(["Main", "Main"], status="unknown"),
                                _arr(), _loud([1, 1]), INFO, "s")
        self.assertEqual(r["fields"]["drops"]["verdict"], "unresolved")

    def test_pop_edm_counts_drop_like_chorus(self):
        funcs = ["Intro", "Main", "Chorus", "Main", "Outro"]
        loud = _loud([0.1, 0.3, 0.9, 0.3, 0.1])
        arr = _arr(blocks=[(20.0, 30.0, ["bass", "drums", "vocals"])])
        r = run(_hint(family="pop_edm", drops=1), funcs, arr, loud)
        row = r["fields"]["drops"]
        self.assertEqual(row["verdict"], "confirmed")
        self.assertEqual(row["evidence"]["drop_like_chorus_section_ids"], ["section-003"])
        # edm family never counts the chorus
        r2 = run(_hint(family="edm", drops=1), funcs, arr, loud)
        self.assertEqual(r2["fields"]["drops"]["verdict"], "refuted")
        # a quiet chorus is not drop-like
        r3 = run(_hint(family="pop_edm", drops=1), funcs, arr, _loud([0.9, 0.9, 0.1, 0.9, 0.9]))
        self.assertEqual(r3["fields"]["drops"]["verdict"], "refuted")

    def test_build_ups(self):
        self.assertEqual(run(_hint(has_build_ups=True), ["Main", "Build-Up", "Drop"])["fields"]["has_build_ups"]["verdict"], "confirmed")
        self.assertEqual(run(_hint(has_build_ups=True), ["Main", "Drop"])["fields"]["has_build_ups"]["verdict"], "refuted")
        self.assertEqual(run(_hint(has_build_ups=False), ["Build-Up", "Drop"])["fields"]["has_build_ups"]["verdict"], "refuted")

    def test_chorus_is_drop_uses_vocals_in_drop_sections(self):
        funcs = ["Main", "Drop", "Main", "Drop"]
        sung = _arr(phrases=[(10, 20), (30, 40)])
        self.assertEqual(run(_hint(chorus_is_drop=True), funcs, sung)["fields"]["chorus_is_drop"]["verdict"], "confirmed")
        self.assertEqual(run(_hint(chorus_is_drop=False), funcs, sung)["fields"]["chorus_is_drop"]["verdict"], "refuted")
        mixed = _arr(phrases=[(10, 20)])
        self.assertEqual(run(_hint(chorus_is_drop=True), funcs + ["Drop"], mixed)["fields"]["chorus_is_drop"]["verdict"], "unresolved")
        self.assertEqual(run(_hint(chorus_is_drop=True), ["Main"])["fields"]["chorus_is_drop"]["verdict"], "unresolved")

    def test_vocals_against_phrase_coverage(self):
        f = ["Main"] * 10
        full = _arr(phrases=[(0, 60)])
        self.assertEqual(run(_hint(vocals="full"), f, full)["fields"]["vocals"]["verdict"], "confirmed")
        self.assertEqual(run(_hint(vocals="none"), f, full)["fields"]["vocals"]["verdict"], "refuted")
        self.assertEqual(run(_hint(vocals="chops"), f, full)["fields"]["vocals"]["verdict"], "refuted")
        self.assertEqual(run(_hint(vocals="chops"), f, _arr(phrases=[(0, 10)]))["fields"]["vocals"]["verdict"], "confirmed")
        self.assertEqual(run(_hint(vocals="full"), f, _arr(phrases=[(0, 10)]))["fields"]["vocals"]["verdict"], "unresolved")

    def test_bpm_row_and_null_fields_have_no_row(self):
        r = run(_hint(bpm=126.0), ["Main"])
        self.assertEqual(list(r["fields"]), ["bpm"])
        self.assertEqual(r["fields"]["bpm"]["verdict"], "confirmed")

    def test_gates_write_no_rows(self):
        mm = run(_hint(drops=1), ["Drop"], vc={**VC_OK, "version_mismatch": True})
        self.assertEqual((mm["status"], mm["reason"], mm["fields"]), ("skipped", "version_mismatch", {}))
        self.assertEqual(run(_hint(family="rock", drops=1), ["Drop"])["reason"], "family")
        self.assertEqual(run(_hint(schema="1.0", drops=1), ["Drop"])["reason"], "hint_schema")


class PublishTests(unittest.TestCase):
    def _paths(self, root: Path) -> SongPaths:
        return SongPaths(song_path=root / "S.mp3", analysis_root=root / "analysis")

    def _setup(self, paths, hint, funcs):
        for p, doc in ((paths.sections_output_path, _sections(funcs)), (paths.arrangement_state_output_path, _arr()),
                       (paths.loudness_output_path, _loud([1.0] * len(funcs))), (paths.info_output_path, INFO)):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(doc))
        pre = paths.reference("pre-analysis")
        pre.mkdir(parents=True, exist_ok=True)
        (pre / "structure.json").write_text(json.dumps(hint))
        return pre

    def test_hintless_song_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(Path(tmp))
            self.assertIsNone(hv.publish_hint_verdict(paths))
            self.assertFalse(paths.reference("pre-analysis", "verdict.json").exists())

    def test_requires_version_check_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(Path(tmp))
            self._setup(paths, _hint(drops=1), ["Drop"])
            with self.assertRaises(AnalysisError):
                hv.publish_hint_verdict(paths)

    def test_preserves_version_check_changes_no_other_file_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._paths(Path(tmp))
            pre = self._setup(paths, _hint(drops=1, bpm=126), ["Intro", "Drop"])
            (pre / "verdict.json").write_text(json.dumps({"version_check": VC_OK}))
            before = {p: p.read_bytes() for p in Path(tmp).rglob("*.json") if p.name != "verdict.json"}
            hv.publish_hint_verdict(paths)
            out = json.loads((pre / "verdict.json").read_text())
            self.assertEqual(out["version_check"], VC_OK)
            self.assertEqual(out["verdicts"]["fields"]["drops"]["verdict"], "confirmed")
            first = (pre / "verdict.json").read_bytes()
            hv.publish_hint_verdict(paths)
            self.assertEqual(first, (pre / "verdict.json").read_bytes())
            self.assertEqual(before, {p: p.read_bytes() for p in Path(tmp).rglob("*.json") if p.name != "verdict.json"})


if __name__ == "__main__":
    unittest.main()
