"""compute — item 5/6b candidate producer:
`rhythm.{drums,bass,harmonic,vocals}` subdivision + confidence from sub-beat
autocorrelation of each stem's 20 ms loudness curve
(`experiments.rhythm_energy_common.autocorr_subdivision`, the same scan as
`segment_seeds.features.stem_rhythm`).

`vocals` is gated on `arrangement_state.json`'s `vocals_phrase` overlap
(`segment_seeds.features.vocals_phrase_overlap`) — where no vocal phrase
overlaps the span, `vocals` is reported `"none"` at confidence 1.0 (an
honest absence, matching the item 4 seed rule), not omitted.

No silent fallbacks otherwise: a span with no usable beat grid is omitted
entirely; a stem missing from `loudness.json` or with too few frames in the
span is omitted from that row's `subdivisions` (the row itself still carries
whichever other stems computed).
"""
from __future__ import annotations

import json

import numpy as np

from experiments.rhythm_energy_common import autocorr_subdivision
from experiments.segment_seeds import features as seed_features

from . import paths


def compute(song: str) -> list[dict]:
    beats = seed_features.load_json(paths.beats_path(song))
    loudness = seed_features.load_json(paths.loudness_path(song))
    arrangement = seed_features.load_json(paths.arrangement_state_path(song))
    if loudness is None:
        return []
    interval_s = ((loudness.get("metadata") or {}).get("interval_ms") or 20) / 1000.0

    rows: list[dict] = []
    for span in paths.spans(song):
        start, end = span["start"], span["end"]
        beat_period = seed_features.beat_period_near(beats, start, end)
        if not beat_period or beat_period <= 0:
            continue
        subs: dict[str, str] = {}
        confs: dict[str, float] = {}
        for stem in paths.STEM_IDS:
            if stem == "vocals" and not seed_features.vocals_phrase_overlap(
                arrangement, start, end
            ):
                subs["vocals"] = "none"
                confs["vocals"] = 1.0
                continue
            idx = seed_features.source_index(loudness, stem)
            if idx is None:
                continue
            xs = np.array(
                [
                    f["normalized_values"][idx]
                    for f in loudness["frames"]
                    if start <= f["time"] < end
                ],
                dtype=float,
            )
            name, conf = autocorr_subdivision(xs, interval_s, beat_period)
            if name is None:
                continue
            subs[stem] = name
            confs[stem] = conf
        if not subs:
            continue
        rows.append({
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "subdivisions": subs,
            "confidence": confs,
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
