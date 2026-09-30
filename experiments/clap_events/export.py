"""compute -> cache/<song>.json (every onset candidate + its shape);
export -> reference/proposals/clap_events.json (candidates the shape test
calls a clap, only)."""
from __future__ import annotations

import datetime
import json

from experiments.drum_hit_shape import hit_shape, load_drums_stem

from . import candidates as cand_mod
from . import paths
from . import verdict

SCHEMA_VERSION = "1.0"


def compute(song: str) -> dict:
    stem = load_drums_stem(song)
    onsets = cand_mod.onset_candidates(stem)
    rows = []
    for t in onsets:
        shape = hit_shape(stem, t)
        if shape is None:
            continue
        rows.append({
            "time": round(t, 3),
            "noise_share": shape.noise_share,
            "body_share": shape.body_share,
            "low_share": shape.low_share,
            "is_clap": verdict.is_clap(shape),
            "confidence": verdict.confidence(shape),
        })
    payload = {
        "song": song,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "candidates": rows,
    }
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def load_cache(song: str) -> dict:
    path = paths.cache_path(song)
    if not path.exists():
        return compute(song)
    return json.loads(path.read_text())


def export(song: str) -> dict:
    cache = load_cache(song)
    events = [
        {
            "time": row["time"],
            "noise_share": row["noise_share"],
            "body_share": row["body_share"],
            "confidence": row["confidence"],
        }
        for row in cache["candidates"] if row["is_clap"]
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/clap_events",
            "engine": "per-hit spectral shape (1-6 kHz noise share / "
                      "120-400 Hz body share) over drums-stem onset "
                      "candidates — never omnizart's event label",
            "params": {
                "win_s": 0.12,
                "noise_min": verdict.NOISE_MIN,
                "body_max": verdict.BODY_MAX,
            },
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "events": events,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        print(f"exported {song} — {len(payload['events'])} claps")
