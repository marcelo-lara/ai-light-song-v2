"""v3.9 item 3 — beat-grid honesty (D3.1: beat times are flagged, never
rewritten). `_compute_off_grid_spans` fits a constant-tempo grid to the
"stable" beats and flags runs of >= 2 consecutive beats that drift more than
`OFF_GRID_TOLERANCE_MS` from it.

A span's `start`/`end` are the bounding STABLE beats either side of the
unstable run, not the run's own first/last (unstable) beat — every
inter-beat interval touching the run is untrustworthy, including the one
leading in and the one leading out (Rapture: IOIs go wrong on the pair
47.53->47.87 and stay wrong through 54.59->54.94, so the span is
47.53-54.94, not the narrower 47.87-54.59).
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from analyzer.paths import SongPaths
from analyzer.stages.ui_data import _compute_off_grid_spans, build_ui_data


def _clean_grid(bpm: float, n: int) -> list[float]:
    period = 60.0 / bpm
    return [round(i * period, 6) for i in range(n)]


class ComputeOffGridSpansTests(unittest.TestCase):
    def test_clean_constant_tempo_grid_has_no_spans(self) -> None:
        times = _clean_grid(120.0, 200)
        self.assertEqual(_compute_off_grid_spans(times, 120.0), [])

    def test_no_bpm_or_too_few_beats_yields_empty_never_none(self) -> None:
        self.assertEqual(_compute_off_grid_spans([0.0, 0.5], 120.0), [])
        self.assertEqual(_compute_off_grid_spans(_clean_grid(120.0, 50), None), [])

    def test_a_fast_region_is_spanned(self) -> None:
        # 160 beats on a clean 120 BPM grid, except a 10-beat stretch (like
        # Rapture's pads-only Pre-Drop, ~167 BPM against the song's 129.84)
        # tracked at a distinctly faster LOCAL rate, then the true grid
        # resumes exactly where it would have anyway — the underlying song
        # never changed tempo, only the tracker's local read of it did, so
        # the beats before/after the glitch are unaffected by it.
        period = 0.5
        n = 160
        times = [round(i * period, 6) for i in range(n)]
        bump_start, bump_len = 100, 10
        fast_period = 0.36
        for offset in range(1, bump_len):
            times[bump_start + offset] = round(times[bump_start] + offset * fast_period, 6)
        # The true grid resumes unaffected right after the glitch.
        for i in range(bump_start + bump_len, n):
            times[i] = round(i * period, 6)

        # times[bump_start] itself is untouched (offset 0), and its incoming
        # IOI from times[bump_start - 1] is still nominal, so it scores
        # stable and IS the span's bounding start (not times[bump_start - 1],
        # which is one beat further back and never itself untrustworthy).
        # times[bump_start + bump_len] is the first beat back on the true
        # grid and bounds the end.
        spans = _compute_off_grid_spans(times, 120.0)
        self.assertEqual(len(spans), 1)
        span = spans[0]
        self.assertEqual(span["start"], times[bump_start])
        self.assertEqual(span["end"], times[bump_start + bump_len])
        self.assertGreater(span["max_deviation_ms"], 70.0)

    def test_a_drifting_region_is_spanned(self) -> None:
        # Clean grid, then a region where the tracker's LOCAL period ramps
        # away from the true tempo and back — a full sine cycle in the local
        # period so the region's own total duration matches what the clean
        # grid would have produced (no artificial reset needed, no
        # discontinuity: the accumulated drift returns to exactly zero by the
        # end of the region on its own, like *Rapture*'s pre-drop-2 grift
        # that self-corrects before the drop hits).
        period = 0.5
        n = 200
        times = [round(i * period, 6) for i in range(n)]
        drift_start, drift_len = 80, 40
        t = times[drift_start]
        amplitude = 0.03  # 6% peak local-tempo deviation — clears GRID_FIT_IOI_TOLERANCE
        for offset in range(1, drift_len):
            local_period = period + amplitude * math.sin(2 * math.pi * offset / drift_len)
            t += local_period
            times[drift_start + offset] = round(t, 6)
        for i in range(drift_start + drift_len, n):
            times[i] = round(i * period, 6)

        spans = _compute_off_grid_spans(times, 120.0)
        self.assertGreaterEqual(len(spans), 1)
        for span in spans:
            self.assertGreater(span["max_deviation_ms"], 70.0)

    def test_a_single_off_grid_beat_is_not_a_span(self) -> None:
        # A lone outlier beat (run length 1) never becomes a span, even if
        # it drifts far past the tolerance.
        period = 0.5
        times = [round(i * period, 6) for i in range(40)]
        times[20] += 0.5  # one beat, way off, then immediately back on-grid
        for i in range(21, 40):
            times[i] = round(i * period, 6)
        spans = _compute_off_grid_spans(sorted(times), 120.0)
        self.assertEqual(spans, [])


def _setup_beats(tmp: str, beats_payload: dict) -> SongPaths:
    root = Path(tmp)
    paths = SongPaths(song_path=root / "songs" / "_test_song.mp3", analysis_root=root / "analysis")
    paths.artifact("essentia").mkdir(parents=True)
    paths.artifact("essentia", "beats.json").write_text(json.dumps(beats_payload))
    paths.artifact("layer_a_harmonic.json").write_text(json.dumps({"global_key": None}))
    paths.artifact("section_segmentation").mkdir(parents=True, exist_ok=True)
    paths.artifact("section_segmentation", "sections.json").write_text(json.dumps({"sections": []}))
    paths.artifact("genre.json").write_text(json.dumps({
        "genres": ["electronic"], "confidence": 0.42,
        "top_predictions": [{"label": "electronic", "confidence": 0.42}],
        "guidance": ["advisory only"],
    }))
    paths.artifact("symbolic_transcription").mkdir(parents=True, exist_ok=True)
    paths.artifact("symbolic_transcription", "drum_events.json").write_text(json.dumps({
        "summary": {"event_count": 0, "kick_count": 0, "snare_count": 0, "hat_count": 0, "unresolved_count": 0},
        "supported_event_types": ["kick", "snare", "hat", "unresolved"],
        "events": [],
    }))
    paths.artifact("essentia", "rms_loudness.json").write_text(json.dumps({
        "sources": [{"id": "mix", "label": "Mix", "path": "/data/x.mp3", "kind": "mix"}],
        "metadata": {"sample_rate": 44100, "duration": 0.01, "normalization_scope": "x",
                     "source_order": ["mix"], "interval_ms": 10},
        "frames": [{"time": 0.005, "values": [0.1], "normalized_values": [0.2]}],
    }))
    paths.sections_output_path.parent.mkdir(parents=True, exist_ok=True)
    return paths


class BuildUiDataOffGridIntegrationTests(unittest.TestCase):
    def test_beats_json_carries_empty_off_grid_spans_and_field_source_on_clean_grid(self) -> None:
        period = 0.5
        beats = [
            {"time": round(i * period, 6), "bar": i // 4 + 1, "beat_in_bar": i % 4 + 1,
             "type": "downbeat" if i % 4 == 0 else "beat", "confidence": 0.9 if i % 4 == 0 else None}
            for i in range(80)
        ]
        payload = {"bpm": 120.0, "beats": beats}
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup_beats(tmp, payload)
            build_ui_data(paths)
            beats_out = json.loads(paths.beats_output_path.read_text())

        self.assertEqual(beats_out["off_grid_spans"], [])
        self.assertEqual(beats_out["field_sources"]["off_grid_spans"], "beat_grid_fit")

    def test_beats_json_flags_a_fast_stretch(self) -> None:
        period = 0.5
        n = 110
        times = [round(i * period, 6) for i in range(n)]
        bump_start, bump_len = 60, 10
        fast_period = 0.36
        for offset in range(1, bump_len):
            times[bump_start + offset] = round(times[bump_start] + offset * fast_period, 6)
        for i in range(bump_start + bump_len, n):
            times[i] = round(i * period, 6)
        beats = [
            {"time": t, "bar": i // 4 + 1, "beat_in_bar": i % 4 + 1,
             "type": "downbeat" if i % 4 == 0 else "beat", "confidence": 0.9 if i % 4 == 0 else None}
            for i, t in enumerate(times)
        ]
        payload = {"bpm": 120.0, "beats": beats}
        with tempfile.TemporaryDirectory() as tmp:
            paths = _setup_beats(tmp, payload)
            build_ui_data(paths)
            beats_out = json.loads(paths.beats_output_path.read_text())

        self.assertGreaterEqual(len(beats_out["off_grid_spans"]), 1)
        # Beat rows are unchanged (D3.1): still essentia's raw times
        # (rounded to the schema's 2 dp, same as every other beat row field).
        self.assertAlmostEqual(beats_out["beats"][60]["time"], times[60], places=2)


if __name__ == "__main__":
    unittest.main()
