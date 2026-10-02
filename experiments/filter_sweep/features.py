"""Per-stem spectral-centroid and loudness series on a half-beat grid.

Centroid = level-weighted mean of log2(band centre Hz) over the 7 published FFT
bands (geometric band centres). Units are octaves, so "depth" is an interval,
not a Hz number. The bands' `levels` are per-band 5th-95th percentile
normalised log power (not linear power), so the centroid is a *relative*
brightness index: reliable for "this stem got brighter/darker", not an
absolute Hz estimate. Silent frames (all bands ~0) yield NaN, never a
fabricated centroid.

Bar length is 4 x the median beat interval (corpus is 4/4 constant tempo);
downbeats / bar numbers are never read (downbeat F1 0.226).
"""
from __future__ import annotations

import json

import numpy as np

from . import paths

LOUDNESS_INDEX = {"mix": 0, "bass": 1, "drums": 2, "harmonic": 3, "vocals": 4}
MIN_TOTAL_LEVEL = 0.15  # sum of 7 band levels below this = silent frame
GRID_PER_BEAT = 2       # grid step = beat / 2; smoothing window = 1 beat


def bar_length(song: str) -> float:
    beats = json.loads(paths.beats_path(song).read_text())["beats"]
    t = np.array(sorted(float(b["time"]) for b in beats))
    if len(t) < 8:
        raise ValueError(f"{song!r}: fewer than 8 beats — cannot derive a bar length")
    return 4.0 * float(np.median(np.diff(t)))


def _centroid_frames(song: str, stem: str) -> tuple[np.ndarray, np.ndarray]:
    data = json.loads(paths.fft_path(song, stem).read_text())
    centres = np.log2(np.sqrt(
        np.array([b["start_hz"] for b in data["bands"]], dtype=float)
        * np.array([b["end_hz"] for b in data["bands"]], dtype=float)))
    times = np.array([f["time"] for f in data["frames"]], dtype=float)
    levels = np.array([f["levels"] for f in data["frames"]], dtype=float)
    total = levels.sum(axis=1)
    cen = np.full(len(times), np.nan)
    ok = total >= MIN_TOTAL_LEVEL
    cen[ok] = (levels[ok] * centres).sum(axis=1) / total[ok]
    return times, cen


def _window_mean(times: np.ndarray, values: np.ndarray, grid: np.ndarray, half_w: float) -> np.ndarray:
    """NaN-aware mean of `values` in [g - half_w, g + half_w] for each grid point."""
    out = np.full(len(grid), np.nan)
    for i, g in enumerate(grid):
        lo = np.searchsorted(times, g - half_w, side="left")
        hi = np.searchsorted(times, g + half_w, side="right")
        seg = values[lo:hi]
        seg = seg[~np.isnan(seg)]
        if len(seg) >= max(1, (hi - lo) // 2):
            out[i] = float(seg.mean())
    return out


def compute_stem(song: str, stem: str, step: float) -> dict:
    ft, cen = _centroid_frames(song, stem)
    loud = json.loads(paths.loudness_path(song).read_text())["frames"]
    lt = np.array([f["time"] for f in loud], dtype=float)
    idx = LOUDNESS_INDEX[stem]
    lv = np.array([f["normalized_values"][idx] for f in loud], dtype=float)
    duration = float(max(ft[-1], lt[-1]))
    grid = np.arange(0.0, duration, step)
    half_w = step  # 1-beat window (step is half a beat)
    return {
        "centroid": _window_mean(ft, cen, grid, half_w),
        "level": _window_mean(lt, lv, grid, half_w),
        "level_p95": float(np.percentile(lv, 95)),
    }


def compute(song: str) -> dict:
    bar = bar_length(song)
    step = bar / 4.0 / GRID_PER_BEAT
    series = {s: compute_stem(song, s, step) for s in paths.STEMS}
    return {"song": song, "bar_length_s": bar, "step_s": step, "series": series}


def to_json(payload: dict) -> dict:
    return {
        "song": payload["song"], "bar_length_s": payload["bar_length_s"], "step_s": payload["step_s"],
        "series": {
            s: {"centroid": [None if np.isnan(v) else round(float(v), 4) for v in d["centroid"]],
                "level": [None if np.isnan(v) else round(float(v), 5) for v in d["level"]],
                "level_p95": d["level_p95"]}
            for s, d in payload["series"].items()
        },
    }


def from_json(raw: dict) -> dict:
    return {
        "song": raw["song"], "bar_length_s": raw["bar_length_s"], "step_s": raw["step_s"],
        "series": {
            s: {"centroid": np.array([np.nan if v is None else v for v in d["centroid"]]),
                "level": np.array([np.nan if v is None else v for v in d["level"]]),
                "level_p95": d["level_p95"]}
            for s, d in raw["series"].items()
        },
    }


def compute_and_cache(song: str) -> dict:
    payload = compute(song)
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(to_json(payload)) + "\n")
    return payload


def load_cache(song: str) -> dict:
    p = paths.cache_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no cache for {song!r} — run `run compute --song {song!r}` first")
    return from_json(json.loads(p.read_text()))
