"""Phase 1: everything measured from the song, cached (`cache/<song>.json`).

What `label.py` needs that `phrases.json` does not carry:

* per-beat series (kick = drums-stem energy below ~150 Hz, never `drum_events`;
  bass / vocals / mix loudness) to measure a kick or bass ENTRY in a window
  around a candidate drop, independent of the phrase it falls in;
* silence runs ("near-silence across all stems") from the 20 ms `loudness.json`
  frames: mix level and every stem at or below a fraction of the song's own p95;
* snare-roll / riser / reverse-cymbal spans (`gestures.py`'s primitive detectors,
  called as functions) to place a Fill;
* `impact` rows of `song_event_timeline.json` (the hit) and the `vocals_phrase`
  spans of `arrangement_state.json` (a vocal pickup).

Trust (docs/analysis-definition.md): beat *times* only outside `off_grid_spans`.
No bar counting, no downbeat read. `energy`/`tension` do not exist here.
"""
from __future__ import annotations

import datetime
import json

import numpy as np

from analyzer.stages import gestures as g

from . import paths

LOUD_IDX = {"mix": 0, "bass": 1, "drums": 2, "harmonic": 3, "vocals": 4}
KICK_BANDS = (0, 1)  # sub 20-60 Hz + bass 60-150 Hz

# near-silence: mix at or below SIL_MIX_FRAC x the song's mix p95 AND every stem
# at or below SIL_STEM_FRAC x the mix p95; runs shorter than SIL_MIN_S are noise,
# runs separated by <= SIL_MERGE_S are one gap (a single tick inside a gap).
SIL_MIX_FRAC = 0.12
SIL_STEM_FRAC = 0.20
SIL_MIN_S = 0.25
SIL_MERGE_S = 0.12


def _load(p):
    return json.loads(p.read_text())


def trusted_flags(beat_times: list[float], spans: list[dict]) -> list[bool]:
    return [not any(s["start"] <= t <= s["end"] for s in spans) for t in beat_times]


def _window_reduce(times: np.ndarray, values: np.ndarray, bounds: np.ndarray, how: str) -> np.ndarray:
    out = np.full((len(bounds) - 1,) + values.shape[1:], np.nan)
    lo_idx = np.searchsorted(times, bounds[:-1], side="left")
    hi_idx = np.searchsorted(times, bounds[1:], side="left")
    for i, (lo, hi) in enumerate(zip(lo_idx, hi_idx)):
        if hi > lo:
            seg = values[lo:hi]
            out[i] = seg.max(axis=0) if how == "max" else seg.mean(axis=0)
    return out


def silence_runs(times: np.ndarray, mix: np.ndarray, stem_max: np.ndarray) -> list[dict]:
    """Runs where the mix and every stem are near-silent. `depth` = how far under
    the threshold the run's loudest frame is (1.0 = digital silence)."""
    if len(times) == 0:
        return []
    p95 = float(np.percentile(mix, 95))
    if p95 <= 0:
        return []
    quiet = (mix <= SIL_MIX_FRAC * p95) & (stem_max <= SIL_STEM_FRAC * p95)
    runs: list[list[float]] = []
    start = None
    for i, q in enumerate(quiet):
        if q and start is None:
            start = i
        if (not q or i == len(quiet) - 1) and start is not None:
            end = i if q else i - 1
            runs.append([float(times[start]), float(times[end])])
            start = None
    merged: list[list[float]] = []
    for a, b in runs:
        if merged and a - merged[-1][1] <= SIL_MERGE_S:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    out = []
    for a, b in merged:
        if b - a < SIL_MIN_S:
            continue
        sel = (times >= a) & (times <= b)
        peak = float(mix[sel].max()) / (SIL_MIX_FRAC * p95)
        out.append({"start": round(a, 3), "end": round(b, 3), "depth": round(max(0.0, 1.0 - peak), 4)})
    return out


def _primitives(song: str, impacts: list[dict]) -> dict:
    mix = _load(paths.mix_fft_path(song))["frames"]
    t = np.array([f["time"] for f in mix])
    lv = np.array([f["levels"] for f in mix])
    tr = np.array([f["transient_strength"] for f in mix])
    ebeats = _load(paths.essentia_beats_path(song))["beats"]
    rms = _load(paths.rms_path(song))
    ids = [s["id"] for s in rms["sources"]]
    rt = np.array([f["time"] for f in rms["frames"]])
    rm = np.array([f["values"][ids.index("mix")] for f in rms["frames"]])
    events = _load(paths.drum_events_path(song))["events"]
    spans = {
        "riser": g.detect_ramps(lv, t, ebeats, kind="riser"),
        "reverse_cymbal": g.detect_reverse_cymbal(lv, t, tr, rt, rm, ebeats),
        "snare_roll": g.detect_snare_roll(events, ebeats),
    }
    return {k: [{"start": round(float(r["start"]), 3), "end": round(float(r["end"]), 3),
                 "confidence": round(float(r["confidence"]), 4)} for r in rows]
            for k, rows in spans.items()}


def compute(song: str) -> dict:
    duration = float(_load(paths.info_path(song))["duration"])
    bj = _load(paths.beats_path(song))
    beat_times = sorted(float(b["time"]) for b in bj["beats"])
    if len(beat_times) < 8:
        raise ValueError(f"{song!r}: fewer than 8 beats — cannot build beat windows")
    spans = bj.get("off_grid_spans")
    if spans is None:
        raise ValueError(f"{song!r}: beats.json has no off_grid_spans — trust unknown, refusing to guess")
    trusted = trusted_flags(beat_times, spans)
    beat_len = float(np.median(np.diff(beat_times)))
    bounds = np.array(beat_times + [max(duration, beat_times[-1] + beat_len)], dtype=float)

    loud = _load(paths.loudness_path(song))["frames"]
    lt = np.array([f["time"] for f in loud])
    lv = np.array([f["normalized_values"] for f in loud])
    series = {stem: _window_reduce(lt, lv[:, i], bounds, "mean") for stem, i in LOUD_IDX.items()}

    dr = _load(paths.drums_fft_path(song))["frames"]
    dt = np.array([f["time"] for f in dr])
    kick = np.array([np.mean([f["levels"][b] for b in KICK_BANDS]) for f in dr])
    series["kick_low"] = _window_reduce(dt, kick, bounds, "max")

    sil = silence_runs(lt, lv[:, 0], lv[:, 1:].max(axis=1))

    impacts = [{"start": round(float(e["start_time"]), 3), "conf": round(float(e["confidence"]), 4)}
               for e in _load(paths.timeline_path(song))["events"] if e["type"] == "impact"]
    vphr = [{"start": round(float(p["start_s"]), 3), "end": round(float(p["end_s"]), 3)}
            for p in _load(paths.arrangement_path(song)).get("vocals_phrase", [])]

    def clean(a):
        return [None if np.isnan(x) else round(float(x), 5) for x in a]

    return {
        "song": song, "duration": duration, "beat_len": round(beat_len, 5),
        "beats": [round(t, 4) for t in beat_times], "trusted": trusted,
        "off_grid_spans": spans,
        "series": {k: clean(v) for k, v in series.items()},
        "silences": sil, "impacts": impacts, "vocal_phrases": vphr,
        "primitives": _primitives(song, impacts),
    }


def compute_and_cache(song: str) -> dict:
    payload = compute(song)
    payload["generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload) + "\n")
    return payload


def load_cache(song: str) -> dict:
    p = paths.cache_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no cache for {song!r} — run `run.py compute --song {song!r}` first")
    return _load(p)
