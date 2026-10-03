"""Write `reference/proposals/bar_features.json` — the "Bar Features" lane input.

A feature table, not a claim: `bars[]` and `half_beats[]`, one row per window
(see features.py for the fields). `bars[].irregular` flags a bar whose length is
not 4 beats (grid slip) — flagged, never fixed.
"""
from __future__ import annotations

import datetime
import json

from . import features, paths

SCHEMA_VERSION = "1.0"


def export(song: str) -> dict:
    cache = features.load_cache(song)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/bar_features",
            "engine": "fusion of existing artifacts onto beats.json bar / half-beat windows; nothing extracted from audio",
            "inputs": ["beats.json", "loudness.json", "artifacts/essentia/fft_bands{,.<stem>}.json",
                       "drum_events.json", "arrangement_state.json", "song_event_timeline.json",
                       "reference/proposals/filter_sweep.json", "reference/proposals/kick_attacks.json"],
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "bars": cache["bars"],
        "half_beats": cache["half_beats"],
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        p = export(song)
        irr = sum(1 for b in p["bars"] if b["irregular"])
        print(f"exported {song} — {len(p['bars'])} bars ({irr} irregular), {len(p['half_beats'])} half-beats")
