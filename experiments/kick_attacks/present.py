"""`kick_attacks` / `kick_present` for a window — shared with `experiments/bar_features`.

`kick_attacks` = non-echo events in [start, end). `kick_present` = at least `min_attacks`
of them with confidence >= PRESENT_MIN_CONF: 2 for a bar (one hit is not a groove), 1 for a
half-beat window. A bar shorter than 2 beats (a grid slip) needs one per beat instead.

An attack belongs to the window its *grid-adjusted* time falls in: the physical onset sits
up to ASSIGN_LEAD_S before the beat that the kick is on (band-pass smear, beat tracker
latency), so `time + ASSIGN_LEAD_S` is what is binned.
"""
from __future__ import annotations

PRESENT_MIN_CONF = 0.25
BAR_MIN_ATTACKS = 2
HALF_MIN_ATTACKS = 1
ASSIGN_LEAD_S = 0.05


def window_counts(events: list[dict], start: float, end: float, min_attacks: int) -> tuple[int, bool]:
    kicks = [e for e in events if e["echo_of"] is None and start <= e["time"] + ASSIGN_LEAD_S < end]
    sure = sum(1 for e in kicks if e["confidence"] >= PRESENT_MIN_CONF)
    return len(kicks), sure >= min_attacks
