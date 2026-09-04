"""Write the per-beat/per-bar reactive-band stream and accent list to
`reference/proposals/reactive_bands.json`.
"""
from __future__ import annotations

import datetime
import json

import numpy as np

from . import accents as accents_mod
from . import aggregate, bands, paths, pipeline

SCHEMA_VERSION = "1.0"


def export(song: str, window_s: float = pipeline.DEFAULT_WINDOW_S) -> dict:
    beats = aggregate.load_beats(song)
    sources_out = {}
    all_accents = []

    for source in ("mix",) + paths.STEM_IDS:
        bp = pipeline.load_cache(song, source)
        source_out = {}
        source_accents = []
        for band_name in bands.THREE_BAND_GROUPS:
            power = bp.power_3[band_name]
            inst, att = pipeline.ratios_for_band(power, window_s=window_s)
            per_beat = aggregate.aggregate_per_beat(bp.times, inst, att, beats)
            source_out[band_name] = {
                "per_beat": per_beat,
                "per_bar": aggregate.aggregate_per_bar(per_beat),
            }
            if source == "mix":
                source_accents += accents_mod.find_accents(bp.times, inst, att, beats, band_name)
        sources_out[source] = source_out
        if source == "mix":
            all_accents = sorted(source_accents, key=lambda a: a["time"])

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/reactive_bands",
            "engine": "reactive_bands.bands (locally auto-gained FFT band power, MilkDrop-style)",
            "params": {"window_s": window_s, "damping_tau_s": pipeline.DEFAULT_DAMPING_TAU_S},
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "bands": list(bands.THREE_BAND_GROUPS.keys()),
        "sources": ["mix"] + list(paths.STEM_IDS),
        "reactive": sources_out,
        "accents": all_accents,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        export(song)
        print(f"exported {song}")
