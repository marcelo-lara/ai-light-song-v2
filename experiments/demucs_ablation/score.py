"""Scores one variant's `vocals.wav` against the exact rule
`analyzer.stages.arrangement_state` uses in production today: a per-stem,
per-song threshold at `PRESENT_DB_BELOW_P98` dB under the stem's own 98th
percentile, gated on `PRESENT_FRACTION` occupancy per `WINDOW_S` window, with
the same `HOLD_S`/`HOLD_AGREEMENT` persistence gate. We import those
functions directly from `src/` (experiments importing `src/` is fine; the
forbidden direction is `src/` importing `experiments/`) rather than
re-deriving the algorithm, per the plan: "the exact rule that is live in
production today."

Production's `detect()` reads the *published* `loudness.json`, which is
htdemucs-only. To score a different variant we build an equivalent synthetic
loudness-shaped doc from that variant's own `vocals.wav` RMS series
(10 ms windows, matching `loudness.py::RMS_INTERVAL_MS`) and feed it through
the same `detect()`/`blocks()` call.

**No ground truth exists yet.** Item 1 added the `type: "vocal"` human-hint
schema but explicitly left marking real spans to the operator
("docs/implementation-plan-v3.5.md` item 1: "Marking real spans on `ayuni`
and a second leaky track is left to the operator"). Checked directly: every
one of the four gold songs and `ayuni` has zero `type == "vocal"` rows in
`reference/human/human_hints.json` in this environment. So
`voiceness_common.scorer.score()`'s `false_vocal_rate` against an EMPTY
marked-span list is mathematically just "fraction of frames the rule calls
voiced" for every song — there is no marked truth to be false *against* yet.
We report that number honestly as `voiced_frame_fraction` (a proxy) rather
than dressing it up as the validated `false_vocal_rate` the plan specifies;
once the operator marks `type: "vocal"` spans, re-running `export` recomputes
the real metric with no code change.
"""
from __future__ import annotations

import math

import numpy as np

from analyzer.stages import arrangement_state as prod

from experiments.voiceness_common import scorer as voiceness_scorer

from . import paths, separate

RMS_INTERVAL_MS = 10  # matches src/analyzer/stages/loudness.py::RMS_INTERVAL_MS


class _FakeSongPaths:
    """Duck-types the two attributes `arrangement_state.detect()` reads off
    `SongPaths`, so the production function can run unmodified against a
    variant's own stem instead of the published `loudness.json`."""

    def __init__(self, song_name: str, loudness_output_path):
        self.song_name = song_name
        self.loudness_output_path = loudness_output_path


def _load_mono(path: str) -> tuple[np.ndarray, int]:
    import soundfile as sf

    audio, sr = sf.read(path, always_2d=True)
    mono = audio.mean(axis=1).astype(np.float64)
    return mono, sr


def _rms_series(audio: np.ndarray, sr: int, window_ms: int = RMS_INTERVAL_MS) -> tuple[list[float], list[float]]:
    window_samples = max(1, int(round(sr * (window_ms / 1000.0))))
    duration_s = len(audio) / sr
    total_frames = max(1, int(math.ceil((duration_s * 1000.0) / window_ms)))
    times: list[float] = []
    values: list[float] = []
    for i in range(total_frames):
        start = i * window_samples
        seg = audio[start : start + window_samples]
        rms = float(np.sqrt(np.mean(np.square(seg)))) if seg.size else 0.0
        times.append(round(i * window_ms / 1000.0, 4))
        values.append(rms)
    return times, values


def _synthetic_loudness_doc(times: list[float], values: list[float], duration_s: float) -> dict:
    return {
        "metadata": {"source_order": ["vocals"], "duration": duration_s},
        "frames": [{"time": t, "values": [v]} for t, v in zip(times, values)],
    }


def voiced_blocks_for_variant(song: str, variant: str) -> tuple[list[dict], float]:
    """Runs the variant's `vocals.wav` through the production
    threshold+hold-gate rule. Returns `(blocks, duration_s)`, `blocks` in the
    exact `arrangement_state.blocks()` shape (`playing` contains `"vocals"`
    or is empty)."""
    stems = separate.cached_stems(song, variant)
    if stems is None:
        raise FileNotFoundError(
            f"no cached stems for song={song!r} variant={variant!r} — run `compute` first"
        )
    vocals_path = stems["vocals"]
    audio, sr = _load_mono(vocals_path)
    duration_s = len(audio) / sr
    times, values = _rms_series(audio, sr)
    doc = _synthetic_loudness_doc(times, values, duration_s)

    import tempfile
    from pathlib import Path

    from analyzer.io import write_json

    with tempfile.TemporaryDirectory() as tmp:
        loudness_path = Path(tmp) / "loudness.json"
        write_json(loudness_path, doc)
        fake_paths = _FakeSongPaths(song, loudness_path)
        result = prod.detect(fake_paths)
        blocks = prod.blocks(result)
    return blocks, duration_s


def score_variant(song: str, variant: str) -> dict:
    """One song x one variant: voiced-frame fraction (== `false_vocal_rate`
    against whatever `type: "vocal"` spans exist today — empty for every
    song in this environment, so this is currently a proxy; see module
    docstring), plus the block-level voiced-duration fraction the refinement
    doc's `ayuni` 40.8 % figure was computed the same way."""
    blocks, duration_s = voiced_blocks_for_variant(song, variant)

    voiced_duration = sum(b["end_s"] - b["start_s"] for b in blocks if "vocals" in b["playing"])
    voiced_duration_fraction = voiced_duration / duration_s if duration_s else 0.0

    # 50ms-grid frames + scorer.score(), for parity with every other
    # voiceness candidate's table shape (items 4-7).
    grid_n = max(1, int(round(duration_s / 0.05)))
    frames: list[tuple[float, float]] = []
    for i in range(grid_n):
        t = round(i * 0.05, 3)
        block = next((b for b in blocks if b["start_s"] <= t < b["end_s"]), None)
        voiced = bool(block and "vocals" in block["playing"])
        frames.append((t, 1.0 if voiced else 0.0))

    hints_path = paths.hints_path(song)
    marked_spans: list[tuple[float, float]] = []
    if hints_path.exists():
        import json

        marked_spans = voiceness_scorer.marked_vocal_spans(json.loads(hints_path.read_text()))

    result = voiceness_scorer.score(frames, phrases=[], marked_spans=marked_spans, duration_s=duration_s)

    return {
        "song": song,
        "variant": variant,
        "duration_s": round(duration_s, 3),
        "n_marked_vocal_spans": len(marked_spans),
        "voiced_duration_fraction": round(voiced_duration_fraction, 4),
        "false_vocal_rate": round(result.false_vocal_rate, 4),
        "is_proxy_no_ground_truth": len(marked_spans) == 0,
        "n_blocks": len(blocks),
    }
