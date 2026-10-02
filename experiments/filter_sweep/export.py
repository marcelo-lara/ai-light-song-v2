"""Write `reference/proposals/filter_sweep.json` — the "Filter Sweeps" lane input.

A proposal to audition by ear, never ground truth. Schema: `blocks[]` with
`direction` (opening|closing), `stem`, `start_s`, `end_s`, `depth` (centroid
change, octaves), `confidence` (heuristic 0..1, not calibrated).
"""
from __future__ import annotations

import datetime
import json

from . import detect, features, paths

SCHEMA_VERSION = "1.0"


def build_blocks(song: str, cache: dict | None = None) -> list[dict]:
    cache = cache or features.load_cache(song)
    return [
        {
            "direction": r["direction"], "stem": r["stem"],
            "start_s": round(r["start"], 3), "end_s": round(r["end"], 3),
            "depth": round(r["depth"], 3), "confidence": r["confidence"],
        }
        for r in detect.detect_song(cache)
    ]


def export(song: str) -> dict:
    blocks = build_blocks(song)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/filter_sweep",
            "engine": "per-stem spectral centroid (log2 Hz, level-weighted over the 7 published "
                      "FFT bands) on a half-beat grid; near-monotonic move over 2-16 bars with "
                      "level-flat stem loudness",
            "inputs": ["artifacts/essentia/fft_bands.harmonic.json", "artifacts/essentia/fft_bands.bass.json",
                       "loudness.json", "beats.json (beat spacing only)"],
            "params": {
                "bar_lengths": list(detect.BAR_LENGTHS), "min_depth_octaves": detect.MIN_DEPTH_OCT,
                "min_monotonicity": detect.MIN_MONO, "max_level_spread": detect.MAX_LEVEL_SPREAD,
                "max_level_trend": detect.MAX_LEVEL_TREND, "present_frac_of_p95": detect.PRESENT_FRAC,
            },
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "blocks": blocks,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        print(f"exported {song} — {len(export(song)['blocks'])} sweeps")
