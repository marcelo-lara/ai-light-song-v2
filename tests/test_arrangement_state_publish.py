"""v3.2 item 2 — top-level arrangement_state.json is a fused view of
artifacts/arrangement_state.json: every block emitted in order, a monotone
`margin_db`-derived `confidence`, a `null` confidence on the leading block, a
field_sources header covering every row key, no host paths.

Same construction as tests/test_loudness_publish.py — a synthetic artifact
written straight into a tempfile song dir, no pipeline run.
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from analyzer.exceptions import DependencyError
from analyzer.models import PRODUCERS
from analyzer.paths import SongPaths
from analyzer.stages.ui_data import publish_arrangement_state

STEMS = ["bass", "drums", "harmonic", "vocals"]

ARTIFACT = {
    "schema_version": "3.0",
    "generated_from": {"engine": "analyzer.stages.arrangement_state", "reads": "loudness.json"},
    "stems": STEMS,
    "blocks": [
        {"start_s": 0.0, "end_s": 10.0, "playing": STEMS,
         "entered": [], "left": [], "margin_db": None},
        {"start_s": 10.0, "end_s": 20.0, "playing": ["bass", "drums", "harmonic"],
         "entered": [], "left": ["vocals"], "margin_db": 1.0},
        {"start_s": 20.0, "end_s": 30.0, "playing": STEMS,
         "entered": ["vocals"], "left": [], "margin_db": 6.0},
        {"start_s": 30.0, "end_s": 40.0, "playing": ["bass", "drums"],
         "entered": [], "left": ["harmonic", "vocals"], "margin_db": 12.0},
    ],
}


def _no_data_paths(obj) -> bool:
    if isinstance(obj, str):
        return not obj.startswith("/data/")
    if isinstance(obj, dict):
        return all(_no_data_paths(v) for v in obj.values())
    if isinstance(obj, list):
        return all(_no_data_paths(v) for v in obj)
    return True


# fft_bands.vocals.json stand-in — the promoted item-4 sibilance cue reads its
# `presence`/`brilliance` levels and `transient_strength` off this artifact.
FFT_BANDS_VOCALS = {
    "bands": [
        {"id": "sub"}, {"id": "bass"}, {"id": "low_mid"}, {"id": "mid"},
        {"id": "upper_mid"}, {"id": "presence"}, {"id": "brilliance"},
    ],
    "frames": [
        # levels: sub..brilliance. Frames at 1.0/1.05 s are bright + transient
        # (a sung consonant); the 20 s frame is dull (instrument bleed).
        {"time": 1.00, "levels": [0, 0, 0, 0, 0, 0.8, 0.6], "transient_strength": 1.0},
        {"time": 1.05, "levels": [0, 0, 0, 0, 0, 0.8, 0.6], "transient_strength": 1.0},
        {"time": 20.00, "levels": [0, 0, 0, 0, 0, 0.02, 0.0], "transient_strength": 0.0},
    ],
}


def _write_whisperx_artifact(paths: SongPaths, proposal: dict) -> None:
    """v3.6 item 2 — `whisperx_vad` is promoted out of `experiments/`; its
    output now lives at `artifacts/whisperx-vad/whisperx_vad.json`, written by
    the separate `whisperx` Compose service (never by this publish step)."""
    out = paths.artifact("whisperx-vad", "whisperx_vad.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proposal))


def _write_inputs(paths: SongPaths, artifact: dict, bands: dict | None = None, *, whisperx: dict | None = None) -> None:
    paths.artifact("essentia").mkdir(parents=True, exist_ok=True)
    paths.artifact("arrangement_state.json").write_text(json.dumps(artifact))
    paths.artifact("essentia", "fft_bands.vocals.json").write_text(
        json.dumps(bands if bands is not None else FFT_BANDS_VOCALS)
    )
    paths.arrangement_state_output_path.parent.mkdir(parents=True, exist_ok=True)
    # Default: the whisperx service has run and found no phrases — the common
    # case for every test in this file that is not itself about vocals_phrase.
    _write_whisperx_artifact(paths, whisperx if whisperx is not None else {"vocal_phrase": []})


def _publish(artifact: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
        _write_inputs(paths, artifact)
        out = publish_arrangement_state(paths)
        assert out == str(paths.arrangement_state_output_path)
        return json.loads(paths.arrangement_state_output_path.read_text())


ROW_KEYS = ("start_s", "end_s", "playing", "entered", "left", "margin_db", "confidence")


class ArrangementStatePublishTests(unittest.TestCase):
    def test_every_block_emitted_in_order(self) -> None:
        payload = _publish(ARTIFACT)
        self.assertEqual(len(payload["blocks"]), len(ARTIFACT["blocks"]))
        self.assertEqual(
            [b["start_s"] for b in payload["blocks"]],
            [b["start_s"] for b in ARTIFACT["blocks"]],
        )
        for row in payload["blocks"]:
            self.assertEqual(set(row), set(ROW_KEYS))

    def test_confidence_is_monotone_non_decreasing_in_margin_db(self) -> None:
        payload = _publish(ARTIFACT)
        numeric = [b["confidence"] for b in payload["blocks"] if b["margin_db"] is not None]
        self.assertEqual(numeric, sorted(numeric))
        self.assertTrue(all(0.0 <= c <= 1.0 for c in numeric))

    def test_leading_block_has_null_margin_and_null_confidence(self) -> None:
        payload = _publish(ARTIFACT)
        lead = payload["blocks"][0]
        self.assertIsNone(lead["margin_db"])
        self.assertIsNone(lead["confidence"])

    def test_confidence_formula(self) -> None:
        payload = _publish(ARTIFACT)
        by_margin = {b["margin_db"]: b["confidence"] for b in payload["blocks"]}
        self.assertEqual(by_margin[6.0], round(1 - math.exp(-1), 3))
        self.assertEqual(by_margin[6.0], 0.632)

    def test_field_sources_covers_every_row_key(self) -> None:
        header = _publish(ARTIFACT)["field_sources"]
        for key in ROW_KEYS:
            self.assertIn(key, header)
            self.assertEqual(header[key], "arrangement_state")
            self.assertIn(header[key], PRODUCERS)

    def test_payload_shape(self) -> None:
        payload = _publish(ARTIFACT)
        self.assertEqual(payload["stems"], STEMS)
        self.assertEqual(payload["schema_version"], "3.1")
        self.assertEqual(payload["song_name"], "_test_song")

    def test_no_data_paths(self) -> None:
        self.assertTrue(_no_data_paths(_publish(ARTIFACT)))

    def test_empty_blocks_still_validates(self) -> None:
        payload = _publish({**ARTIFACT, "blocks": []})
        self.assertEqual(payload["blocks"], [])
        for key in ROW_KEYS:
            self.assertEqual(payload["field_sources"][key], "arrangement_state")

    def test_publish_raises_when_whisperx_artifact_missing(self) -> None:
        """v3.6 item 2 — no silent fallback: a missing
        `artifacts/whisperx-vad/whisperx_vad.json` (the `whisperx` service has
        not been run for this song) raises rather than publishing a guessed
        or honest-looking-`None` `vocals_phrase`."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
            paths.artifact("essentia").mkdir(parents=True, exist_ok=True)
            paths.artifact("arrangement_state.json").write_text(json.dumps(ARTIFACT))
            paths.artifact("essentia", "fft_bands.vocals.json").write_text(json.dumps(FFT_BANDS_VOCALS))
            paths.arrangement_state_output_path.parent.mkdir(parents=True, exist_ok=True)
            with self.assertRaises(DependencyError) as ctx:
                publish_arrangement_state(paths)
            self.assertIn("docker compose run --rm whisperx --song", str(ctx.exception))


class VocalsPhrasePromotionTests(unittest.TestCase):
    """v3.5 item 7 promotion — the whisperx_vad phrase-proposal artifact,
    when present, is fused into `vocals_phrase` with every span's confidence
    hardcoded 1.0 (operator's rule: a detected phrase is asserted certain)."""

    def _publish_with_cache(self, artifact: dict, proposal: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
            _write_inputs(paths, artifact, whisperx=proposal)
            out = publish_arrangement_state(paths)
            return json.loads(Path(out).read_text())

    def test_spans_promoted_with_confidence_forced_true(self) -> None:
        proposal = {
            "vocal_phrase": [
                {"start": 1.0, "end": 2.5, "confidence": 0.561},
                {"start": 10.0, "end": 12.0, "confidence": 0.976},
            ]
        }
        payload = self._publish_with_cache(ARTIFACT, proposal)
        spans = payload["vocals_phrase"]
        self.assertEqual(
            [(s["start_s"], s["end_s"], s["confidence"]) for s in spans],
            [(1.0, 2.5, 1.0), (10.0, 12.0, 1.0)],
        )
        self.assertEqual(payload["field_sources"]["vocals_phrase"], "whisperx_vad")

    def test_empty_span_list_is_distinct_from_absent_cache(self) -> None:
        payload = self._publish_with_cache(ARTIFACT, {"vocal_phrase": []})
        self.assertEqual(payload["vocals_phrase"], [])
        self.assertEqual(payload["field_sources"]["vocals_phrase"], "whisperx_vad")


class SibilanceDiscriminatorTests(unittest.TestCase):
    """v3.5 item 4 promotion — the sibilance cue only (vibrato/portamento are
    deliberately not promoted). Ported from
    experiments/vocal_voiceness/features.py: score = mean(presence, brilliance)
    * (0.4 + 0.6 * transient_strength)."""

    def test_song_mean_and_per_phrase_value_are_computed(self) -> None:
        proposal = {"vocal_phrase": [
            {"start": 0.9, "end": 1.1, "confidence": 0.9},    # the bright/transient frames
            {"start": 19.9, "end": 20.1, "confidence": 0.9},  # the dull frame
        ]}
        payload = VocalsPhrasePromotionTests()._publish_with_cache(ARTIFACT, proposal)
        bright, dull = payload["vocals_phrase"]
        # mean(0.8, 0.6) = 0.7; 0.7 * (0.4 + 0.6 * 1.0) = 0.7
        self.assertAlmostEqual(bright["sibilance"], 0.7, places=4)
        # mean(0.02, 0.0) = 0.01; 0.01 * (0.4 + 0.6 * 0.0) = 0.004
        self.assertAlmostEqual(dull["sibilance"], 0.004, places=4)
        self.assertGreater(bright["sibilance"], dull["sibilance"])
        self.assertEqual(payload["field_sources"]["vocals_phrase.sibilance"], "vocal_sibilance")
        self.assertEqual(payload["field_sources"]["vocals_sibilance_song_mean"], "vocal_sibilance")

    def test_song_mean_is_the_reference_level_for_the_per_phrase_values(self) -> None:
        payload = _publish(ARTIFACT)
        # (0.7 + 0.7 + 0.004) / 3
        self.assertAlmostEqual(payload["vocals_sibilance_song_mean"], 0.4680, places=3)

    def test_phrase_covering_no_frame_gets_null_not_zero(self) -> None:
        proposal = {"vocal_phrase": [{"start": 100.0, "end": 101.0, "confidence": 0.9}]}
        payload = VocalsPhrasePromotionTests()._publish_with_cache(ARTIFACT, proposal)
        self.assertIsNone(payload["vocals_phrase"][0]["sibilance"])


if __name__ == "__main__":
    unittest.main()
