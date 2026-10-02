"""Phase 1 of the experiment: everything measured from the song, cached.

`compute_and_cache` writes `cache/<song>.json`: the trusted-beat list, one
feature row per beat window (kick / bass / vocals / harmonic presence, mix
level, mix 7-band profile) and the edge *candidates* from every input the plan
names. `detect.py` turns candidates into edges, `build.py` turns edges into
phrases. No bar counting anywhere: windows are beat-to-beat; a bar number or a
downbeat is never read (downbeat F1 0.226).

Trust (docs/analysis-definition.md): beat *times* are trusted only outside
`beats.json`'s `off_grid_spans`; `trusted` marks the beats that are.

Kick presence is drums-STEM energy below ~150 Hz (FFT bands `sub` + `bass`,
20-150 Hz) — never `drum_events`' kick, which folds in toms and ghost hits.
"""
from __future__ import annotations

import datetime
import json

import numpy as np

from analyzer.stages import gestures as g

from . import paths

LOUD_IDX = {"mix": 0, "bass": 1, "drums": 2, "harmonic": 3, "vocals": 4}
KICK_BANDS = (0, 1)  # sub 20-60 Hz + bass 60-150 Hz

#: Candidate weights. An edge is accepted when the distinct evidence groups in
#: its cluster sum to >= `detect.ACCEPT_SCORE` (1.5). Set once, from the
#: sources' own roles: a bass/drums stem change is hard evidence; a vocals or
#: pad change is soft; an impact, riser end or roll end alone is never enough.
W_STEM_HARD = 1.0       # bass / drums enters or leaves (arrangement_state)
W_STEM_SOFT = 0.5       # vocals / harmonic enters or leaves
W_PRESENCE = 1.5        # stem_presence_sections boundary: it already survived a 4-bar persistence
                        # test, so on its own it clears ACCEPT_SCORE (the baseline's edges are a floor)
W_PRESENCE_UNRESOLVED = 0.75  # its onset refinement found no crossing: needs corroboration
W_IMPACT = 0.6          # x impact confidence
W_GAP_END = 0.8         # x gap confidence; gap end = the hit it precedes
W_RISER_END = 0.4       # x confidence (riser, reverse cymbal)
W_ROLL_END = 0.4        # x confidence (snare roll)
PERSIST_BEATS = 4.0     # a stem change must hold this long to carry full weight
FLICKER_FACTOR = 0.25


def _load(p):
    return json.loads(p.read_text())


def trusted_flags(beat_times: list[float], spans: list[dict]) -> list[bool]:
    return [not any(s["start"] <= t <= s["end"] for s in spans) for t in beat_times]


def _window_reduce(times: np.ndarray, values: np.ndarray, bounds: np.ndarray, how: str) -> np.ndarray:
    """Per beat window [bounds[i], bounds[i+1]) reduction; NaN when no frame falls in it."""
    out = np.full((len(bounds) - 1,) + values.shape[1:], np.nan)
    lo_idx = np.searchsorted(times, bounds[:-1], side="left")
    hi_idx = np.searchsorted(times, bounds[1:], side="left")
    for i, (lo, hi) in enumerate(zip(lo_idx, hi_idx)):
        if hi > lo:
            seg = values[lo:hi]
            out[i] = seg.max(axis=0) if how == "max" else seg.mean(axis=0)
    return out


def _arrangement_candidates(song: str, beat_len: float) -> list[dict]:
    """Stem entries / exits. arrangement_state flickers (a stem leaves for half a
    beat and returns), so an entry or exit only carries its full weight when the
    new state PERSISTS for `PERSIST_BEATS` beats — the same hysteresis idea as
    stem_presence_sections, applied per stem; a flicker keeps `FLICKER_FACTOR` of it."""
    blocks = _load(paths.arrangement_path(song))["blocks"]
    out = []
    for k, b in enumerate(blocks):
        t = float(b["start_s"])
        if t <= 0:
            continue
        conf = b.get("confidence")
        c = 0.0 if conf is None else float(conf)
        for direction, stems in (("enter", b.get("entered", [])), ("exit", b.get("left", []))):
            for stem in stems:
                # time until this stem flips state again
                until = None
                for nb in blocks[k + 1:]:
                    if (stem in nb.get("playing", [])) != (direction == "enter"):
                        until = float(nb["start_s"])
                        break
                held = (until if until is not None else float(blocks[-1]["end_s"])) - t
                persist = FLICKER_FACTOR if held < PERSIST_BEATS * beat_len else 1.0
                base = W_STEM_HARD if stem in ("bass", "drums") else W_STEM_SOFT
                out.append(_cand(t, f"stem_{direction}:{stem}", f"arr:{stem}", stem, direction,
                                 base * c * persist, c))
    return out


def _cand(t, kind, group, stem, direction, weight, conf):
    return {"t": round(float(t), 3), "kind": kind, "group": group, "stem": stem,
            "dir": direction, "weight": round(float(weight), 4), "conf": round(float(conf), 4)}


_PRESENCE = {"full": (True, True), "bass_only": (True, False),
             "drums_only": (False, True), "stripped": (False, False)}


def _presence_candidates(song: str) -> tuple[list[dict], bool]:
    """`experiments/stem_presence_sections`' state machine, folded in as data:
    each of its boundaries (a bass/drums state change that persisted past its
    hysteresis) is one candidate, tagged with which stem entered or left."""
    p = paths.stem_presence_path(song)
    if not p.exists():
        return [], False
    blocks = _load(p)["blocks"]
    out = []
    for prev, nxt in zip(blocks, blocks[1:]):
        pb, pd = _PRESENCE[prev["state"]]
        nb, nd = _PRESENCE[nxt["state"]]
        w = W_PRESENCE if nxt.get("boundary_resolved") is not False else W_PRESENCE_UNRESOLVED
        for stem, a, b in (("bass", pb, nb), ("drums", pd, nd)):
            if a != b:
                out.append(_cand(nxt["start_s"], f"presence_{'enter' if b else 'exit'}:{stem}",
                                 "presence", stem, "enter" if b else "exit", w, w))
    return out, True


def _primitive_candidates(song: str, impacts: list[dict]) -> tuple[list[dict], dict]:
    """Riser / reverse-cymbal / snare-roll / pre-drop-gap spans from `gestures.py`'s
    own detectors (called as functions; `src/` is not modified)."""
    mix = _load(paths.mix_fft_path(song))["frames"]
    t = np.array([f["time"] for f in mix])
    lv = np.array([f["levels"] for f in mix])
    tr = np.array([f["transient_strength"] for f in mix])
    dr = np.array([f["dropout_strength"] for f in mix])
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
        "pre_drop_gap": g.detect_pre_drop_gaps(t, dr, [{"start": i["start"]} for i in impacts], ebeats),
    }
    cands = []
    for kind, rows in spans.items():
        for r in rows:
            w = {"riser": W_RISER_END, "reverse_cymbal": W_RISER_END,
                 "snare_roll": W_ROLL_END, "pre_drop_gap": W_GAP_END}[kind] * float(r["confidence"])
            cands.append(_cand(r["end"], f"{kind}_end", kind, None, "end", w, r["confidence"]))
    slim = {k: [{"start": r["start"], "end": r["end"], "confidence": r["confidence"]} for r in rows]
            for k, rows in spans.items()}
    return cands, slim


def compute(song: str) -> dict:
    info = _load(paths.info_path(song))
    duration = float(info["duration"])
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

    mix = _load(paths.mix_fft_path(song))["frames"]
    mt = np.array([f["time"] for f in mix])
    ml = np.array([f["levels"] for f in mix])
    bands = _window_reduce(mt, ml, bounds, "mean")  # (n,7)

    impacts = [{"start": float(e["start_time"]), "conf": float(e["confidence"])}
               for e in _load(paths.timeline_path(song))["events"] if e["type"] == "impact"]

    cands = _arrangement_candidates(song, beat_len)
    pres, has_presence = _presence_candidates(song)
    cands += pres
    for im in impacts:
        cands.append(_cand(im["start"], "impact", "impact", None, "hit", W_IMPACT * im["conf"], im["conf"]))
    prim_c, prim = _primitive_candidates(song, impacts)
    cands += prim_c
    cands.sort(key=lambda c: (c["t"], c["kind"]))

    def clean(a):
        return [None if np.isnan(x) else round(float(x), 5) for x in a]

    return {
        "song": song, "duration": duration, "beat_len": round(beat_len, 5),
        "beats": [round(t, 4) for t in beat_times], "trusted": trusted,
        "off_grid_spans": spans,
        "series": {k: clean(v) for k, v in series.items()},
        "bands": [clean(r) for r in bands],
        "candidates": cands, "primitives": prim,
        "inputs": {"stem_presence_sections": has_presence,
                   "filter_sweep": paths.filter_sweep_path(song).exists()},
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
