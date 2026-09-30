"""Per-bar stem-level aggregation from `loudness.json`, and the cache
`compute` writes / `export` and `score` read.

`loudness.json`'s `normalized_values` are already per-song-normalized
(0..~1ish per stem), so a **fraction of that song's own p95** is the
song-relative on/off threshold the task brief asks for — never an absolute
dB or level number, which would not transfer across songs of different mix
loudness.
"""
from __future__ import annotations

import bisect
import datetime
import json

import numpy as np

from . import bars as bar_mod
from . import paths

STEM_INDEX = {"mix": 0, "bass": 1, "drums": 2, "harmonic": 3, "vocals": 4}


def _load_loudness(song: str) -> dict:
    return json.loads(paths.loudness_path(song).read_text())


def compute_bars(song: str) -> dict:
    """Per-bar mean `normalized_values` for every stem, plus each stem's
    song-level p95 (over bars, not raw frames — a bar-level distribution is
    what the state machine classifies)."""
    loud = _load_loudness(song)
    frames = loud["frames"]
    times = np.array([f["time"] for f in frames], dtype=float)
    stem_series = {
        stem: np.array([f["normalized_values"][idx] for f in frames], dtype=float)
        for stem, idx in STEM_INDEX.items()
    }

    grid = bar_mod.load_bar_grid(song)
    bar_rows = []
    for b in grid:
        lo = bisect.bisect_left(times, b.start)
        hi = bisect.bisect_left(times, b.end)
        if hi <= lo:
            # a bar shorter than one loudness frame (20 ms) — nearest single
            # frame instead of an empty slice, never a fabricated zero.
            lo = max(0, min(len(times) - 1, bisect.bisect_left(times, b.start)))
            hi = lo + 1
        row = {"bar": b.bar, "start": b.start, "end": b.end,
               "downbeat_confidence": b.downbeat_confidence}
        for stem, series in stem_series.items():
            row[f"level_{stem}"] = float(np.mean(series[lo:hi]))
        bar_rows.append(row)

    thresholds = {
        f"{stem}_p95": float(np.percentile(
            [r[f"level_{stem}"] for r in bar_rows], 95
        )) if bar_rows else 0.0
        for stem in STEM_INDEX
    }

    return {
        "song": song,
        "duration": float(json.loads(paths.info_path(song).read_text())["duration"]),
        "bars": bar_rows,
        "thresholds": thresholds,
    }


def compute_and_cache(song: str) -> dict:
    payload = compute_bars(song)
    payload["generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def load_cache(song: str) -> dict:
    p = paths.cache_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no cache for {song!r} — run `run.py compute --song {song!r}` first")
    return json.loads(p.read_text())


def load_or_compute_cache(song: str) -> dict:
    p = paths.cache_path(song)
    if p.exists():
        return json.loads(p.read_text())
    return compute_and_cache(song)
