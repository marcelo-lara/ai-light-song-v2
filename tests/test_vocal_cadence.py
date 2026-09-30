"""v3.9 item 1 — `publish-vocal-cadence`, ported from
`experiments/vocal_cadence/tests/` (12/12 on Queen of Kings). Unit tests on
the module's internals (resolve-downbeat, lead-in-bars incl. the
Fill-before-drop case, cadence repeats) plus an end-to-end no-lyrics (D1.1)
and no-text integration test against a synthetic song dir — no pipeline run.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.models import PRODUCERS
from analyzer.paths import SongPaths
from analyzer.stages import vocal_cadence as vc

BPM = 120.0  # beat_period = 0.5s, bar = 2.0s


def _beats(n_bars: int) -> list[vc.BeatRow]:
    beats = []
    t = 0.0
    for bar in range(1, n_bars + 1):
        for beat in range(1, 5):
            conf = 0.9 if beat == 1 else None
            beats.append(vc.BeatRow(time=round(t, 3), bar=bar, beat=beat, downbeat_confidence=conf))
            t += 0.5
    return beats


class ResolveDownbeatTests(unittest.TestCase):
    def test_finds_the_landing_token_and_ignores_the_pickup(self):
        beats = _beats(4)
        line = vc.Line(
            line_id=1, start=3.7, end=4.3,
            onsets=(vc.Onset(-1, 1, 3.7, 3.78), vc.Onset(-1, 1, 3.82, 3.9), vc.Onset(-1, 1, 4.0, 4.3)),
        )
        db = vc._resolve_downbeat(line, beats)
        self.assertIsNotNone(db)
        self.assertEqual((db.bar, db.time), (3, 4.0))

    def test_none_when_no_token_lands_on_a_downbeat(self):
        beats = _beats(4)
        line = vc.Line(line_id=1, start=3.7, end=3.9, onsets=(vc.Onset(-1, 1, 3.7, 3.9),))
        self.assertIsNone(vc._resolve_downbeat(line, beats))


class LeadInBarsTests(unittest.TestCase):
    def test_zero_when_line_lands_on_the_boundary_hit(self):
        beats = _beats(4)
        sections = [
            vc.Section("section-001", start=0.0, end=4.0),
            vc.Section("section-002", start=4.0, end=8.0),
        ]
        lines = [vc.Line(line_id=1, start=4.0, end=4.5, onsets=(vc.Onset(-1, 1, 4.0, 4.5),))]
        result = vc._lead_in_bars(1, sections, lines, beats, BPM)
        self.assertEqual(result["bars"], 0)
        self.assertEqual(result["line_id"], 1)
        self.assertEqual(result["resolve_time_s"], 4.0)

    def test_fill_before_drop_picks_the_continuous_candidate(self):
        """Mirrors Queen of Kings drop 2: a short Fill section sits directly
        in front of the boundary. An even earlier line also resolves inside
        the search window but is disconnected from the boundary by a gap
        >= 1 bar, so it must be rejected in favour of the later,
        vocally-continuous candidate."""
        beats = _beats(7)
        sections = [
            vc.Section("section-001", start=0.0, end=8.0),
            vc.Section("section-002", start=8.0, end=16.0),  # boundary bar 5
        ]
        line_early = vc.Line(  # resolves bar 3 (t=4.0); disconnected from the boundary
            line_id=1, start=3.7, end=4.05,
            onsets=(vc.Onset(-1, 1, 3.7, 3.75), vc.Onset(-1, 1, 4.0, 4.05)),
        )
        line_fill = vc.Line(  # resolves bar 4 (t=6.0); one bar before the boundary
            line_id=2, start=6.06, end=6.3, onsets=(vc.Onset(-1, 2, 6.0, 6.3),),
        )
        line_reaching = vc.Line(  # carries the chain across the boundary
            line_id=3, start=6.5, end=8.5, onsets=(vc.Onset(-1, 3, 6.5, 8.5),),
        )
        all_lines = [line_early, line_fill, line_reaching]

        result = vc._lead_in_bars(1, sections, all_lines, beats, BPM)
        self.assertEqual(result["bars"], -1)
        self.assertEqual(result["line_id"], 2)
        self.assertIsNone(result["reason"])

    def test_null_with_reason_when_nothing_qualifies(self):
        beats = _beats(4)
        sections = [vc.Section("section-001", start=0.0, end=8.0)]
        lines = [vc.Line(line_id=1, start=0.2, end=0.4, onsets=(vc.Onset(-1, 1, 0.2, 0.4),))]
        result = vc._lead_in_bars(0, sections, lines, beats, BPM)
        self.assertIsNone(result["bars"])
        self.assertIsNotNone(result["reason"])


class RestsAndHeldNotesTests(unittest.TestCase):
    def test_rest_and_held_note_detected(self):
        beats = _beats(4)
        sections = [vc.Section("section-001", start=0.0, end=8.0)]
        lines = [
            vc.Line(line_id=1, start=0.0, end=0.5, onsets=(vc.Onset(-1, 1, 0.0, 0.5),)),
            vc.Line(line_id=2, start=2.0, end=3.5, onsets=(vc.Onset(-1, 2, 2.0, 3.5),)),
        ]
        owned = vc._lines_by_section(lines, sections)
        rests, held = vc._rests_and_held_notes(0, None, owned, beats, BPM)
        self.assertEqual(len(rests), 1)
        self.assertEqual(rests[0]["length_beats"], 3.0)
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["length_beats"], 3.0)


class CadenceRepeatsTests(unittest.TestCase):
    def test_finds_offset_and_marks_best(self):
        sections = [
            vc.Section("section-001", start=0.0, end=8.0),
            vc.Section("section-002", start=8.0, end=16.0),
        ]
        pattern_a = [vc.PatternOnset(rel_beats=0.0, abs_time=0.0), vc.PatternOnset(rel_beats=2.0, abs_time=1.0)]
        pattern_b = [vc.PatternOnset(rel_beats=-4.0, abs_time=6.0), vc.PatternOnset(rel_beats=-2.0, abs_time=7.0)]
        repeats = vc._cadence_repeats(sections, [pattern_a, pattern_b], BPM)
        self.assertEqual(repeats[0], [])
        cands = repeats[1]
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0]["section_id"], "section-001")
        self.assertEqual(cands[0]["bar_offset"], -1)
        self.assertTrue(cands[0]["best"])
        self.assertEqual(cands[0]["match_fraction"], 1.0)


class CallTokenTests(unittest.TestCase):
    def test_is_call_token_pure_parens_only(self):
        self.assertTrue(vc._is_call_token("(hey)"))
        self.assertTrue(vc._is_call_token(" (hey) "))
        self.assertFalse(vc._is_call_token("case through the key (hey)"))
        self.assertFalse(vc._is_call_token("hey"))
        self.assertFalse(vc._is_call_token("(hey"))
        self.assertFalse(vc._is_call_token("hey)"))

    def test_build_lines_excludes_markers_and_splits_calls(self):
        raw = [
            {"id": 1, "line_id": 1, "start": 1.0, "end": 1.0, "text": "<SOL>", "confidence": None},
            {"id": 2, "line_id": 1, "start": 1.0, "end": 1.5, "text": "word", "confidence": "0.99"},
            {"id": 3, "line_id": 1, "start": 1.6, "end": 2.0, "text": "(hey)", "confidence": "0.99"},
            {"id": 4, "line_id": 1, "start": 2.0, "end": 2.0, "text": "<EOL>", "confidence": None},
        ]
        lines = vc._build_lines(raw)
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line.token_count, 1)
        self.assertEqual(len(line.calls), 1)
        self.assertEqual(line.calls[0].time, 1.6)

    def test_build_lines_never_retains_text(self):
        raw = [{"id": 1, "line_id": 1, "start": 1.0, "end": 1.5, "text": "secretword", "confidence": "0.99"}]
        lines = vc._build_lines(raw)
        self.assertNotIn("secretword", repr(lines))


class PublishIntegrationTests(unittest.TestCase):
    """End-to-end against a synthetic song dir — no pipeline run."""

    def _make_song(self, tmp: Path, with_lyrics: bool = True) -> SongPaths:
        paths = SongPaths(song_path=Path("/data/songs/Test Song.mp3"), analysis_root=tmp)
        song_dir = paths.song_output_dir
        song_dir.mkdir(parents=True)

        beats = []
        t = 0.0
        for bar in range(1, 9):
            for beat in range(1, 5):
                beats.append({
                    "time": round(t, 3), "bar": bar, "beat": beat, "type": "downbeat" if beat == 1 else "beat",
                    "downbeat_confidence": 0.9 if beat == 1 else None,
                })
                t += 0.5
        (song_dir / "beats.json").write_text(json.dumps({"field_sources": {}, "beats": beats}))
        (song_dir / "info.json").write_text(json.dumps({"schema_version": "3.1", "song_name": "Test Song", "field_sources": {}, "bpm": BPM, "duration": t}))
        sections = [
            {"section_id": "section-001", "start": 0.0, "end": 8.0},
            {"section_id": "section-002", "start": 8.0, "end": 16.0},
        ]
        (song_dir / "sections.json").write_text(json.dumps({"field_sources": {}, "sections": sections}))

        if with_lyrics:
            human_dir = paths.reference("human")
            human_dir.mkdir(parents=True)
            tokens = [
                {"id": 1, "line_id": 1, "start": 0.0, "end": 0.5, "text": "secretword", "confidence": "0.99"},
                {"id": 2, "line_id": 1, "start": 0.6, "end": 0.7, "text": "(hey)", "confidence": "0.99"},
            ]
            (human_dir / "lyrics.json").write_text(json.dumps(tokens))
        return paths

    def test_no_lyrics_writes_honest_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._make_song(Path(tmp), with_lyrics=False)
            out_path = vc.publish_vocal_cadence(paths)
            payload = json.loads(Path(out_path).read_text())
            self.assertIsNone(payload["source"])
            self.assertEqual(payload["lines"], [])
            self.assertEqual(payload["sections"], [])
            self.assertEqual(payload["calls"], [])
            self.assertIsNotNone(payload["reason"])
            self.assertTrue(set(payload["field_sources"].values()) <= PRODUCERS)

    def test_no_text_in_published_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._make_song(Path(tmp), with_lyrics=True)
            out_path = vc.publish_vocal_cadence(paths)
            dumped = Path(out_path).read_text()
            self.assertNotIn("secretword", dumped)
            payload = json.loads(dumped)
            self.assertEqual(payload["source"], "human")
            self.assertEqual(len(payload["calls"]), 1)
            self.assertEqual(payload["calls"][0]["time_s"], 0.6)
            self.assertTrue(set(payload["field_sources"].values()) <= PRODUCERS)


if __name__ == "__main__":
    unittest.main()
