"""Physical-onset boundary refinement.

CLAUDE.md: "the physical onset wins over the nearest grid position — a cue
fired late is a cue missed." The state machine (`state_machine.py`) decides
*that* a section boundary exists, using the bar grid to find where a change
persists; this module then moves that boundary from the bar edge to the
actual entry/exit onset in the 20 ms `loudness.json` frames of whichever stem
changed, searched within one bar either side of the nominal edge (never
wider — a search window that big could latch onto an unrelated later
transient). When no crossing is found in that window the boundary stays at
the bar edge and is reported `resolved: false` — the honest "we didn't find
a sharper onset", never a silent snap.
"""
from __future__ import annotations

import json
from bisect import bisect_left
from dataclasses import dataclass

from . import paths
from .features import STEM_INDEX


@dataclass(frozen=True)
class RefinedBoundary:
    time: float
    resolved: bool


def _series(frames: list[dict], stem: str) -> tuple[list[float], list[float]]:
    idx = STEM_INDEX[stem]
    times = [f["time"] for f in frames]
    values = [f["normalized_values"][idx] for f in frames]
    return times, values


def _nearest_crossing(
    times: list[float], values: list[float], nominal_time: float, midpoint: float, window_s: float
) -> float | None:
    lo = bisect_left(times, nominal_time - window_s)
    hi = bisect_left(times, nominal_time + window_s)
    best: float | None = None
    best_dist = float("inf")
    for i in range(max(lo, 0), min(hi, len(times) - 1)):
        v0, v1 = values[i], values[i + 1]
        if (v0 - midpoint) == 0 or (v0 - midpoint) * (v1 - midpoint) <= 0:
            t0, t1 = times[i], times[i + 1]
            # linear-interpolate the crossing within the frame pair
            if v1 != v0:
                frac = (midpoint - v0) / (v1 - v0)
                frac = min(1.0, max(0.0, frac))
            else:
                frac = 0.0
            t_cross = t0 + frac * (t1 - t0)
            dist = abs(t_cross - nominal_time)
            if dist < best_dist:
                best_dist = dist
                best = t_cross
    return best


def refine_boundary(
    frames: list[dict],
    nominal_time: float,
    changed_stems: list[str],
    level_before: dict[str, float],
    level_after: dict[str, float],
    window_s: float,
) -> RefinedBoundary:
    """`changed_stems`: which of `"bass"`/`"drums"` actually changed
    classification across this boundary (state_machine's before/after coarse
    label owns that decision, not this module). Tries each changed stem's
    20 ms series for a midpoint crossing within `window_s` of the nominal bar
    edge, and keeps the crossing nearest the nominal time across all of
    them."""
    best: float | None = None
    best_dist = float("inf")
    for stem in changed_stems:
        times, values = _series(frames, stem)
        midpoint = (level_before[stem] + level_after[stem]) / 2.0
        t = _nearest_crossing(times, values, nominal_time, midpoint, window_s)
        if t is None:
            continue
        dist = abs(t - nominal_time)
        if dist < best_dist:
            best_dist = dist
            best = t
    if best is None:
        return RefinedBoundary(time=nominal_time, resolved=False)
    return RefinedBoundary(time=best, resolved=True)


def load_frames(song: str) -> list[dict]:
    return json.loads(paths.loudness_path(song).read_text())["frames"]
