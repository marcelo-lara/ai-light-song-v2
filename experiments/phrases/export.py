"""Write `reference/proposals/phrases.json` — the "Phrases" lane input.

A proposal to audition by ear, never ground truth. `blocks[]` tile the song:
the first starts at 0.0 and the last ends at `info.json`'s duration.
"""
from __future__ import annotations

import json

from . import build, detect, features, paths

SCHEMA_VERSION = "1.0"


def _sweeps(song: str) -> list[dict] | None:
    p = paths.filter_sweep_path(song)
    return json.loads(p.read_text())["blocks"] if p.exists() else None


def build_blocks(song: str, cache: dict | None = None) -> list[dict]:
    cache = cache or features.load_cache(song)
    return build.build_phrases(cache, _sweeps(song))


def export(song: str) -> dict:
    cache = features.load_cache(song)
    blocks = build_blocks(song, cache)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/phrases",
            "engine": "edges = clusters of arrangement_state stem entries/exits, "
                      "stem_presence_sections boundaries, gestures impacts and the ends of "
                      "risers / reverse cymbals / snare rolls / pre-drop gaps, accepted at "
                      "summed evidence >= 1.0 and moved to the nearest trusted beat; "
                      "per-phrase presence and density features; no bar counting",
            "inputs": ["arrangement_state.json", "song_event_timeline.json (impacts)",
                       "loudness.json", "beats.json (times + off_grid_spans only)",
                       "artifacts/essentia/fft_bands.json", "artifacts/essentia/fft_bands.drums.json",
                       "reference/proposals/stem_presence_sections.json",
                       "reference/proposals/filter_sweep.json"],
            "inputs_present": cache["inputs"],
            "params": {
                "accept_score": detect.ACCEPT_SCORE, "cluster_beats": detect.CLUSTER_BEATS,
                "min_phrase_beats": detect.MIN_PHRASE_BEATS, "snap_max_beats": detect.SNAP_MAX_BEATS,
                "spread_conflict_beats": detect.SPREAD_CONFLICT_BEATS,
                "kick_on_frac_of_p95": build.KICK_ON_FRAC, "kick_on_floor": build.KICK_ON_FLOOR,
                "bass_on_frac_of_p95": build.BASS_ON_FRAC, "vocals_on_frac_of_p95": build.VOCALS_ON_FRAC,
                "weights": {k: getattr(features, k) for k in dir(features) if k.startswith("W_")},
                "repeat_max_dist": build.REPEAT_MAX_DIST, "conf_full_score": build.CONF_FULL_SCORE,
            },
        },
        "blocks": blocks,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        b = export(song)["blocks"]
        print(f"exported {song} — {len(b)} phrases ({sum(not x['resolved'] for x in b)} unresolved)")
