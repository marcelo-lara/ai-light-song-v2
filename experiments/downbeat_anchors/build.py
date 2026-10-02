"""Song -> anchors + counted downbeats (+ the cheap baselines). I/O wrapper over anchors.py."""
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
    allin1 = {i for i, b in enumerate(beats)
              if b.get("type") == "downbeat" and b.get("downbeat_confidence") is not None}
    return {"times": times, "trusted": trusted, "allin1": allin1, "beats": beats}


def build(song: str, min_score: float = A.ANCHOR_MIN_SCORE, use_fallback: bool = True) -> dict:
    b = load_beats(song)
    phrases = json.loads(paths.phrases_path(song).read_text())["blocks"]
    cand = A.anchor_edges(phrases, min_score)
    located = A.locate(b["times"], cand)
    res = A.count(b["times"], b["trusted"], located, b["allin1"] if use_fallback else set())
    res["anchors"] = located
    res["n_phrase_edges"] = len(phrases) - 1
    res["n_candidate_anchors"] = len(cand)
    res["n_beats"] = len(b["times"])
    res["n_trusted"] = sum(b["trusted"])
    return res


def allin1_downbeats(song: str) -> list[float]:
    """The incumbent: beats.json downbeats with a non-null confidence."""
    b = load_beats(song)
    return [b["times"][i] for i in sorted(b["allin1"])]


def modulo_downbeats(song: str) -> list[float]:
    """Cheapest baseline: every 4th beat from the first beat (the old `beat_in_bar`)."""
    return load_beats(song)["times"][::4]


def kick_phase_downbeats(song: str) -> list[float]:
    """Cheap song-wide baseline: pick the one phase of four whose beats carry the
    most drums-stem sub+bass energy, then every 4th beat from it. No anchors."""
    b = load_beats(song)
    fr = json.loads(paths.drums_fft_path(song).read_text())["frames"]
    ft = np.array([f["time"] for f in fr])
    low = np.array([f["levels"][0] + f["levels"][1] for f in fr])
    t = np.array(b["times"])
    idx = np.clip(np.searchsorted(ft, t), 0, len(ft) - 1)
    e = low[idx]
    sums = [float(e[p::4][np.array(b["trusted"])[p::4]].sum()) for p in range(4)]
    p = int(np.argmax(sums))
    return b["times"][p::4]
