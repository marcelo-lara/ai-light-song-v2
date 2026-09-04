"""Write the detector's output to `reference/proposals/vocal_phrases.json`.

Never `artifacts/`, never `reference/human/` (constitution §3.2/§9): this is a
proposal, not a deliverable.
"""
from __future__ import annotations

import datetime
import json

from . import detector, paths

SCHEMA_VERSION = "1.0"


def export(song: str) -> dict:
    env = detector.load_envelope(song)
    derived = detector.derive_phrases(env)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/vocal_phrases",
            "engine": "vocal_phrases.detector (local-auto-gain hysteresis over vocals stem, pYIN sustained-note pass)",
            "source_stem": str(paths.vocals_stem_path(song)),
            "params": derived["params"],
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "vocal_phrases": derived["vocal_phrases"],
        "instrumental_gaps": derived["instrumental_gaps"],
        "sustained_notes": derived["sustained_notes"],
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        export(song)
        print(f"exported {song}")
