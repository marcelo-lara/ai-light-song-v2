"""Write `reference/proposals/texture_novelty.json` — the timeline lane input.

Blocks are the segments between predicted texture boundaries from feature set 1
(the measured baseline; `score` shows the other two do not beat it). A proposal
to audition against Human Hints, never ground truth.
"""
from __future__ import annotations

import datetime
import json

import numpy as np

from . import features as feat_mod
from . import novelty as nov
from . import paths

SCHEMA_VERSION = "1.0"
DEFAULT_FEATURE_SET = 1


def export(song: str, feature_set: int = DEFAULT_FEATURE_SET) -> dict:
    cache = feat_mod.load_cache(song)
    times = np.asarray(cache["times"], dtype=float)
    duration = float(cache["duration"][0])
    matrix = feat_mod.feature_matrix(cache, feature_set)
    curve = nov.novelty_curve(matrix)
    bounds = nov.pick_boundaries(times, curve)

    def strength_at(t: float) -> float:
        return round(float(curve[int(np.argmin(np.abs(times - t)))]), 4)

    edges = [0.0, *[float(b) for b in bounds], duration]
    blocks = []
    for i in range(len(edges) - 1):
        blocks.append({
            "start_s": round(edges[i], 3),
            "end_s": round(edges[i + 1], 3),
            "edge_strength": strength_at(edges[i]) if i > 0 else None,
        })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/texture_novelty",
            "engine": "cosine self-similarity + Foote checkerboard novelty (1.0 s half-window)",
            "feature_set": FEATURE_SET_LABEL[feature_set],
            "params": {"half_window_s": nov.HALF_WINDOW_S, "min_gap_s": 2.0, "k_std": 1.0},
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "blocks": blocks,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


FEATURE_SET_LABEL = {
    1: "raw 7-band MIX vector",
    2: "chroma(MIX) + percussive-band weight",
    3: "per-stem band weight (28-dim)",
}


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        print(f"exported {song} — {len(payload['blocks'])} blocks")
