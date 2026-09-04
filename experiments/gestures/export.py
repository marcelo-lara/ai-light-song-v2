"""Write the assembled gestures to `reference/proposals/gestures.json`."""
from __future__ import annotations

import datetime
import json

from . import assembly, loaders, paths, primitives

SCHEMA_VERSION = "1.0"


def run_detectors(song: str) -> dict:
    fft = loaders.load_fft_bands(song)
    rms = loaders.load_rms_loudness(song)
    drum_events = loaders.load_drum_events(song)
    beats = loaders.load_beats(song)

    risers = primitives.detect_ramps(fft, beats, kind="riser")
    downlifters = primitives.detect_ramps(fft, beats, kind="downlifter")
    reverse_cymbals = primitives.detect_reverse_cymbal(fft, rms, beats)
    snare_rolls = primitives.detect_snare_roll(drum_events, beats)
    impacts = primitives.detect_impacts(fft, beats)
    pre_drop_gaps = primitives.detect_pre_drop_gaps(fft, impacts, beats)

    gestures = assembly.assemble(
        impacts, risers + downlifters, reverse_cymbals, snare_rolls, pre_drop_gaps, beats,
        rms.times, rms.values.get("mix"),
    )

    return {
        "primitives": {
            "riser": risers,
            "downlifter": downlifters,
            "reverse_cymbal": reverse_cymbals,
            "snare_roll": snare_rolls,
            "impact": impacts,
            "pre_drop_gap": pre_drop_gaps,
        },
        "gestures": gestures,
    }


def export(song: str) -> dict:
    result = run_detectors(song)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/gestures",
            "engine": "gestures.primitives (rule-based sound-design device detectors) + gestures.assembly",
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        **result,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        p = export(song)
        print(f"exported {song}: {len(p['gestures'])} gestures, "
              f"{sum(len(v) for v in p['primitives'].values())} primitives")
