"""compute — item 5/6a candidate producer: `rhythm.drums` subdivision +
confidence from `drum_events.json` inter-onset intervals.

Method: median drum-event IOI inside the span / local beat period -> nearest
of half/quarter/eighth/sixteenth/eighth_triplet (log-distance, same
vocabulary as `segment_seeds.features.nearest_subdivision`); below 1 onset
per bar -> `"none"`. Confidence is `rhythm_energy_common.
subdivision_from_ratio`'s normalised margin between the best and second-best
candidate (or, for `"none"`, the honest distance below the 1-onset-per-bar
floor) — never a constant.

No silent fallbacks: a span with no usable beat grid, or fewer than 2 drum
onsets in it, is omitted from the output entirely.
"""
from __future__ import annotations

import json

from experiments.rhythm_energy_common import dominant_ioi_ratio, subdivision_from_ratio
from experiments.segment_seeds import features as seed_features

from . import paths


def compute(song: str) -> list[dict]:
    beats = seed_features.load_json(paths.beats_path(song))
    drum_events = seed_features.load_json(paths.drum_events_path(song))
    events = (drum_events or {}).get("events") or []

    rows: list[dict] = []
    for span in paths.spans(song):
        start, end = span["start"], span["end"]
        beat_period = seed_features.beat_period_near(beats, start, end)
        if not beat_period or beat_period <= 0:
            continue
        onsets = sorted(e["time"] for e in events if start <= e["time"] < end)
        span_bars = (end - start) / (beat_period * 4.0)
        if span_bars <= 0 or len(onsets) < 2:
            continue
        onsets_per_bar = len(onsets) / span_bars
        if onsets_per_bar < 1.0:
            name, conf = subdivision_from_ratio(None, below_frac=onsets_per_bar)
        else:
            ratio = dominant_ioi_ratio(onsets, beat_period)
            if ratio is None:
                continue
            name, conf = subdivision_from_ratio(ratio)
        if name is None:
            continue
        rows.append({
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "subdivisions": {"drums": name},
            "confidence": {"drums": conf},
            "onsets_per_bar": round(onsets_per_bar, 3),
        })
    return rows


def compute_and_cache(song: str) -> list[dict]:
    rows = compute(song)
    path = paths.cache_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def load_cache(song: str) -> list[dict]:
    path = paths.cache_path(song)
    if not path.exists():
        return compute_and_cache(song)
    return json.loads(path.read_text())
