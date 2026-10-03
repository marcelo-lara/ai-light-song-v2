"""Per-bar and per-half-beat feature table fusing data that already exists.

Nothing is extracted from audio here. Windows come from `beats.json`: a bar is a
run of consecutive beats carrying the same `bar` number, so a bar that is not 4
beats long (a known grid slip, e.g. Medicine-MilkInc bar 16) is *flagged*
(`irregular`, `beats_in_bar`), never repaired — re-anchoring is a later item.

Every window (bar or half-beat) is [start_s, end_s) and receives the fields below;
half-beat rows are slimmed to loudness, mix bands, brightness, transients and drum counts
(`HALF_BEAT_KEYS`):
  loud_rms / loud_norm  mean of loudness.json `values` / `normalized_values` per source
  bands                 mean of the 7 FFT band levels per source (mix + 4 stems)
  brightness, transient_mean, transient_std   mix FFT frames
  kick / snare / hat    drum_events.json counts
  kick_attacks / kick_present   experiments/kick_attacks (v3.12 item 29), mix-audio kick attacks net of
                        echoes; present = >= 2 confident ones in a bar (1 per beat in a bar under 2 beats),
                        >= 1 in a half-beat window (`kick_attacks.present`)
  vocals_cover          fraction covered by arrangement_state `vocals_phrase`
  entered / left / playing   arrangement_state block boundaries in the window / block at the midpoint
  sweep                 fraction overlapped by filter_sweep proposals, per direction
  gestures              song_event_timeline overlap fraction per type (point events: 1.0 if inside)
A missing input file raises; there is no default.
"""
from __future__ import annotations

import json

import numpy as np

from experiments.kick_attacks import present as kick_present_rule

from . import paths

DRUM_TYPES = ("kick", "snare", "hat")
BAND_DECIMALS = 3


def _load(path):
    if not path.exists():
        raise FileNotFoundError(f"bar_features input missing: {path}")
    return json.loads(path.read_text())


def build_windows(beats: list[dict]) -> tuple[list[dict], list[dict]]:
    """(bars, half_beats) from beats.json rows. Last window ends one median beat after the last beat."""
    if len(beats) < 8:
        raise ValueError("fewer than 8 beats — cannot build bar windows")
    times = np.array([float(b["time"]) for b in beats])
    beat_len = float(np.median(np.diff(times)))
    ends = list(times[1:]) + [times[-1] + beat_len]

    bars: list[dict] = []
    halves: list[dict] = []
    for i, b in enumerate(beats):
        s, e = float(times[i]), float(ends[i])
        if not bars or bars[-1]["bar"] != b["bar"]:
            bars.append({"bar": b["bar"], "start_s": s, "end_s": e, "beats_in_bar": 0})
        bars[-1]["end_s"] = e
        bars[-1]["beats_in_bar"] += 1
        mid = (s + e) / 2.0
        halves.append({"bar": b["bar"], "beat": b["beat"], "half": 0, "start_s": s, "end_s": mid})
        halves.append({"bar": b["bar"], "beat": b["beat"], "half": 1, "start_s": mid, "end_s": e})
    for r in bars:
        r["irregular"] = r["beats_in_bar"] != 4
    return bars, halves


def _frame_means(times: np.ndarray, values: np.ndarray, wins: np.ndarray) -> np.ndarray:
    """Mean of `values` rows with time in [s, e) per window; NaN rows for empty windows."""
    flat = values.reshape(len(values), -1)
    lo = np.searchsorted(times, wins[:, 0], side="left")
    hi = np.searchsorted(times, wins[:, 1], side="left")
    csum = np.vstack([np.zeros((1, flat.shape[1])), np.cumsum(flat, axis=0)])
    n = (hi - lo).astype(float)
    out = np.full((len(wins), flat.shape[1]), np.nan)
    ok = n > 0
    out[ok] = (csum[hi[ok]] - csum[lo[ok]]) / n[ok][:, None]
    return out.reshape((len(wins),) + values.shape[1:])


def _frame_std(times: np.ndarray, values: np.ndarray, wins: np.ndarray) -> np.ndarray:
    m = _frame_means(times, values, wins)
    m2 = _frame_means(times, values ** 2, wins)
    return np.sqrt(np.maximum(m2 - m ** 2, 0.0))


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _cover(spans: list[tuple[float, float]], s: float, e: float) -> float:
    """Fraction of [s, e) covered by the union of spans."""
    if e <= s:
        return 0.0
    clipped = sorted((max(a, s), min(b, e)) for a, b in spans if b > s and a < e)
    total, cur = 0.0, None
    for a, b in clipped:
        if cur is None or a > cur[1]:
            if cur:
                total += cur[1] - cur[0]
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    if cur:
        total += cur[1] - cur[0]
    return total / (e - s)


def load_inputs(song: str) -> dict:
    loud = _load(paths.top_path(song, "loudness.json"))
    if tuple(loud["source_order"]) != paths.SOURCES:
        raise ValueError(f"{song}: loudness source_order {loud['source_order']} != {paths.SOURCES}")
    fft = {}
    for src in paths.SOURCES:
        d = _load(paths.fft_path(song, src))
        fft[src] = {
            "t": np.array([f["time"] for f in d["frames"]], dtype=float),
            "levels": np.array([f["levels"] for f in d["frames"]], dtype=float),
            "bright": np.array([f["brightness_ratio"] for f in d["frames"]], dtype=float),
            "trans": np.array([f["transient_strength"] for f in d["frames"]], dtype=float),
        }
    beats = _load(paths.top_path(song, "beats.json"))
    return {
        "beats": beats["beats"],
        "off_grid": [(s["start"], s["end"]) for s in beats.get("off_grid_spans", [])],
        "loud_t": np.array([f["time"] for f in loud["frames"]], dtype=float),
        "loud_rms": np.array([f["values"] for f in loud["frames"]], dtype=float),
        "loud_norm": np.array([f["normalized_values"] for f in loud["frames"]], dtype=float),
        "fft": fft,
        "drums": _load(paths.top_path(song, "drum_events.json"))["events"],
        "arr": _load(paths.top_path(song, "arrangement_state.json")),
        "timeline": _load(paths.top_path(song, "song_event_timeline.json"))["events"],
        "sweeps": _load(paths.filter_sweep_path(song))["blocks"],
        "kick_attacks": _load(paths.kick_attacks_path(song))["events"],
    }


def _rows(windows: list[dict], inp: dict) -> list[dict]:
    wins = np.array([[w["start_s"], w["end_s"]] for w in windows], dtype=float)
    loud_rms = _frame_means(inp["loud_t"], inp["loud_rms"], wins)
    loud_norm = _frame_means(inp["loud_t"], inp["loud_norm"], wins)
    bands = {s: _frame_means(f["t"], f["levels"], wins) for s, f in inp["fft"].items()}
    mix = inp["fft"]["mix"]
    bright = _frame_means(mix["t"], mix["bright"], wins)
    trans_m = _frame_means(mix["t"], mix["trans"], wins)
    trans_s = _frame_std(mix["t"], mix["trans"], wins)

    dt = {k: np.array(sorted(e["time"] for e in inp["drums"] if e["event_type"] == k)) for k in DRUM_TYPES}
    counts = {k: np.searchsorted(v, wins[:, 1], "left") - np.searchsorted(v, wins[:, 0], "left") for k, v in dt.items()}

    arr = inp["arr"]
    voc = [(p["start_s"], p["end_s"]) for p in arr["vocals_phrase"]]
    blocks = arr["blocks"]
    sweeps = {d: [(b["start_s"], b["end_s"]) for b in inp["sweeps"] if b["direction"] == d]
              for d in ("opening", "closing")}
    gest_types = sorted({e["type"] for e in inp["timeline"]})
    points = [e for e in inp["timeline"] if e["end_time"] <= e["start_time"]]
    spans = [e for e in inp["timeline"] if e["end_time"] > e["start_time"]]

    def rnd(v, n=4):
        return None if v is None or np.isnan(v) else round(float(v), n)

    rows = []
    for i, w in enumerate(windows):
        s, e = w["start_s"], w["end_s"]
        is_bar = "beats_in_bar" in w
        min_att = min(kick_present_rule.BAR_MIN_ATTACKS, w["beats_in_bar"]) if is_bar else kick_present_rule.HALF_MIN_ATTACKS
        n_kick, kick_here = kick_present_rule.window_counts(inp["kick_attacks"], s, e, min_att)
        mid = (s + e) / 2.0
        entered: list[str] = []
        left: list[str] = []
        for b in blocks:
            if s <= b["start_s"] < e and b["start_s"] > 0:
                entered += [x for x in b["entered"] if x not in entered]
                left += [x for x in b["left"] if x not in left]
        playing = next((b["playing"] for b in blocks if b["start_s"] <= mid < b["end_s"]), None)
        gest = {}
        for t in gest_types:
            f = _cover([(x["start_time"], x["end_time"]) for x in spans if x["type"] == t], s, e)
            if any(p["type"] == t and s <= p["start_time"] < e for p in points):
                f = 1.0
            if f > 0:
                gest[t] = round(f, 3)
        row = dict(w)
        row.update({
            "start_s": round(s, 3), "end_s": round(e, 3),
            "loud_rms": {src: rnd(loud_rms[i, k], 5) for k, src in enumerate(paths.SOURCES)},
            "loud_norm": {src: rnd(loud_norm[i, k], 5) for k, src in enumerate(paths.SOURCES)},
            "bands": {src: [rnd(x, BAND_DECIMALS) for x in bands[src][i]] for src in paths.SOURCES},
            "brightness": rnd(bright[i]),
            "transient_mean": rnd(trans_m[i]), "transient_std": rnd(trans_s[i]),
            "kick": int(counts["kick"][i]), "snare": int(counts["snare"][i]), "hat": int(counts["hat"][i]),
            "kick_attacks": n_kick, "kick_present": kick_here,
            "vocals_cover": round(_cover(voc, s, e), 3),
            "entered": entered, "left": left, "playing": playing,
            "sweep": {d: round(_cover(sp, s, e), 3) for d, sp in sweeps.items()},
            "gestures": gest,
            "off_grid": _cover(inp["off_grid"], s, e) > 0.5,
        })
        rows.append(row)
    return rows


HALF_BEAT_KEYS = ("bar", "beat", "half", "start_s", "end_s", "loud_rms", "bands_mix", "brightness",
                  "transient_mean", "transient_std", "kick", "snare", "hat", "kick_attacks", "kick_present")


def _slim_half(row: dict) -> dict:
    """Half-beat rows keep the signal columns items 4/5 need; no stems' bands, arrangement or gestures."""
    row = dict(row)
    row["bands_mix"] = row["bands"]["mix"]
    return {k: row[k] for k in HALF_BEAT_KEYS}


def compute(song: str) -> dict:
    inp = load_inputs(song)
    bars, halves = build_windows(inp["beats"])
    return {"song": song, "bars": _rows(bars, inp), "half_beats": [_slim_half(r) for r in _rows(halves, inp)]}


def compute_and_cache(song: str) -> dict:
    payload = compute(song)
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload) + "\n")
    return payload


def load_cache(song: str) -> dict:
    p = paths.cache_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no cache for {song!r} — run `run compute --song {song!r}` first")
    return json.loads(p.read_text())
