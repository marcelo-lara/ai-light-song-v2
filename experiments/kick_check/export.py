from __future__ import annotations

import datetime
import json

from experiments.drum_hit_shape import attack_envelope, hit_shape, load_drums_stem

from . import paths
from . import verdict

SCHEMA_VERSION = "1.0"


def _omnizart_kicks(song: str) -> list[float]:
    events = json.loads(paths.drum_events_path(song).read_text())["events"]
    return sorted(e["time"] for e in events if e["event_type"] == "kick")


def compute(song: str) -> dict:
    stem = load_drums_stem(song)
    env = attack_envelope(stem)
    attack_threshold = verdict.ATTACK_FACTOR * env.percentile(75)
    rows = []
    for t in _omnizart_kicks(song):
        shape = hit_shape(stem, t)
        if shape is None:
            continue
        feat = verdict.KickFeatures(
            time=round(t, 3),
            low_share=shape.low_share,
            noise_share=shape.noise_share,
            attack=round(env.at(t), 4),
            attack_threshold=round(attack_threshold, 4),
        )
        rows.append({
            "time": feat.time,
            "low_share": feat.low_share,
            "noise_share": feat.noise_share,
            "attack": feat.attack,
            "attack_threshold": feat.attack_threshold,
            "verdict": "keep" if verdict.keep(feat) else "reject",
        })
    payload = {
        "song": song,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "kicks": rows,
    }
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def load_cache(song: str) -> dict:
    path = paths.cache_path(song)
    if not path.exists():
        return compute(song)
    return json.loads(path.read_text())


def export(song: str) -> dict:
    cache = load_cache(song)
    rows = [
        {
            "time": row["time"],
            "verdict": row["verdict"],
            "low_share": row["low_share"],
            "noise_share": row["noise_share"],
        }
        for row in cache["kicks"]
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/kick_check",
            "engine": "per-hit spectral shape (sub/low body share, "
                      "1-6 kHz noise share) + percussive-attack gate "
                      "(low-band onset strength vs song-relative baseline) "
                      "over every omnizart `kick` event",
            "params": {
                "low_min": verdict.LOW_MIN,
                "noise_max": verdict.NOISE_MAX,
                "attack_factor": verdict.ATTACK_FACTOR,
            },
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "kicks": rows,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        kept = sum(1 for r in payload["kicks"] if r["verdict"] == "keep")
        print(f"exported {song} — {kept}/{len(payload['kicks'])} kicks kept")
