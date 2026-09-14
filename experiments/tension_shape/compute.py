"""compute — item 5/6 candidate producer: `tension` (1-5) from energy slope
+ gesture build/tension overlap + Phrase Periodicity regime.

Method: `slope = mean(mix loudness, second half of span) - mean(mix
loudness, first half)` (rising = tenser) — the same raw signal as
`segment_seeds.features.compute_seed`'s `tension` rule (item 4's seed
writer) — song-relative quintile-binned to 1-5, **+1** when a
`song_event_timeline.json` gesture `build`/`tension` phase overlaps the span
(`segment_seeds.features.gesture_tension_overlap`), **+1** when the sibling
`experiments/phrase_periodicity` experiment's `through-composed` regime
overlaps the span (a candidate signal item 6 names but the item-4 seed rule
does not use), clamped to 5.

Confidence is the quintile-bin margin on the *slope only*
(`rhythm_energy_common.quintile_with_margin`) — the two +1 bumps are binary
evidence, not folded into the confidence number, and recorded separately in
`evidence` so a reader can see whether a 5 came from the slope alone or from
a bump.

No silent fallbacks: if a song has no `loudness.json` or no segment spans,
`compute` returns an empty list.
"""
from __future__ import annotations

import json

from experiments.rhythm_energy_common import quintile_with_margin
from experiments.segment_seeds import features as seed_features

from . import paths


def _phrase_periodicity_regimes(song: str) -> list[dict]:
    payload = seed_features.load_json(paths.phrase_periodicity_path(song))
    if not payload:
        return []
    return payload.get("blocks", [])


def _through_composed_overlap(regimes: list[dict], start: float, end: float) -> bool:
    for b in regimes:
        if b.get("regime") != "through-composed":
            continue
        bs, be = b.get("start_s"), b.get("end_s")
        if bs is None or be is None:
            continue
        if min(end, be) - max(start, bs) > 0:
            return True
    return False


def compute(song: str) -> list[dict]:
    loudness = seed_features.load_json(paths.loudness_path(song))
    event_timeline = seed_features.load_json(paths.song_event_timeline_path(song))
    regimes = _phrase_periodicity_regimes(song)
    spans = paths.spans(song)
    if not spans or loudness is None:
        return []

    mix_idx = seed_features.source_index(loudness, "mix")

    raw: list[float] = []
    evidence: list[dict] = []
    for span in spans:
        start, end = span["start"], span["end"]
        mid = (start + end) / 2.0
        first_mean = seed_features.mean_in_span(loudness, mix_idx, start, mid)
        second_mean = seed_features.mean_in_span(loudness, mix_idx, mid, end)
        slope = second_mean - first_mean
        raw.append(slope)
        gesture_bump = seed_features.gesture_tension_overlap(event_timeline, start, end)
        regime_bump = _through_composed_overlap(regimes, start, end)
        evidence.append({
            "slope": round(slope, 4),
            "gesture_bump": gesture_bump,
            "phrase_periodicity_through_composed_bump": regime_bump,
        })

    binned = quintile_with_margin(raw)
    rows: list[dict] = []
    for span, (bin_val, conf), ev in zip(spans, binned, evidence):
        bumped = min(
            5,
            bin_val
            + (1 if ev["gesture_bump"] else 0)
            + (1 if ev["phrase_periodicity_through_composed_bump"] else 0),
        )
        rows.append({
            "start_s": round(span["start"], 3),
            "end_s": round(span["end"], 3),
            "tension": int(bumped),
            "confidence": conf,
            "evidence": ev,
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
