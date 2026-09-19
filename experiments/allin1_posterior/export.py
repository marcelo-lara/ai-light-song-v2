"""Writes `reference/proposals/allin1_posterior.json` — a proposal lane, never
a deliverable. Never overwrites `reference/human/`."""
from __future__ import annotations

from analyzer.io import write_json

from . import analysis, paths


def export_song(song: str) -> dict:
    shadows = analysis.detect_shadow_labels(song)
    entropy_check = analysis.section_entropy_confidences(song)
    payload = {
        "song_name": song,
        "shadow_labels": shadows,
        "section_entropy_parity_check": entropy_check,
        "note": (
            "function_confidence on sections.json is already this module's entropy "
            "measure, shipped in production (segmentation.py). Only shadow_labels "
            "is new — a candidate field, not yet published anywhere."
        ),
    }
    write_json(paths.proposals_path(song), payload)
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        print(f"exporting {song} ...", flush=True)
        payload = export_song(song)
        print(f"  {len(payload['shadow_labels'])} shadow spans")
