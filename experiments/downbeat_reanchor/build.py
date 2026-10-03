"""Song -> re-anchored bar labels. I/O wrapper over anchors.py."""
from __future__ import annotations

import json

import numpy as np

from . import anchors as A
from . import paths


def load_beats(song: str) -> dict:
    d = json.loads(paths.beats_path(song).read_text())
    beats = d["beats"]
    spans = d.get("off_grid_spans", [])
    times = [float(b["time"]) for b in beats]
    trusted = [not any(s["start"] <= t <= s["end"] for s in spans) for t in times]
    return {"times": times, "trusted": trusted, "beats": beats,
            "beat_len": float(np.median(np.diff(times))) if len(times) > 1 else 0.5}


def load_anchor_inputs(song: str) -> dict:
    tl = json.loads(paths.timeline_path(song).read_text())["events"]
    arr = json.loads(paths.arrangement_path(song).read_text())["blocks"]
    kicks = json.loads(paths.kick_attacks_path(song).read_text())["events"]
    impacts = [{"t": float(e["start_time"]), "confidence": e.get("confidence")} for e in tl if e["type"] == "impact"]
    entries = [{"t": float(b["start_s"]), "confidence": b.get("confidence")} for b in arr
               if set(b.get("entered", [])) & {"bass", "drums"}]
    return {"impacts": impacts, "entries": entries, "kicks": kicks}


def build(song: str, use: tuple[str, ...] = ("kick", "impact", "entry")) -> dict:
    b = load_beats(song)
    inp = load_anchor_inputs(song)
    allin1 = {i: 1 for i, r in enumerate(b["beats"]) if r.get("type") == "downbeat"}
    res = A.reanchor(
        b["times"], b["trusted"], allin1,
        inp["impacts"] if "impact" in use else [], inp["entries"] if "entry" in use else [],
        inp["kicks"] if "kick" in use else [], b["beat_len"])
    res["irregular"] = A.irregular_bars(res["beats"], b["trusted"])
    res["old_irregular"] = A.irregular_bars(
        [{"bar": r["bar"]} for r in b["beats"]], b["trusted"])
    res["times"] = b["times"]
    res["trusted"] = b["trusted"]
    return res


def allin1_downbeats(song: str) -> list[float]:
    """The incumbent: beats.json downbeats with a non-null confidence."""
    b = load_beats(song)
    return [b["times"][i] for i, r in enumerate(b["beats"])
            if r.get("type") == "downbeat" and r.get("downbeat_confidence") is not None]
