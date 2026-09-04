"""Write the resolved grid to `reference/proposals/grid.json`."""
from __future__ import annotations

import datetime
import json

from . import consensus, paths, phrase

SCHEMA_VERSION = "1.0"


def export(song: str) -> dict:
    result = consensus.resolve_song(song)
    # Reuse section starts + gesture impacts directly for phrase-length scoring.
    section_starts = []
    if paths.sections_path(song).exists():
        rows = json.loads(paths.sections_path(song).read_text())
        section_starts = [float(r["start"]) for r in rows if float(r["start"]) > 0.05]
    gesture_impacts = []
    if paths.gestures_proposal_path(song).exists():
        gdata = json.loads(paths.gestures_proposal_path(song).read_text())
        gesture_impacts = [g["impact_time"] for g in gdata.get("gestures", [])]

    phrase_grid = phrase.derive_phrase_grid(
        result["essentia_beats"], result["winning_phase"] if result["winning_phase"] is not None else 0,
        section_starts + gesture_impacts,
    )

    downbeats = [
        {"time": b["time"], "bar_beat_index": i, "confidence": result["confidence"], "status": result["grid_status"]}
        for i, b in enumerate(result["essentia_beats"]) if i % 4 == (result["winning_phase"] or 0)
    ]

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/grid_consensus",
            "engine": "grid_consensus.consensus (musical-evidence phase resolution over essentia/beat-this/allin1)",
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "winning_phase": result["winning_phase"],
        "confidence": result["confidence"],
        "margin": result["margin"],
        "status": result["grid_status"],
        "votes": result["votes"],
        "vote_compatibility": result["vote_compatibility"],
        "agreeing_hypotheses": result["agreeing_hypotheses"],
        "disagreeing_hypotheses": result["disagreeing_hypotheses"],
        "downbeats": downbeats,
        "phrase_grid": phrase_grid,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        p = export(song)
        print(f"exported {song}: phase={p['winning_phase']} status={p['status']} "
              f"confidence={p['confidence']} phrase_len={p['phrase_grid']['phrase_length_bars']}")
