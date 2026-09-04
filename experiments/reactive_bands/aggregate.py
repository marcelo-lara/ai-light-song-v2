"""Per-beat / per-bar reduction — the token-budget-respecting projected form."""
from __future__ import annotations

import json

import numpy as np

from . import paths


def load_beats(song: str) -> list[dict]:
    return json.loads(paths.beats_path(song).read_text())


def aggregate_per_beat(times: np.ndarray, ratio_inst: np.ndarray, ratio_att: np.ndarray, beats: list[dict]) -> list[dict]:
    """One row per beat: max/mean instantaneous ratio inside the beat window,
    mean of the damped ratio. Matches the plan's "per-beat and per-bar
    aggregates (max and mean of the instantaneous ratio, mean of the
    attenuated one)"."""
    rows = []
    beat_times = [b["time"] for b in beats]
    for i, b in enumerate(beats):
        t0 = beat_times[i]
        t1 = beat_times[i + 1] if i + 1 < len(beat_times) else t0 + (beat_times[i] - beat_times[i - 1] if i > 0 else 1.0)
        idx = (times >= t0) & (times < t1)
        if not idx.any():
            continue
        rows.append({
            "time": round(t0, 3),
            "beat": b["beat"],
            "bar": b["bar"],
            "max": round(float(ratio_inst[idx].max()), 4),
            "mean": round(float(ratio_inst[idx].mean()), 4),
            "mean_att": round(float(ratio_att[idx].mean()), 4),
        })
    return rows


def aggregate_per_bar(per_beat: list[dict]) -> list[dict]:
    bars: dict[int, list[dict]] = {}
    for row in per_beat:
        bars.setdefault(row["bar"], []).append(row)
    out = []
    for bar, rows in sorted(bars.items()):
        out.append({
            "bar": bar,
            "time": rows[0]["time"],
            "max": round(max(r["max"] for r in rows), 4),
            "mean": round(sum(r["mean"] for r in rows) / len(rows), 4),
            "mean_att": round(sum(r["mean_att"] for r in rows) / len(rows), 4),
        })
    return out
