"""Phase 3 (relate) — `energy`, `tension`, `rhythm` and `impact_alignment`
clue fields on `sections.json` rows (docs/product-refinement-v3.6.md item 6,
plan item 10; `impact_alignment` is docs/product-refinement-v3.7.md item 2,
plan item 4).

`impact_alignment` (always emitted, `null` when unresolved — see
`_nearest_impact_alignment`) is the nearest `song_event_timeline.json`
gesture `impact` to a section's `start`, so a late payoff ("the section
started but the impact lands 3.8s later") is a fact on the row rather than
something a reader has to cross-reference and subtract by hand. Unlike
`energy`/`tension`/`rhythm` it has no human/seed tier — there is no
`reference/` producer for it — and no confidence field of its own; the
gesture's own `confidence` lives on the `song_event_timeline.json` row.

Nothing here reads audio. Every input is a *published* top-level file
(`sections.json`, `beats.json`, `drum_events.json`, `loudness.json`,
`arrangement_state.json`, `song_event_timeline.json`), the phase-3-safe
pre-computed `artifacts/whisperx-vad/vocal_onsets.json` (D10.1 — a second
output of the `whisperx` service, never raw audio by the time this stage
runs), or `reference/human/{segments.json,segments.seed.json}`.

**Precedence, per field, per section** (refinement item 6):

1. `reference/human/segments.json` value — source `human`.
2. the highest-confidence candidate producer that computed a value for this
   field on this section — source is that producer's name.
3. `reference/human/segments.seed.json` value — source `seed_unreviewed`,
   confidence explicitly `null` (an inferred seed, not yet operator-reviewed).
4. otherwise the field is simply absent from the row — never a guessed
   default (CLAUDE.md "no silent fallbacks").

`segments.json`/`segments.seed.json` spans need not line up with
`sections.json`'s own boundaries (the segment editor's spans are
independently authored). Tier 1/3 match a `sections.json` row to whichever
human/seed row overlaps it the most; a section with no overlapping row at
that tier simply has nothing to offer from it.

**Candidate producers** (ported from `experiments/{energy_level,
tension_shape,rhythm_drum_ioi,rhythm_stem_autocorr}`, math shared with
`experiments/rhythm_energy_common.py` — computed here directly against
`sections.json`'s own spans, not the experiments' original segment-span
preference, since the output is fused onto those exact rows):

| field | producer(s) |
| --- | --- |
| `energy` | `energy_level`: 0.5×mean loudness + 0.5×stems-playing fraction, song-relative quintile |
| `tension` | `tension_shape`: loudness slope, +1 gesture build/tension overlap, quintile |
| `rhythm.drums` | `rhythm_drum_ioi`: drum-event IOI / beat period |
| `rhythm.bass`, `rhythm.harmonic` | `rhythm_stem_autocorr`: sub-beat loudness autocorrelation |
| `rhythm.vocals` | `rhythm_stem_autocorr` (autocorrelation) **and** `rhythm_vocal_onsets` (word IOI from `vocal_onsets.json`) — whichever clears the floor with the higher confidence wins per section |

A producer that could not compute a field for a section (no beat grid, too
few onsets, no usable frames) simply has no candidate there — "clearing the
floor" is that non-omission, not a separate numeric threshold; each
producer's own confidence formula (`rhythm_energy_common`) already reports an
honest low number rather than hiding a weak call.

**`field_sources` + per-row overrides.** The file-level header declares one
default producer per field (`energy`, `energy_confidence`, `tension`,
`tension_confidence`, `rhythm.drums`, `rhythm.bass`, `rhythm.harmonic`,
`rhythm.vocals` — dotted keys, the existing convention for a field that is
really per-sub-field, see `arrangement_state.py`'s `vocals_phrase.sibilance`).
A row whose *actual* winning tier differs from that default carries a sparse
override: `energy_source` / `tension_source` on the row itself, and a
`source` key inside the specific `rhythm.<name>` object — generalising
`hints.json`'s per-row `source` field (CLAUDE.md "published files are fused
and attributed"). No override key appears when the row matches the file
default — repeating an identical source on every row is pure token cost.

Never mutates in place from scratch: like `contest-section-function`, this
stage re-fuses the already-published `sections.json`, adding these fields on
top of build-ui-data's output.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyzer.exceptions import AnalysisError
from analyzer.io import read_json, write_json
from analyzer.models import validate_field_sources
from analyzer.paths import SongPaths

# ---------------------------------------------------------------------------
# Shared subdivision/confidence math, ported from experiments/
# rhythm_energy_common.py + experiments/segment_seeds/features.py. Not
# reimported from experiments/ — CLAUDE.md: "src/ never imports from
# experiments/".
# ---------------------------------------------------------------------------

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

#: loudness.json / arrangement_state.json stem order after "mix".
STEM_IDS = ("bass", "drums", "harmonic", "vocals")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _subdivision_from_ratio(
    ratio: float | None, *, below_frac: float | None = None
) -> tuple[str | None, float | None]:
    """Nearest `SUBDIVISIONS` name to `ratio` by log-distance. Confidence is
    the normalised margin between the best and second-best candidate.
    `below_frac` (0..1): the caller has already decided "none" (an onset rate
    below its per-bar/beat floor) — confidence is the honest distance below
    that floor."""
    if below_frac is not None:
        return "none", round(_clamp01(1.0 - below_frac), 4)
    if ratio is None or ratio <= 0:
        return None, None
    dists = sorted(
        (abs(np.log(ratio) - np.log(target)), name)
        for name, target in SUBDIVISIONS.items()
    )
    best_dist, best_name = dists[0]
    second_dist = dists[1][0] if len(dists) > 1 else best_dist + 1.0
    denom = best_dist + second_dist
    conf = (second_dist - best_dist) / denom if denom > 0 else 0.0
    return best_name, round(_clamp01(conf), 4)


def _dominant_ioi_ratio(onset_times: list[float], beat_period: float) -> float | None:
    times = sorted(onset_times)
    if len(times) < 2 or not beat_period or beat_period <= 0:
        return None
    iois = np.diff(np.array(times, dtype=float))
    iois = iois[iois > 0]
    if iois.size == 0:
        return None
    return float(np.median(iois)) / beat_period


def _autocorr_subdivision(
    xs: np.ndarray, interval_s: float, beat_period: float | None
) -> tuple[str | None, float | None]:
    if xs.size < 8 or not beat_period or beat_period <= 0:
        return None, None
    xs = xs - xs.mean()
    denom = float(np.sum(xs * xs))
    if denom <= 1e-9:
        return "none", 0.0
    scored: list[tuple[float, str]] = []
    for name, frac in SUBDIVISIONS.items():
        lag = int(round((beat_period * frac) / interval_s))
        if lag <= 0 or lag >= xs.size:
            continue
        a, b = xs[:-lag], xs[lag:]
        corr = float(np.sum(a * b) / denom)
        scored.append((corr, name))
    if not scored:
        return None, None
    scored.sort(reverse=True)
    best_corr, best_name = scored[0]
    second_corr = scored[1][0] if len(scored) > 1 else -1.0
    if best_corr < MIN_AUTOCORR:
        return "none", round(_clamp01(1.0 - best_corr / MIN_AUTOCORR), 4)
    denom2 = abs(best_corr) + abs(second_corr)
    conf = (best_corr - second_corr) / denom2 if denom2 > 0 else 0.0
    return best_name, round(_clamp01(conf), 4)


def _quintile_with_margin(raw_scores: list[float]) -> list[tuple[int, float]]:
    n = len(raw_scores)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: (raw_scores[i], i))
    out: list[tuple[int, float]] = [(0, 0.0)] * n
    for rank, i in enumerate(order):
        frac = (rank + 0.5) / n
        bin_frac = frac * 5.0
        b = min(5, max(1, int(np.ceil(bin_frac))))
        dist = min(bin_frac - np.floor(bin_frac), np.ceil(bin_frac) - bin_frac)
        conf = round(_clamp01(2.0 * float(dist)), 4)
        out[i] = (b, conf)
    return out


def _beat_period_near(beats: dict | None, start: float, end: float) -> float | None:
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


def _source_index(loudness: dict | None, source_id: str) -> int | None:
    if not loudness:
        return None
    for i, s in enumerate(loudness.get("sources") or loudness.get("source_order") or []):
        sid = s.get("id") if isinstance(s, dict) else s
        if sid == source_id:
            return i
    return None


def _mean_in_span(loudness: dict | None, idx: int | None, start: float, end: float) -> float:
    if loudness is None or idx is None:
        return 0.0
    key = "normalized_values" if loudness.get("frames") and "normalized_values" in loudness["frames"][0] else "values"
    vals = [f[key][idx] for f in loudness["frames"] if start <= f["time"] < end]
    if not vals:
        return 0.0
    return float(np.mean(vals))


def _frames_in_span(loudness: dict, idx: int, start: float, end: float) -> np.ndarray:
    key = "normalized_values" if loudness.get("frames") and "normalized_values" in loudness["frames"][0] else "values"
    return np.array(
        [f[key][idx] for f in loudness["frames"] if start <= f["time"] < end], dtype=float
    )


def _stems_playing_fraction(arrangement: dict | None, start: float, end: float, total_stems: int) -> float:
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


def _vocals_phrase_overlap(arrangement: dict | None, start: float, end: float) -> bool:
    phrases = (arrangement or {}).get("vocals_phrase") or []
    for p in phrases:
        ps, pe = p.get("start_s") if "start_s" in p else p.get("start"), p.get("end_s") if "end_s" in p else p.get("end")
        if ps is None or pe is None:
            continue
        if min(end, pe) - max(start, ps) > 0:
            return True
    return False


def _impact_events(event_timeline: dict | None) -> list[dict]:
    events = (event_timeline or {}).get("events") or []
    return [e for e in events if e.get("type") == "impact" and e.get("start_time") is not None]


def _nearest_impact_alignment(
    start: float, impacts: list[dict], bpm: float | None
) -> dict | None:
    """Nearest gesture impact (by `start_time`) to a section's `start`.
    `null` when none falls within +-2 bars — an honest omission, never a
    nearest-match at any distance (CLAUDE.md "no silent fallbacks"). Bar
    length is derived from the song's whole-song `bpm` (info.json) assuming
    4/4 (corpus-wide assumption, see docs/analysis-definition.md). `offset_s`
    is signed (`impact_time - start`; positive = late).
    `impact_position` is left `null` here — item 5's `mcp/serializers.py`
    `position` deriver backfills it on read; nothing is stored in bars."""
    if not impacts or not bpm or bpm <= 0:
        return None
    beat_period = 60.0 / bpm
    bar_s = beat_period * 4.0
    max_distance = 2.0 * bar_s
    best: dict | None = None
    best_dist: float | None = None
    for e in impacts:
        t = float(e["start_time"])
        dist = abs(t - start)
        if best_dist is None or dist < best_dist:
            best_dist, best = dist, e
    if best is None or best_dist is None or best_dist > max_distance:
        return None
    impact_time = float(best["start_time"])
    offset_s = round(impact_time - start, 3)
    offset_beats = round(offset_s / beat_period, 3)
    return {
        "gesture_id": best.get("gesture_id"),
        "impact_time": round(impact_time, 3),
        "offset_s": offset_s,
        "offset_beats": offset_beats,
        "impact_position": None,
    }


def _gesture_tension_overlap(event_timeline: dict | None, start: float, end: float) -> bool:
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


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def _best_overlap_row(rows: list[dict], start: float, end: float) -> dict | None:
    """The row (from `segments.json`/`segments.seed.json`) with the greatest
    temporal overlap with `[start, end)`. `None` when nothing overlaps."""
    best: dict | None = None
    best_overlap = 0.0
    for row in rows:
        rs, re = float(row["start"]), float(row["end"])
        ov = _overlap(start, end, rs, re)
        if ov > best_overlap:
            best_overlap, best = ov, row
    return best


# ---------------------------------------------------------------------------
# Candidate producers — each returns {section_id: (value, confidence)} (or,
# for rhythm, {section_id: {source_name: (subdivision, confidence,
# onsets_per_beat_or_None)}}). A section absent from the dict means the
# producer could not compute that field there (no silent fallback).
# ---------------------------------------------------------------------------


def _energy_level(sections: list[dict], loudness: dict | None, arrangement: dict | None) -> dict[str, tuple[int, float]]:
    if loudness is None or not sections:
        return {}
    mix_idx = _source_index(loudness, "mix")
    raw: list[float] = []
    ids: list[str] = []
    for s in sections:
        start, end = float(s["start"]), float(s["end"])
        mix_mean = _mean_in_span(loudness, mix_idx, start, end)
        stems_frac = _stems_playing_fraction(arrangement, start, end, len(STEM_IDS))
        raw.append(0.5 * mix_mean + 0.5 * stems_frac)
        ids.append(s["section_id"])
    binned = _quintile_with_margin(raw)
    return {sid: (int(val), conf) for sid, (val, conf) in zip(ids, binned)}


def _tension_shape(
    sections: list[dict], loudness: dict | None, event_timeline: dict | None
) -> dict[str, tuple[int, float]]:
    if loudness is None or not sections:
        return {}
    mix_idx = _source_index(loudness, "mix")
    raw: list[float] = []
    bumps: list[bool] = []
    ids: list[str] = []
    for s in sections:
        start, end = float(s["start"]), float(s["end"])
        mid = (start + end) / 2.0
        first_mean = _mean_in_span(loudness, mix_idx, start, mid)
        second_mean = _mean_in_span(loudness, mix_idx, mid, end)
        raw.append(second_mean - first_mean)
        bumps.append(_gesture_tension_overlap(event_timeline, start, end))
        ids.append(s["section_id"])
    binned = _quintile_with_margin(raw)
    out: dict[str, tuple[int, float]] = {}
    for sid, (val, conf), bump in zip(ids, binned, bumps):
        bumped = min(5, val + (1 if bump else 0))
        out[sid] = (int(bumped), conf)
    return out


def _rhythm_drum_ioi(
    sections: list[dict], beats: dict | None, drum_events: dict | None
) -> dict[str, tuple[str, float, float | None]]:
    events = (drum_events or {}).get("events") or []
    out: dict[str, tuple[str, float, float | None]] = {}
    for s in sections:
        start, end = float(s["start"]), float(s["end"])
        beat_period = _beat_period_near(beats, start, end)
        if not beat_period or beat_period <= 0:
            continue
        onsets = sorted(e["time"] for e in events if start <= e["time"] < end)
        span_bars = (end - start) / (beat_period * 4.0)
        if span_bars <= 0 or len(onsets) < 2:
            continue
        onsets_per_bar = len(onsets) / span_bars
        if onsets_per_bar < 1.0:
            name, conf = _subdivision_from_ratio(None, below_frac=onsets_per_bar)
        else:
            ratio = _dominant_ioi_ratio(onsets, beat_period)
            if ratio is None:
                continue
            name, conf = _subdivision_from_ratio(ratio)
        if name is None:
            continue
        out[s["section_id"]] = (name, conf, round(onsets_per_bar / 4.0, 3))
    return out


def _rhythm_stem_autocorr(
    sections: list[dict], beats: dict | None, loudness: dict | None, arrangement: dict | None
) -> dict[str, dict[str, tuple[str, float]]]:
    if loudness is None:
        return {}
    interval_s = (loudness.get("interval_ms") or (loudness.get("metadata") or {}).get("interval_ms") or 20) / 1000.0
    out: dict[str, dict[str, tuple[str, float]]] = {}
    for s in sections:
        start, end = float(s["start"]), float(s["end"])
        beat_period = _beat_period_near(beats, start, end)
        if not beat_period or beat_period <= 0:
            continue
        per_source: dict[str, tuple[str, float]] = {}
        for stem in STEM_IDS:
            if stem == "vocals" and not _vocals_phrase_overlap(arrangement, start, end):
                per_source["vocals"] = ("none", 1.0)
                continue
            idx = _source_index(loudness, stem)
            if idx is None:
                continue
            xs = _frames_in_span(loudness, idx, start, end)
            name, conf = _autocorr_subdivision(xs, interval_s, beat_period)
            if name is None:
                continue
            per_source[stem] = (name, conf)
        if per_source:
            out[s["section_id"]] = per_source
    return out


def _rhythm_vocal_onsets(
    sections: list[dict], beats: dict | None, vocal_onsets: dict | None
) -> dict[str, tuple[str, float, float | None]]:
    words = (vocal_onsets or {}).get("words") or []
    onsets = sorted(float(w["time"]) for w in words)
    out: dict[str, tuple[str, float, float | None]] = {}
    for s in sections:
        start, end = float(s["start"]), float(s["end"])
        beat_period = _beat_period_near(beats, start, end)
        if not beat_period or beat_period <= 0:
            continue
        span_onsets = [t for t in onsets if start <= t < end]
        n_beats = (end - start) / beat_period
        onsets_per_beat = round(len(span_onsets) / n_beats, 3) if n_beats > 0 else None
        if len(span_onsets) < 2:
            continue
        ratio = _dominant_ioi_ratio(span_onsets, beat_period)
        if ratio is None:
            continue
        name, conf = _subdivision_from_ratio(ratio)
        if name is None:
            continue
        out[s["section_id"]] = (name, conf, onsets_per_beat)
    return out


# ---------------------------------------------------------------------------
# Human / seed tiers
# ---------------------------------------------------------------------------


def _load_rows(path) -> list[dict]:
    if not path.exists():
        return []
    data = read_json(path)
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Precedence fuse
# ---------------------------------------------------------------------------


def _resolve_scalar(
    *,
    human_row: dict | None,
    seed_row: dict | None,
    field: str,
    producer_name: str,
    producer_values: dict[str, tuple[Any, float]],
    section_id: str,
) -> tuple[Any, float | None, str] | None:
    """Tier 1 -> 2 -> 3 for a scalar field (`energy`/`tension`). Returns
    `(value, confidence, source)` or `None` if no tier has anything."""
    if human_row is not None and human_row.get(field) is not None:
        return human_row[field], None, "human"
    if section_id in producer_values:
        val, conf = producer_values[section_id]
        return val, conf, producer_name
    if seed_row is not None and seed_row.get(field) is not None:
        return seed_row[field], None, "seed_unreviewed"
    return None


def _resolve_rhythm_source(
    *,
    human_row: dict | None,
    seed_row: dict | None,
    source_name: str,
    candidates: list[tuple[str, str, float, float | None]],
) -> tuple[str, float | None, float | None, str] | None:
    """Tier 1 -> 2 -> 3 for one `rhythm.<source_name>` entry. `candidates` is
    a list of `(producer_name, subdivision, confidence, onsets_per_beat)`
    from every producer that computed something for this source; the
    highest-confidence one wins tier 2. Returns
    `(subdivision, confidence, onsets_per_beat, source)` or `None`."""
    human_rhythm = (human_row or {}).get("rhythm") or {}
    if source_name in human_rhythm and human_rhythm[source_name] is not None:
        return human_rhythm[source_name], None, None, "human"
    if candidates:
        producer_name, subdivision, conf, opb = max(candidates, key=lambda c: c[2])
        return subdivision, conf, opb, producer_name
    seed_rhythm = (seed_row or {}).get("rhythm") or {}
    if source_name in seed_rhythm and seed_rhythm[source_name] is not None:
        return seed_rhythm[source_name], None, None, "seed_unreviewed"
    return None


# ---------------------------------------------------------------------------
# Stage entry point
# ---------------------------------------------------------------------------

FIELD_SOURCES_DEFAULT = {
    "energy": "energy_level",
    "energy_confidence": "energy_level",
    "tension": "tension_shape",
    "tension_confidence": "tension_shape",
    "rhythm.drums": "rhythm_drum_ioi",
    "rhythm.bass": "rhythm_stem_autocorr",
    "rhythm.harmonic": "rhythm_stem_autocorr",
    "rhythm.vocals": "rhythm_stem_autocorr",
    "impact_alignment": "impact_alignment",
}


def section_clues(paths: SongPaths) -> dict:
    """Stage entry point. Re-fuses the published `sections.json`, adding
    `energy`, `energy_confidence`, `tension`, `tension_confidence` and
    `rhythm` per the precedence rule documented above."""
    sections_payload = read_json(paths.sections_output_path)
    sections = sections_payload["sections"]

    beats = read_json(paths.beats_output_path) if paths.beats_output_path.exists() else None
    drum_events = read_json(paths.drum_events_output_path) if paths.drum_events_output_path.exists() else None
    loudness = read_json(paths.loudness_output_path) if paths.loudness_output_path.exists() else None
    arrangement = read_json(paths.arrangement_state_output_path) if paths.arrangement_state_output_path.exists() else None
    event_timeline = read_json(paths.timeline_output_path) if paths.timeline_output_path.exists() else None

    vocal_onsets_path = paths.artifact("whisperx-vad", "vocal_onsets.json")
    if not vocal_onsets_path.exists():
        raise AnalysisError(
            f"section-clues requires artifacts/whisperx-vad/vocal_onsets.json "
            f"(D10.1) — run the 'whisperx' service for {paths.song_name!r} first."
        )
    vocal_onsets = read_json(vocal_onsets_path)

    info_payload = read_json(paths.info_output_path) if paths.info_output_path.exists() else None
    bpm = (info_payload or {}).get("bpm")
    impacts = _impact_events(event_timeline)

    human_rows = _load_rows(paths.reference("human", "segments.json"))
    seed_rows = _load_rows(paths.reference("human", "segments.seed.json"))

    energy_vals = _energy_level(sections, loudness, arrangement)
    tension_vals = _tension_shape(sections, loudness, event_timeline)
    drum_rhythm = _rhythm_drum_ioi(sections, beats, drum_events)
    stem_rhythm = _rhythm_stem_autocorr(sections, beats, loudness, arrangement)
    vocal_onset_rhythm = _rhythm_vocal_onsets(sections, beats, vocal_onsets)

    any_seed = False
    seed_section_ids: list[str] = []
    emitted_keys: set[str] = set()
    rhythm_sources_emitted: set[str] = set()

    for section in sections:
        sid = section["section_id"]
        start, end = float(section["start"]), float(section["end"])
        human_row = _best_overlap_row(human_rows, start, end)
        seed_row = _best_overlap_row(seed_rows, start, end)

        resolved_any_seed_here = False

        energy_resolved = _resolve_scalar(
            human_row=human_row, seed_row=seed_row, field="energy",
            producer_name="energy_level", producer_values=energy_vals, section_id=sid,
        )
        if energy_resolved is not None:
            val, conf, source = energy_resolved
            section["energy"] = val
            section["energy_confidence"] = conf
            emitted_keys.add("energy")
            emitted_keys.add("energy_confidence")
            if source != FIELD_SOURCES_DEFAULT["energy"]:
                section["energy_source"] = source
            if source == "seed_unreviewed":
                resolved_any_seed_here = True

        tension_resolved = _resolve_scalar(
            human_row=human_row, seed_row=seed_row, field="tension",
            producer_name="tension_shape", producer_values=tension_vals, section_id=sid,
        )
        if tension_resolved is not None:
            val, conf, source = tension_resolved
            section["tension"] = val
            section["tension_confidence"] = conf
            emitted_keys.add("tension")
            emitted_keys.add("tension_confidence")
            if source != FIELD_SOURCES_DEFAULT["tension"]:
                section["tension_source"] = source
            if source == "seed_unreviewed":
                resolved_any_seed_here = True

        rhythm: dict[str, dict] = {}
        for source_name in STEM_IDS:
            candidates: list[tuple[str, str, float, float | None]] = []
            if source_name == "drums" and sid in drum_rhythm:
                name, conf, opb = drum_rhythm[sid]
                candidates.append(("rhythm_drum_ioi", name, conf, opb))
            if sid in stem_rhythm and source_name in stem_rhythm[sid]:
                name, conf = stem_rhythm[sid][source_name]
                candidates.append(("rhythm_stem_autocorr", name, conf, None))
            if source_name == "vocals" and sid in vocal_onset_rhythm:
                name, conf, opb = vocal_onset_rhythm[sid]
                candidates.append(("rhythm_vocal_onsets", name, conf, opb))

            resolved = _resolve_rhythm_source(
                human_row=human_row, seed_row=seed_row, source_name=source_name,
                candidates=candidates,
            )
            if resolved is None:
                continue
            subdivision, conf, opb, source = resolved
            entry: dict[str, Any] = {"subdivision": subdivision, "confidence": conf}
            if opb is not None:
                entry["onsets_per_beat"] = opb
            if source != FIELD_SOURCES_DEFAULT[f"rhythm.{source_name}"]:
                entry["source"] = source
            rhythm[source_name] = entry
            rhythm_sources_emitted.add(source_name)
            if source == "seed_unreviewed":
                resolved_any_seed_here = True

        if rhythm:
            section["rhythm"] = rhythm
            emitted_keys.add("rhythm")

        section["impact_alignment"] = _nearest_impact_alignment(start, impacts, bpm)
        emitted_keys.add("impact_alignment")

        if resolved_any_seed_here:
            any_seed = True
            seed_section_ids.append(sid)

    header = dict(sections_payload.get("field_sources", {}))
    coverage_keys: set[str] = set(sections_payload["field_sources"])
    if "energy" in emitted_keys:
        header["energy"] = FIELD_SOURCES_DEFAULT["energy"]
        header["energy_confidence"] = FIELD_SOURCES_DEFAULT["energy_confidence"]
        coverage_keys.update({"energy", "energy_confidence"})
    if "tension" in emitted_keys:
        header["tension"] = FIELD_SOURCES_DEFAULT["tension"]
        header["tension_confidence"] = FIELD_SOURCES_DEFAULT["tension_confidence"]
        coverage_keys.update({"tension", "tension_confidence"})
    for source_name in sorted(rhythm_sources_emitted):
        header[f"rhythm.{source_name}"] = FIELD_SOURCES_DEFAULT[f"rhythm.{source_name}"]
    if "impact_alignment" in emitted_keys:
        header["impact_alignment"] = FIELD_SOURCES_DEFAULT["impact_alignment"]
        coverage_keys.add("impact_alignment")

    sections_payload["field_sources"] = validate_field_sources(
        header,
        coverage_keys,
        file="sections.json",
        exempt=("energy_source", "tension_source", "rhythm"),
    )
    write_json(paths.sections_output_path, sections_payload)

    return {
        "sections_with_seed_unreviewed": seed_section_ids,
        "any_seed_unreviewed": any_seed,
    }
