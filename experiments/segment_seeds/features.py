"""features.py — the seed rule table, refinement item 6 "Seeds first", exactly.
Fixed, not tuned (docs/product-refinement-v3.6.md section 6):

| field                       | seed rule                                                                                                     |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `energy`                     | segment mean of `loudness.json` mix `normalized_values`, plus `arrangement_state` stems playing; song-relative quintiles -> 1-5 |
| `tension`                    | `energy` slope across the segment (rising = tense), +1 when a gesture `build`/`tension` phase overlaps, clamped 1-5 |
| `rhythm.drums`               | dominant `drum_events.json` inter-onset interval / beat period -> nearest of 1/2, 1/4, 1/8, 1/16, 1/3 (`eighth_triplet`); `none` below 1 onset per bar |
| `rhythm.bass/harmonic/vocals`| strongest sub-beat autocorrelation peak of that stem's 20 ms loudness at the same fractions; `vocals` is `none` where no `vocals_phrase` overlaps |

Reads only top-level published song JSON (`loudness.json`, `arrangement_state.json`,
`drum_events.json`, `beats.json`, `song_event_timeline.json`) plus, for spans,
`reference/human/segments.json` (falls back to `sections.json`). Every value
that cannot be computed (no beat grid in the span, no frames, etc.) is omitted
— never a guessed default (CLAUDE.md "no silent fallbacks").
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from . import paths

#: candidate subdivisions as a fraction of the beat (quarter-note) period.
SUBDIVISIONS: dict[str, float] = {
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25,
    "eighth_triplet": 1.0 / 3.0,
}

#: below this normalised-autocorrelation strength, report "none" rather than
#: the nominally-best (but weak) candidate.
MIN_AUTOCORR = 0.15


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def segment_spans(song: str) -> list[dict[str, Any]]:
    """`segments.json` spans where that file exists and is non-empty, else
    `sections.json` spans. `label` is carried only for the seed file's own
    readability — never republished as a fact the seed method asserts
    (refinement item 6: "seeds never supply boundaries or labels")."""
    seg = load_json(paths.segments_path(song))
    if isinstance(seg, list) and seg:
        return [
            {
                "start": float(s["start"]),
                "end": float(s["end"]),
                "label": s.get("label"),
            }
            for s in seg
        ]
    sec = load_json(paths.sections_path(song)) or {}
    rows = sec.get("sections", [])
    return [
        {
            "start": float(s["start"]),
            "end": float(s["end"]),
            "label": s.get("function"),
        }
        for s in rows
    ]


def source_index(loudness: dict | None, source_id: str) -> int | None:
    if not loudness:
        return None
    for i, s in enumerate(loudness.get("sources", [])):
        if s.get("id") == source_id:
            return i
    return None


def mean_in_span(loudness: dict | None, idx: int | None, start: float, end: float) -> float:
    if loudness is None or idx is None:
        return 0.0
    vals = [
        f["normalized_values"][idx]
        for f in loudness["frames"]
        if start <= f["time"] < end
    ]
    if not vals:
        return 0.0
    return float(np.mean(vals))


def stems_playing_fraction(
    arrangement: dict | None, start: float, end: float, total_stems: int
) -> float:
    blocks = (arrangement or {}).get("blocks") or []
    weighted = 0.0
    total_overlap = 0.0
    for b in blocks:
        bs, be = b.get("start_s"), b.get("end_s")
        if bs is None or be is None:
            continue
        overlap = min(end, be) - max(start, bs)
        if overlap <= 0:
            continue
        frac = (len(b.get("playing") or []) / total_stems) if total_stems else 0.0
        weighted += frac * overlap
        total_overlap += overlap
    if total_overlap <= 0:
        return 0.0
    return weighted / total_overlap


def gesture_tension_overlap(event_timeline: dict | None, start: float, end: float) -> bool:
    events = (event_timeline or {}).get("events") or []
    for e in events:
        if e.get("gesture_id") is None:
            continue
        if e.get("type") not in ("build", "tension"):
            continue
        es, ee = e.get("start_time"), e.get("end_time")
        if es is None or ee is None:
            continue
        if min(end, ee) - max(start, es) > 0:
            return True
    return False


def beat_period_near(beats: dict | None, start: float, end: float) -> float | None:
    """Median inter-beat gap (quarter-note period), preferring beats inside
    the span; falls back to the whole song's beats if the span holds fewer
    than 2. `None` when the song carries no usable beat grid."""
    rows = (beats or {}).get("beats") or []
    if not rows:
        return None
    inside = sorted(b["time"] for b in rows if start <= b["time"] <= end)
    pool = inside if len(inside) >= 2 else sorted(b["time"] for b in rows)
    if len(pool) < 2:
        return None
    diffs = [b - a for a, b in zip(pool, pool[1:]) if b - a > 0]
    if not diffs:
        return None
    return float(np.median(diffs))


def nearest_subdivision(ratio: float) -> str | None:
    if ratio is None or ratio <= 0:
        return None
    best_name, best_dist = None, None
    for name, target in SUBDIVISIONS.items():
        dist = abs(np.log(ratio) - np.log(target))
        if best_dist is None or dist < best_dist:
            best_name, best_dist = name, dist
    return best_name


def drum_rhythm(
    drum_events: dict | None, beats: dict | None, start: float, end: float
) -> str | None:
    beat_period = beat_period_near(beats, start, end)
    if not beat_period or beat_period <= 0:
        return None
    events = (drum_events or {}).get("events") or []
    onsets = sorted(e["time"] for e in events if start <= e["time"] < end)
    span_bars = (end - start) / (beat_period * 4.0)
    if span_bars <= 0:
        return None
    onsets_per_bar = len(onsets) / span_bars
    if onsets_per_bar < 1.0 or len(onsets) < 2:
        return "none"
    iois = np.diff(np.array(onsets, dtype=float))
    iois = iois[iois > 0]
    if iois.size == 0:
        return "none"
    dominant_ioi = float(np.median(iois))
    ratio = dominant_ioi / beat_period
    return nearest_subdivision(ratio) or "none"


def stem_rhythm(
    loudness: dict | None,
    stem_id: str,
    start: float,
    end: float,
    beat_period: float | None,
) -> str | None:
    """Strongest sub-beat autocorrelation peak of `stem_id`'s 20 ms loudness,
    tested at the same beat-fraction lags as `rhythm.drums`."""
    if loudness is None or not beat_period or beat_period <= 0:
        return None
    idx = source_index(loudness, stem_id)
    if idx is None:
        return None
    metadata = loudness.get("metadata") or {}
    interval_s = (metadata.get("interval_ms") or 20) / 1000.0
    xs = np.array(
        [
            f["normalized_values"][idx]
            for f in loudness["frames"]
            if start <= f["time"] < end
        ],
        dtype=float,
    )
    if xs.size < 8:
        return "none"
    xs = xs - xs.mean()
    denom = float(np.sum(xs * xs))
    if denom <= 1e-9:
        return "none"
    best_name, best_corr = None, -1.0
    for name, frac in SUBDIVISIONS.items():
        lag_frames = int(round((beat_period * frac) / interval_s))
        if lag_frames <= 0 or lag_frames >= xs.size:
            continue
        a, b = xs[:-lag_frames], xs[lag_frames:]
        corr = float(np.sum(a * b) / denom)
        if corr > best_corr:
            best_corr, best_name = corr, name
    if best_name is None or best_corr < MIN_AUTOCORR:
        return "none"
    return best_name


def vocals_phrase_overlap(arrangement: dict | None, start: float, end: float) -> bool:
    phrases = (arrangement or {}).get("vocals_phrase") or []
    for p in phrases:
        ps, pe = p.get("start_s"), p.get("end_s")
        if ps is None or pe is None:
            continue
        if min(end, pe) - max(start, ps) > 0:
            return True
    return False


def quintile_bin(raw_scores: list[float]) -> list[int]:
    """Song-relative rank -> 1-5, roughly equal-sized bins. Ties keep the
    original (stable) order so the result is deterministic."""
    n = len(raw_scores)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: (raw_scores[i], i))
    bins = [0] * n
    for rank, i in enumerate(order):
        frac = (rank + 0.5) / n
        bins[i] = min(5, max(1, int(np.ceil(frac * 5))))
    return bins


def compute_seed(song: str) -> list[dict[str, Any]]:
    spans = segment_spans(song)
    if not spans:
        return []

    loudness = load_json(paths.loudness_path(song))
    arrangement = load_json(paths.arrangement_state_path(song))
    drum_events = load_json(paths.drum_events_path(song))
    beats = load_json(paths.beats_path(song))
    event_timeline = load_json(paths.song_event_timeline_path(song))

    total_stems = len(paths.STEM_IDS)
    mix_idx = source_index(loudness, "mix")

    energy_raw: list[float] = []
    tension_raw: list[float] = []
    extras: list[dict[str, Any]] = []

    for span in spans:
        start, end = span["start"], span["end"]
        mid = (start + end) / 2.0

        mix_mean = mean_in_span(loudness, mix_idx, start, end)
        stems_frac = stems_playing_fraction(arrangement, start, end, total_stems)
        energy_raw.append(0.5 * mix_mean + 0.5 * stems_frac)

        first_mean = mean_in_span(loudness, mix_idx, start, mid)
        second_mean = mean_in_span(loudness, mix_idx, mid, end)
        tension_raw.append(second_mean - first_mean)

        beat_period = beat_period_near(beats, start, end)
        drums_sub = drum_rhythm(drum_events, beats, start, end)
        bass_sub = stem_rhythm(loudness, "bass", start, end, beat_period)
        harmonic_sub = stem_rhythm(loudness, "harmonic", start, end, beat_period)
        vocals_sub = (
            stem_rhythm(loudness, "vocals", start, end, beat_period)
            if vocals_phrase_overlap(arrangement, start, end)
            else "none"
        )

        extras.append(
            {
                "rhythm": {
                    "drums": drums_sub,
                    "bass": bass_sub,
                    "harmonic": harmonic_sub,
                    "vocals": vocals_sub,
                },
                "gesture_bump": gesture_tension_overlap(event_timeline, start, end),
            }
        )

    energy_bins = quintile_bin(energy_raw)
    tension_bins = quintile_bin(tension_raw)

    rows: list[dict[str, Any]] = []
    for span, e, t, extra in zip(spans, energy_bins, tension_bins, extras):
        tension_val = min(5, t + (1 if extra["gesture_bump"] else 0))
        rhythm = {k: v for k, v in extra["rhythm"].items() if v is not None}
        rows.append(
            {
                "start": round(float(span["start"]), 3),
                "end": round(float(span["end"]), 3),
                "label": span.get("label") or None,
                "energy": int(e),
                "tension": int(tension_val),
                "rhythm": rhythm,
            }
        )
    return rows
