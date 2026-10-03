"""Compute (audio -> cache) and export (`reference/proposals/filter_sweep_v2.json`).

cache: `half_beats[]` (features.py columns, NaN -> null), `bars[]` aligned one-to-one with
`experiments/bar_features` bars (same windows from `beats.json`): `bar`, `start_s`, `end_s`,
`median` (hl / roll / peak per bar), `slope` {series: {N: [slope, cons]}}, `state`.

proposal: `blocks[]` -- one per sweep run: `direction`, `start_s`, `end_s` (the run),
`end_time` (first beat of the bar after, on the grid), `end_bar`, `end_kind` (top|cut),
`aftermath` (gap|drop|break|none), `hl_change_db`, `roll_change_oct`, `consistency`,
`confidence` -- plus `bars[]` (bar, start_s, state, hl/roll slope over 4 bars).
"""
from __future__ import annotations

import datetime
import json
import math

import librosa
import numpy as np

from experiments.bar_features import features as bf_features

from . import aftermath, detect, features, paths

SCHEMA_VERSION = "1.0"
NONE_PENALTY = 0.5
HL_FULL_DB = 15.0


def _nan(v):
    return None if isinstance(v, float) and math.isnan(v) else v


def compute(song: str) -> dict:
    wav = paths.harmonic_wav_path(song)
    if not wav.exists():
        raise FileNotFoundError(f"harmonic stem missing: {wav}")
    y, sr = librosa.load(str(wav), sr=features.SR, mono=True)
    beats = json.loads(paths.beats_path(song).read_text())["beats"]
    bars, _ = bf_features.build_windows(beats)
    beat_t = np.array([float(b["time"]) for b in beats])
    bar_len = 4.0 * float(np.median(np.diff(beat_t)))
    times, power, centres, _ = features.log_spectrogram(y, sr)
    rows = features.half_beat_rows(times, power, centres, beat_t)
    detect.add_log_columns(rows)
    bar_idx, beat_bar = -1, []
    last = None
    for b in beats:
        if b["bar"] != last:
            bar_idx += 1
            last = b["bar"]
        beat_bar.append(bar_idx)
    row_bar = [beat_bar[r["beat_index"]] for r in rows]
    slopes = detect.bar_slopes(rows, row_bar, len(bars), bar_len)
    states = detect.bar_states(slopes)
    out_bars = []
    for i, b in enumerate(bars):
        out_bars.append({
            "bar": b["bar"], "start_s": round(b["start_s"], 3), "end_s": round(b["end_s"], 3),
            "median": {k: (None if v is None else round(v, 3)) for k, v in slopes[i]["median"].items()},
            "slope": {k: {str(n): [None if s is None else round(s, 4), None if c is None else round(c, 3)]
                          for n, (s, c) in slopes[i][k].items()} for k in detect.SERIES},
            "state": states[i],
        })
    payload = {
        "song": song, "bar_len": round(bar_len, 4), "bars": out_bars,
        "half_beats": [{k: (round(v, 3) if isinstance(v, float) and not math.isnan(v) else _nan(v)) for k, v in r.items()}
                       for r in rows],
    }
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload) + "\n")
    return payload


def load_cache(song: str) -> dict:
    p = paths.cache_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no cache for {song!r} — run `run compute --song {song!r}` first")
    return json.loads(p.read_text())


def build_blocks(cache: dict, bf_bars: list[dict]) -> list[dict]:
    bars = cache["bars"]
    if [b["bar"] for b in bars] != [b["bar"] for b in bf_bars]:
        raise ValueError(f"{cache['song']}: bar windows differ from bar_features — recompute both")
    blocks = []
    for i, j, direction in detect.runs_of([b["state"] for b in bars]):
        sign = 1.0 if direction == "opening" else -1.0
        med = lambda k, idx: bars[idx]["median"][k]  # noqa: E731
        hl0, hl1 = med("hl", i), med("hl", j)
        r0, r1 = med("roll", i), med("roll", j)
        hl_change = None if hl0 is None or hl1 is None else hl1 - hl0
        roll_change = None if r0 is None or r1 is None else r1 - r0
        cons = [c for b in bars[i:j + 1] for k in ("hl", "roll") for s, c in [b["slope"][k]["4"]]
                if s is not None and c is not None and s * sign > 0]
        consistency = float(np.mean(cons)) if cons else 0.0
        e = j + 1
        end_bar = bars[e] if e < len(bars) else None
        after = aftermath.classify(bf_bars, j)
        kind = detect.end_kind(direction, hl1, med("hl", e) if end_bar else None)
        depth = 0.0 if hl_change is None else min(max(sign * hl_change, 0.0) / HL_FULL_DB, 1.0)
        conf = (0.3 + 0.7 * (0.5 * consistency + 0.5 * depth)) * (NONE_PENALTY if after == "none" else 1.0)
        blocks.append({
            "direction": direction, "start_s": bars[i]["start_s"], "end_s": bars[j]["end_s"],
            "start_bar": bars[i]["bar"], "end_bar": end_bar["bar"] if end_bar else None,
            "end_time": end_bar["start_s"] if end_bar else bars[j]["end_s"],
            "end_kind": kind, "aftermath": after,
            "hl_change_db": None if hl_change is None else round(hl_change, 2),
            "roll_change_oct": None if roll_change is None else round(roll_change, 2),
            "consistency": round(consistency, 3), "confidence": round(conf, 3),
        })
    return blocks


def export(song: str) -> dict:
    cache = load_cache(song)
    bf_bars = bf_features.compute(song)["bars"]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/filter_sweep_v2",
            "engine": "harmonic-stem log-frequency spectrogram (6 bins/octave, 100 Hz-15.5 kHz) per half beat: "
                      "high/low energy ratio (>2 kHz vs <500 Hz) and 99 % rolloff; trailing 4/8-bar slope with "
                      "consistency; sweep end on the first beat after the run; aftermath from bar_features",
            "inputs": ["artifacts/stems/harmonic.wav", "beats.json", "experiments/bar_features table"],
            "params": {"hl_slope_db_per_bar": detect.HL_SLOPE, "roll_slope_oct_per_bar": detect.ROLL_SLOPE,
                       "min_consistency": detect.MIN_CONS, "min_run_bars": detect.MIN_RUN_BARS,
                       "cut_db": detect.CUT_DB, "hole_ratio": aftermath.HOLE_RATIO,
                       "drop_ratio": aftermath.DROP_RATIO, "none_confidence_factor": NONE_PENALTY},
            "confidence_reason": "heuristic 0.3 + 0.7 x (consistency, depth), halved when nothing follows; not calibrated",
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "blocks": build_blocks(cache, bf_bars),
        "bars": [{"bar": b["bar"], "start_s": b["start_s"], "state": b["state"],
                  "hl_slope_4": b["slope"]["hl"]["4"][0], "roll_slope_4": b["slope"]["roll"]["4"][0]}
                 for b in cache["bars"]],
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        blocks = export(song)["blocks"]
        print(f"exported {song} — {len(blocks)} sweeps ({sum(b['aftermath'] == 'none' for b in blocks)} with no aftermath)")
