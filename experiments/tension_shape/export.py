"""Write `reference/proposals/tension_shape.json` — the timeline lane input,
and a candidate `tension` producer for item 5/6's fusion."""
from __future__ import annotations

import json

from . import compute, paths

SCHEMA_VERSION = "1.0"


def export(song: str) -> dict:
    rows = compute.load_cache(song)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/tension_shape",
            "engine": (
                "mix-loudness slope across the span (2nd-half mean minus "
                "1st-half mean), song-relative quintile -> 1-5, +1 gesture "
                "build/tension overlap, +1 phrase_periodicity "
                "through-composed regime overlap, clamped 5"
            ),
            "spans": "reference/human/segments.json (falls back to sections.json)",
        },
        "blocks": rows,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        print(f"exported {song} — {len(payload['blocks'])} blocks")
