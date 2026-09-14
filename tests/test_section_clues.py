"""v3.6 item 10 — phase-3 `section_clues`.

A synthetic published `sections.json` + prerequisite top-level files written
straight into a tempfile song dir (no pipeline run), mirroring
tests/test_section_function.py. Exercises the precedence chain: `human` >
highest-confidence producer that computed a value > `segments.seed.json`
(`seed_unreviewed`, `confidence: null`) > field absent.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from analyzer.exceptions import AnalysisError
from analyzer.paths import SongPaths
from analyzer.stages.section_clues import section_clues

SOURCE_ORDER = ["mix", "bass", "drums", "harmonic", "vocals"]

SECTIONS_FIELD_SOURCES = {
    "section_id": "allin1", "start": "allin1", "end": "allin1",
    "function": "allin1",
    "function_confidence": "allin1", "function_status": "allin1",
    "same_label_as": "allin1", "confidence": "allin1",
    "key": "harmonic",
}


def _section(section_id: str, start: float, end: float) -> dict:
    return {
        "section_id": section_id, "start": start, "end": end,
        "function": "verse", "function_confidence": 0.5,
        "function_status": "known", "same_label_as": None, "confidence": 0.5,
        "key": None,
    }


def _beats(start: float, end: float, period: float = 0.5) -> list[dict]:
    beats = []
    t = start
    i = 0
    while t < end:
        beats.append({"time": round(t, 3), "beat": (i % 4) + 1,
                      "bar": i // 4 + 1, "type": "beat",
                      "downbeat_confidence": None})
        t += period
        i += 1
    return beats


def _loudness_frames(start: float, end: float, mix_level: float = 0.3) -> list[dict]:
    frames = []
    t = start
    while t < end:
        values = [mix_level, 0.1, 0.1, 0.1, 0.1]
        frames.append({"time": round(t, 3), "values": values,
                       "normalized_values": values})
        t += 0.02
    return frames


def _write_song(
    tmp: str,
    *,
    sections: list[dict],
    loudness_frames: list[dict] | None,
    beats: list[dict] | None,
    human_rows: list[dict] | None = None,
    seed_rows: list[dict] | None = None,
    drum_events: list[dict] | None = None,
) -> SongPaths:
    root = Path(tmp)
    paths = SongPaths(song_path=root / "songs" / "_test_song.mp3",
                      analysis_root=root / "analysis")
    paths.artifact().mkdir(parents=True, exist_ok=True)
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    paths.reference("human").mkdir(parents=True, exist_ok=True)
    paths.artifact("whisperx-vad").mkdir(parents=True, exist_ok=True)

    paths.sections_output_path.write_text(json.dumps({
        "field_sources": dict(SECTIONS_FIELD_SOURCES),
        "sections": sections,
    }))

    if loudness_frames is not None:
        paths.loudness_output_path.write_text(json.dumps({
            "schema_version": "3.1", "song_name": "_test_song",
            "field_sources": {"time": "essentia", "values": "essentia",
                              "normalized_values": "essentia"},
            "source_order": SOURCE_ORDER,
            "interval_ms": 20,
            "frames": loudness_frames,
        }))

    if beats is not None:
        paths.beats_output_path.write_text(json.dumps({
            "field_sources": {}, "beats": beats,
        }))

    paths.arrangement_state_output_path.write_text(json.dumps({
        "schema_version": "3.0", "song_name": "_test_song",
        "field_sources": {}, "stems": ["bass", "drums", "harmonic", "vocals"],
        "blocks": [{"start_s": 0.0, "end_s": 999.0,
                    "playing": ["bass", "drums", "harmonic", "vocals"],
                    "entered": [], "left": [], "margin_db": None,
                    "confidence": None}],
        "vocals_phrase": [],
    }))

    paths.timeline_output_path.write_text(json.dumps({
        "field_sources": {}, "events": [],
    }))

    paths.drum_events_output_path.write_text(json.dumps({
        "schema_version": "3.1", "song_name": "_test_song",
        "field_sources": {"time": "omnizart", "event_type": "omnizart"},
        "summary": {}, "supported_event_types": [], "confidence": None,
        "confidence_reason": "test",
        "events": drum_events or [],
    }))

    paths.artifact("whisperx-vad", "vocal_onsets.json").write_text(json.dumps({
        "schema_version": "3.1", "song_name": "_test_song",
        "generated_from": {}, "metadata": {"total_words": 0}, "words": [],
    }))

    if human_rows is not None:
        (paths.reference("human", "segments.json")).write_text(json.dumps(human_rows))
    if seed_rows is not None:
        (paths.reference("human", "segments.seed.json")).write_text(json.dumps(seed_rows))

    return paths


class PrecedenceChain(unittest.TestCase):
    """One section, energy field, across three runs: human wins, then
    (after removing human) the producer wins, then (after also removing the
    producer's only input — loudness.json) the seed wins with null
    confidence."""

    def test_human_beats_producer_beats_seed(self) -> None:
        sections = [_section("section-001", 0.0, 10.0)]

        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_song(
                tmp, sections=sections,
                loudness_frames=_loudness_frames(0.0, 10.0),
                beats=_beats(0.0, 10.0),
                human_rows=[{"start": 0.0, "end": 10.0, "label": "verse", "energy": 2}],
                seed_rows=[{"start": 0.0, "end": 10.0, "label": "verse", "energy": 5}],
            )
            section_clues(paths)
            row = json.loads(paths.sections_output_path.read_text())["sections"][0]
            self.assertEqual(row["energy"], 2)
            self.assertEqual(row["energy_source"], "human")
            self.assertIsNone(row["energy_confidence"])

    def test_producer_wins_once_human_is_absent(self) -> None:
        sections = [_section("section-001", 0.0, 10.0)]

        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_song(
                tmp, sections=sections,
                loudness_frames=_loudness_frames(0.0, 10.0),
                beats=_beats(0.0, 10.0),
                human_rows=None,
                seed_rows=[{"start": 0.0, "end": 10.0, "label": "verse", "energy": 5}],
            )
            section_clues(paths)
            row = json.loads(paths.sections_output_path.read_text())["sections"][0]
            # single-section quintile always bins to 3, confidence 1.0
            # (rank frac 0.5 -> bin_frac 2.5 -> ceil 3, distance to nearest
            # integer boundary is 0.5 -> conf = 2*0.5 = 1.0).
            self.assertEqual(row["energy"], 3)
            self.assertEqual(row["energy_confidence"], 1.0)
            self.assertNotIn("energy_source", row)  # matches file default

    def test_seed_wins_once_producer_has_nothing(self) -> None:
        sections = [_section("section-001", 0.0, 10.0)]

        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_song(
                tmp, sections=sections,
                loudness_frames=None,  # energy_level cannot compute at all
                beats=_beats(0.0, 10.0),
                human_rows=None,
                seed_rows=[{"start": 0.0, "end": 10.0, "label": "verse", "energy": 5}],
            )
            section_clues(paths)
            row = json.loads(paths.sections_output_path.read_text())["sections"][0]
            self.assertEqual(row["energy"], 5)
            self.assertEqual(row["energy_source"], "seed_unreviewed")
            self.assertIsNone(row["energy_confidence"])


class RhythmVocalsProducerFusion(unittest.TestCase):
    """rhythm.vocals has two candidate producers (rhythm_stem_autocorr,
    rhythm_vocal_onsets) — the higher-confidence one wins and is recorded as
    the row override when it differs from the file default."""

    def test_vocal_onsets_wins_when_more_confident(self) -> None:
        sections = [_section("section-001", 0.0, 10.0)]
        # Beat period 0.5s -> quarter-note words every 0.5s is an exact hit
        # (confidence 1.0), beating a weak/absent autocorrelation candidate
        # (no vocals_phrase overlap -> stem_autocorr reports "none" at 1.0
        # too — so widen the margin with more, cleanly periodic words).
        onsets = [round(t, 3) for t in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]]

        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_song(
                tmp, sections=sections,
                loudness_frames=_loudness_frames(0.0, 10.0),
                beats=_beats(0.0, 10.0),
            )
            # A vocals_phrase overlap makes rhythm_stem_autocorr actually run
            # its autocorrelation (rather than the no-overlap "none"/1.0
            # shortcut) — on this flat/constant loudness curve it degenerates
            # to ("none", 0.0), cleanly beaten by rhythm_vocal_onsets's 1.0.
            arrangement = json.loads(paths.arrangement_state_output_path.read_text())
            arrangement["vocals_phrase"] = [{"start_s": 0.0, "end_s": 10.0, "confidence": 1.0}]
            paths.arrangement_state_output_path.write_text(json.dumps(arrangement))
            paths.artifact("whisperx-vad", "vocal_onsets.json").write_text(json.dumps({
                "schema_version": "3.1", "song_name": "_test_song",
                "generated_from": {}, "metadata": {"total_words": len(onsets)},
                "words": [{"time": t, "word": "w", "confidence": 0.9} for t in onsets],
            }))
            section_clues(paths)
            row = json.loads(paths.sections_output_path.read_text())["sections"][0]
            vocals = row["rhythm"]["vocals"]
            self.assertEqual(vocals["subdivision"], "quarter")
            self.assertEqual(vocals["source"], "rhythm_vocal_onsets")


class MissingVocalOnsetsFailsExplicitly(unittest.TestCase):
    def test_raises_without_vocal_onsets_artifact(self) -> None:
        sections = [_section("section-001", 0.0, 10.0)]
        with tempfile.TemporaryDirectory() as tmp:
            paths = _write_song(
                tmp, sections=sections,
                loudness_frames=_loudness_frames(0.0, 10.0),
                beats=_beats(0.0, 10.0),
            )
            paths.artifact("whisperx-vad", "vocal_onsets.json").unlink()
            with self.assertRaises(AnalysisError):
                section_clues(paths)


if __name__ == "__main__":
    unittest.main()
