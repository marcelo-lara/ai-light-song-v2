from __future__ import annotations

import datetime
import json

from experiments.drum_hit_shape import bright_decay_ratio, is_stream_continuation, load_beat_length, load_drums_stem

from . import paths
from . import verdict

SCHEMA_VERSION = "1.0"


def _omnizart_crashes(song: str) -> list[float]:
    events = json.loads(paths.drum_events_path(song).read_text())["events"]
    return sorted(e["time"] for e in events if e["event_type"] == "crash")


def compute(song: str) -> dict:
    stem = load_drums_stem(song)
    beat_len = load_beat_length(song)
    times = _omnizart_crashes(song)
    rows = []
    prev: float | None = None
    for t in times:
        cont = is_stream_continuation(prev, t, beat_len, tol_frac=verdict.STREAM_TOL_FRAC)
        decay = bright_decay_ratio(stem, t)
        feat = verdict.CrashFeatures(time=round(t, 3), is_stream_continuation=cont, decay_ratio=decay)
        rows.append({
            "time": feat.time,
            "is_stream_continuation": cont,
            "decay_ratio": decay,
            "verdict": "keep" if verdict.keep(feat) else "reject",
        })
        prev = t
    payload = {
        "song": song,
        "beat_length_s": round(beat_len, 4),
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "crashes": rows,
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
            "is_stream_continuation": row["is_stream_continuation"],
            "decay_ratio": row["decay_ratio"],
        }
        for row in cache["crashes"]
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/crash_check",
            "engine": "regular-stream-period rejection (~1-2 beat spacing) "
                      "+ brilliance-band decay-shape gate over every "
                      "omnizart `crash` event",
            "params": {
                "decay_max": verdict.DECAY_MAX,
                "stream_tol_frac": verdict.STREAM_TOL_FRAC,
                "beat_length_s": cache["beat_length_s"],
            },
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "crashes": rows,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        kept = sum(1 for r in payload["crashes"] if r["verdict"] == "keep")
        print(f"exported {song} — {kept}/{len(payload['crashes'])} crashes kept")
