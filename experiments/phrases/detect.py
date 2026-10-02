"""Candidates -> phrase edges. Pure functions, no I/O (unit-tested).

An edge is a cluster of candidates (within `CLUSTER_BEATS` of the earliest)
whose distinct evidence groups sum to >= `ACCEPT_SCORE`. Its time is the
physical time of the strongest positional member, moved to the nearest
TRUSTED beat (outside `off_grid_spans`) when one is within `SNAP_MAX_BEATS`;
otherwise it stays at the physical time and the edge is flagged unsnapped.
Phrases are never closer than `MIN_PHRASE_BEATS` beats — a beat count, not a
bar count; no phrase length, grid or downbeat is assumed.

Disagreeing evidence is reported, never forced: `conflicts` on an edge makes
both phrases it touches `resolved: false` (build.py).
"""
from __future__ import annotations

import bisect

ACCEPT_SCORE = 1.5
CLUSTER_BEATS = 3.0
MIN_PHRASE_BEATS = 4.0
SNAP_MAX_BEATS = 1.0
SPREAD_CONFLICT_BEATS = 2.0

#: groups whose time is the moment the change physically happens; the gap /
#: riser / roll *ends* only corroborate.
POSITIONAL_PREFIXES = ("arr:bass", "arr:drums", "presence", "impact")


def _positional(c: dict) -> bool:
    return c["group"].startswith(POSITIONAL_PREFIXES) or c["group"] in ("arr:vocals", "arr:harmonic")


def _position_rank(c: dict) -> int:
    """Whose time wins when sources differ: the 20 ms onset-refined presence
    boundary, then a gestures impact (physical transient), then arrangement_state
    (0.25 s blocks, hard stems before soft)."""
    g = c["group"]
    if g == "presence":
        return 0
    if g == "impact":
        return 1
    return 2 if g in ("arr:bass", "arr:drums") else 3


def cluster(cands: list[dict], beat_len: float) -> list[list[dict]]:
    """Greedy, anchored on the earliest unassigned candidate (no chaining)."""
    out: list[list[dict]] = []
    for c in sorted(cands, key=lambda c: c["t"]):
        if out and c["t"] - out[-1][0]["t"] <= CLUSTER_BEATS * beat_len:
            out[-1].append(c)
        else:
            out.append([c])
    return out


def cluster_score(members: list[dict]) -> float:
    best: dict[str, float] = {}
    for m in members:
        best[m["group"]] = max(best.get(m["group"], 0.0), m["weight"])
    return sum(best.values())


def nearest_trusted(beats: list[float], trusted: list[bool], t: float, max_dist: float) -> float | None:
    ok = [b for b, k in zip(beats, trusted) if k]
    if not ok:
        return None
    i = bisect.bisect_left(ok, t)
    near = [ok[j] for j in (i - 1, i) if 0 <= j < len(ok)]
    best = min(near, key=lambda b: abs(b - t))
    return best if abs(best - t) <= max_dist else None


def conflicts_of(members: list[dict], beat_len: float) -> list[str]:
    out = []
    hard = [m for m in members if m["group"] in ("arr:bass", "arr:drums", "presence")]
    if hard and max(m["t"] for m in hard) - min(m["t"] for m in hard) > SPREAD_CONFLICT_BEATS * beat_len:
        out.append("position: stem sources disagree on the change time by more than two beats")
    for stem in ("bass", "drums", "vocals", "harmonic"):
        dirs = {m["dir"] for m in members if m.get("stem") == stem and m["dir"] in ("enter", "exit")}
        if len(dirs) == 2:
            out.append(f"direction: {stem} both enters and leaves within one cluster")
    return out


def make_edge(members: list[dict], beats: list[float], trusted: list[bool], beat_len: float) -> dict:
    pos = [m for m in members if _positional(m)] or members
    lead = min(pos, key=lambda m: (_position_rank(m), -m["weight"], m["t"]))
    snapped_t = nearest_trusted(beats, trusted, lead["t"], SNAP_MAX_BEATS * beat_len)
    conflicts = conflicts_of(members, beat_len)
    if snapped_t is None:
        conflicts.append("grid: no trusted beat within one beat of the physical change")
    score = cluster_score(members)
    return {
        "t": round(snapped_t if snapped_t is not None else lead["t"], 3),
        "onset_s": round(lead["t"], 3),
        "snapped": snapped_t is not None,
        "score": round(score, 4),
        "kinds": sorted({m["kind"] for m in members}),
        "conflicts": conflicts,
    }


def detect_edges(cands: list[dict], beats: list[float], trusted: list[bool], beat_len: float,
                 duration: float) -> list[dict]:
    edges = []
    for members in cluster(cands, beat_len):
        if cluster_score(members) >= ACCEPT_SCORE:
            edges.append(make_edge(members, beats, trusted, beat_len))
    min_gap = MIN_PHRASE_BEATS * beat_len
    edges = [e for e in edges if e["t"] >= min_gap and duration - e["t"] >= min_gap]
    # drop the weaker of any two edges closer than the minimum phrase length
    while True:
        edges.sort(key=lambda e: e["t"])
        bad = next((i for i in range(len(edges) - 1) if edges[i + 1]["t"] - edges[i]["t"] < min_gap), None)
        if bad is None:
            return edges
        a, b = edges[bad], edges[bad + 1]
        edges.pop(bad if a["score"] < b["score"] else bad + 1)
