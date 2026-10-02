"""Write `reference/proposals/downbeat_anchors.json` (a proposal, never ground truth)."""
from __future__ import annotations

import json

from . import anchors as A
from . import build, paths

SCHEMA_VERSION = "1.0"


def compute(song: str) -> dict:
    res = build.build(song)
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    paths.cache_path(song).write_text(json.dumps(res, indent=1) + "\n")
    return res


def export(song: str) -> dict:
    res = json.loads(paths.cache_path(song).read_text()) if paths.cache_path(song).exists() else compute(song)
    b = build.load_beats(song)
    conf_by_idx = {a["beat_index"]: a["confidence"] for a in res["anchors"]}
    rows = []
    for d in res["downbeats"]:
        beat = b["beats"][d["beat_index"]]
        if d["source"] == "anchor":
            conf = conf_by_idx.get(d["beat_index"])
        elif d["source"] == "allin1":
            conf = beat.get("downbeat_confidence")
        else:
            conf = None  # a count carries no measured confidence of its own
        rows.append({"time": round(d["time"], 3), "beat_index": d["beat_index"], "source": d["source"],
                     "span": d["span"], "confidence": conf})
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/downbeat_anchors",
            "engine": "phrase start edges (conflict-free, snapped, with a stem/presence entry or impact) are "
                      "downbeats; bars counted in fours on beats between anchors; anchors disagreeing on "
                      "phase or a span crossing off-grid beats -> resolved:false and no downbeat; "
                      "allin1 downbeats only on beats no anchor reaches",
            "inputs": ["reference/proposals/phrases.json", "beats.json (times, off_grid_spans, "
                       "allin1 type/downbeat_confidence as fallback)"],
            "params": {"anchor_min_score": A.ANCHOR_MIN_SCORE, "reach_beats": A.REACH_BEATS,
                       "snap_tol_s": A.SNAP_TOL_S, "beats_per_bar": A.BEATS_PER_BAR},
        },
        "anchors": [{"time": a["t"], "beat_index": a["beat_index"], "score": a["score"],
                     "kinds": a["kinds"], "confidence": a["confidence"]} for a in res["anchors"]],
        "spans": [{"id": i, "start_s": s["start_s"], "end_s": s["end_s"], "resolved": s["resolved"],
                   "reason": s["reason"]} for i, s in enumerate(res["spans"])],
        "downbeats": rows,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        p = export(song)
        un = sum(not s["resolved"] for s in p["spans"])
        print(f"exported {song} — {len(p['anchors'])} anchors, {len(p['spans'])} spans ({un} unresolved), "
              f"{len(p['downbeats'])} downbeats")
