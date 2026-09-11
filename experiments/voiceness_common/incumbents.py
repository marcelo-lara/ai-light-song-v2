"""The three incumbents every voiceness candidate (items 4-7) is measured
against, wired to `scorer.py`'s exact frame/phrase shape so all three (and
any future candidate) land in one comparable table.

    arrangement_state_incumbent    the shipped claim: `vocals` in
                                    `arrangement_state.json`'s `playing` list,
                                    per block, expanded to the shared 50ms
                                    grid.
    vocal_phrases_incumbent        `experiments/vocal_phrases`'s existing
                                    local-auto-gain hysteresis detector, run
                                    fresh (no cache dependency) and resampled
                                    onto the same grid.
    mix_rms_baseline_incumbent     new, minimal: a fixed threshold on the
                                    already-published, per-song-normalized
                                    mix RMS (`loudness.json`) — no stem, no
                                    hysteresis. The "do nothing clever"
                                    detector any stem-based method must beat.

All three return `(frames, vocal_phrase)` in exactly the shape
`schema.VoicenessProposal` and `scorer.score()` expect, via
`schema.frames_as_tuples` / `schema.phrases_as_dicts`.
"""
from __future__ import annotations

import json

import numpy as np

from . import paths
from .schema import VocalPhrase, VoicenessFrame

FRAME_INTERVAL_S = 0.05  # the shared 50ms grid every incumbent (and future candidate) reports on

#: D2.2 (resolved): fixed, never swept per-song. The naive baseline exists to
#: be beaten, not tuned — a threshold chosen per song would stop being a
#: baseline. Picked against the already per-song-normalized
#: (`per-song-per-source-peak-rms`) `normalized_values` series, so one
#: constant is comparable across songs.
MIX_RMS_THRESHOLD = 0.10
MIN_PHRASE_S = 0.15


def _uniform_grid(duration_s: float, interval_s: float = FRAME_INTERVAL_S) -> list[float]:
    n = max(1, int(round(duration_s / interval_s)))
    return [round(i * interval_s, 3) for i in range(n)]


def _nearest_index(times: np.ndarray, t: float) -> int:
    return int(np.argmin(np.abs(times - t)))


def _runs(active: list[bool], times: list[float]) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    start = None
    for i, a in enumerate(active):
        if a and start is None:
            start = times[i]
        elif not a and start is not None:
            spans.append((start, times[i]))
            start = None
    if start is not None:
        spans.append((start, times[-1] if times else start))
    return spans


def _combine_confidence(a: float | None, b: float | None) -> float | None:
    vals = [v for v in (a, b) if v is not None]
    return sum(vals) / len(vals) if vals else None


def arrangement_state_incumbent(song: str) -> tuple[list[VoicenessFrame], list[VocalPhrase]]:
    """The shipped `vocals` claim: `arrangement_state.json`'s `playing` list
    per block, read from the top-level published file (never the
    `artifacts/` intermediate)."""
    doc = json.loads(paths.arrangement_state_path(song).read_text())
    blocks = doc["blocks"]
    duration = blocks[-1]["end_s"] if blocks else 0.0
    grid = _uniform_grid(duration)

    frames: list[VoicenessFrame] = []
    for t in grid:
        block = next((b for b in blocks if b["start_s"] <= t < b["end_s"]), None)
        if block is None:
            block = blocks[-1] if blocks else None
        if block is None:
            frames.append(VoicenessFrame(time_s=t, voiceness=0.0, confidence=None))
            continue
        voiced = "vocals" in block["playing"]
        frames.append(
            VoicenessFrame(
                time_s=t,
                voiceness=1.0 if voiced else 0.0,
                confidence=block.get("confidence"),
            )
        )

    # Merge adjacent vocals-present blocks (blocks are contiguous, so a merge
    # is valid only when the previous appended phrase's end lines up exactly
    # with this block's start — i.e. no non-voiced block sits between them).
    phrases: list[VocalPhrase] = []
    for b in blocks:
        if "vocals" not in b["playing"]:
            continue
        if phrases and abs(phrases[-1].end - b["start_s"]) < 1e-6:
            phrases[-1] = VocalPhrase(
                start=phrases[-1].start,
                end=b["end_s"],
                confidence=_combine_confidence(phrases[-1].confidence, b.get("confidence")),
            )
        else:
            phrases.append(VocalPhrase(start=b["start_s"], end=b["end_s"], confidence=b.get("confidence")))
    return frames, phrases


def vocal_phrases_incumbent(song: str) -> tuple[list[VoicenessFrame], list[VocalPhrase]]:
    """`experiments/vocal_phrases`'s hysteresis-over-vocals-stem detector,
    imported directly (experiment-to-experiment, not `src/`-to-
    `experiments/` — allowed) and run fresh so this has no dependency on that
    experiment's own `cache/` being populated."""
    from experiments.vocal_phrases import detector as vp_detector

    env = vp_detector.compute_envelope(song)
    derived = vp_detector.derive_phrases(env)

    times = np.array(env.times)
    ratio = np.array(env.ratio)
    active = vp_detector._hysteresis_active(ratio, vp_detector.ON_RATIO, vp_detector.OFF_RATIO)

    duration = env.times[-1] if env.times else 0.0
    grid = _uniform_grid(duration)
    frames: list[VoicenessFrame] = []
    for t in grid:
        if len(times) == 0:
            frames.append(VoicenessFrame(time_s=t, voiceness=0.0, confidence=None))
            continue
        idx = _nearest_index(times, t)
        voiced = bool(active[idx])
        # No per-frame confidence in this detector — only the derived
        # phrase carries one. Honest `None`, not a guess.
        frames.append(VoicenessFrame(time_s=t, voiceness=1.0 if voiced else 0.0, confidence=None))

    phrases = [
        VocalPhrase(start=p["start"], end=p["end"], confidence=p.get("confidence"))
        for p in derived["vocal_phrases"]
    ]
    return frames, phrases


def mix_rms_baseline_incumbent(
    song: str, threshold: float = MIX_RMS_THRESHOLD
) -> tuple[list[VoicenessFrame], list[VocalPhrase]]:
    """Fixed threshold on the published, already per-song-normalized mix RMS
    (`loudness.json`, `mix` source) — no stem, no hysteresis. The "do nothing
    clever" baseline any real candidate must beat."""
    doc = json.loads(paths.loudness_path(song).read_text())
    order = doc["metadata"]["source_order"]
    mix_i = order.index("mix")
    raw_times = np.array([f["time"] for f in doc["frames"]], dtype=float)
    raw_vals = np.array([f["normalized_values"][mix_i] for f in doc["frames"]], dtype=float)

    duration = doc["metadata"]["duration"]
    grid = _uniform_grid(duration)

    frames: list[VoicenessFrame] = []
    active: list[bool] = []
    for t in grid:
        if len(raw_times) == 0:
            v = 0.0
        else:
            v = float(raw_vals[_nearest_index(raw_times, t)])
        voiced = v >= threshold
        active.append(voiced)
        frames.append(VoicenessFrame(time_s=t, voiceness=1.0 if voiced else 0.0, confidence=None))

    spans = _runs(active, grid)
    phrases = [VocalPhrase(start=s, end=e, confidence=None) for s, e in spans if e - s >= MIN_PHRASE_S]
    return frames, phrases
