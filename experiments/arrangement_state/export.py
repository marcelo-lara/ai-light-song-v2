"""Write the UI review lane's proposal file.

Proposals only — nothing in `src/` reads this, and it never touches
`reference/human/`.
"""
from __future__ import annotations

import json

from . import detector, paths


def export(song: str) -> None:
    res = detector.detect(song)
    doc = {
        "schema_version": "1.0",
        "song_name": song,
        "generated_from": {
            "engine": "experiments.arrangement_state.detector",
            "reads": "data/analysis/{song}/loudness.json (published per-stem RMS; no audio)",
            "window_s": detector.WINDOW_S,
            "present_db_below_p98": detector.PRESENT_DB_BELOW_P98,
            "present_fraction": detector.PRESENT_FRACTION,
            "hold_s": detector.HOLD_S,
        },
        "note": (
            "Arrangement-state blocks: who is playing, and where that changes. "
            "Proposals for review, not deliverables. Boundary times are the "
            "unsmoothed 250 ms edge — never a smoothed centre."
        ),
        "stems": res.stems,
        "thresholds_db": res.thresholds_db,
        "blocks": detector.blocks(res),
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"  wrote {out} ({len(doc['blocks'])} blocks)")


def export_all(songs: list[str]) -> None:
    for song in songs:
        export(song)
