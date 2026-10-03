"""Write `reference/proposals/light_changes.json` — the "Light Changes" lane input.

`points[]`: `bar` (current beats.json numbering), `time_s` / `end_s` (the bar), `role`
(groove_in | build | break | drop | gap | fill | unknown), `score` (pooled evidence, not
a probability), `features` (the feature groups that moved), `z` (signed move per group, in
robust sigmas), `irregular_bar`, `confidence` (always null: the score is not calibrated).
"""
from __future__ import annotations

import datetime
import json

from . import detect, features, paths

SCHEMA_VERSION = "1.0"


def build_points(song: str) -> list[dict]:
    bars = features.load_bars(song)
    cache = features.load_cache(song, bars)
    out = []
    for p in detect.detect(bars, cache["texture_novelty"]):
        out.append({
            "bar": p["bar"], "time_s": round(p["time_s"], 3), "end_s": round(p["end_s"], 3),
            "role": p["role"], "score": p["score"], "features": p["active"],
            "z": p["z"], "irregular_bar": p["irregular_bar"], "confidence": None,
        })
    return out


def export(song: str) -> dict:
    points = build_points(song)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/light_changes",
            "engine": "sequential change-point walk over the bar_features table: each bar vs the median of the "
                      "previous <=8 bars of the current segment, per-channel robust z, channels pooled into "
                      "groups, S = sum(clip(group max |z| - Z0, 0, ZCAP)); rule-based role labels",
            "inputs": ["reference/proposals/bar_features.json", "artifacts/essentia/fft_bands.<stem>.json (texture_novelty input)"],
            "params": {"ref_max_bars": detect.REF_MAX, "z0": detect.Z0, "zcap": detect.ZCAP,
                       "score_threshold": detect.S_THRESHOLD, "short_window_beats": detect.SHORT_BEATS},
            "confidence_reason": "pooled evidence score is not calibrated against any ground truth beyond two validation songs",
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "points": points,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        print(f"exported {song} — {len(export(song)['points'])} change points")
