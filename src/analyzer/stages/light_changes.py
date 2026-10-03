"""Phase-3 stage `light-changes` (v3.12 item 32): where the light should change inside a section.

Ports `experiments/bar_features` (item 1), `experiments/light_changes` (item 2) and the
sweep slope/state of `experiments/filter_sweep_v2` (item 31). `src/` never imports
`experiments/`; the experiments stay as the reference. Phase 3: reads published files and
phase-1/2 artifacts, **never audio and never `reference/`**. The two audio measurements it
needs are their own stages: `extract-harmonic-spectrum` (1.5, half-beat spectrum of the
harmonic stem) and `detect-kick-attacks` (2.6, kick attacks on the mix).

Inputs: published `beats.json`, `loudness.json`, `drum_events.json`, `arrangement_state.json`;
`artifacts/essentia/fft_bands{,.<stem>}.json`, `artifacts/kick_attacks/kick_attacks.json`,
`artifacts/harmonic_spectrum/half_beats.json`. A missing input raises; there is no default.
Outputs (artifacts only, nothing published here):

  artifacts/light_changes/bar_features.json   per-bar table + slim half-beat table
  artifacts/light_changes/light_changes.json  `points[]`

Per-bar table. A bar is a run of consecutive beats with the same `bar` number; a bar that is
not 4 beats is flagged (`irregular`) and never repaired. Columns: mix/stem loudness, 7 FFT
bands per source, brightness, transients, omnizart drum counts, `kick_attacks` /
`kick_present` (>= 2 confident non-echo attacks in a bar, one per beat in a bar under 2 beats,
>= 1 in a half-beat window), `vocals_cover`, arrangement `entered`/`left`/`playing`,
`sweep_slope` {hl dB/bar, roll oct/bar over the last 4 bars} and `sweep_state`
(opening / closing / null).

Detector (unchanged from the experiment). Channels pooled into groups; each bar is compared
with the median of the previous <= 8 bars of the current segment; per channel robust z; a
bar fires when S = sum_g clip(max|z|_g - Z0, 0, ZCAP) >= S_THRESHOLD. A point starts a new
segment; the bar after a point may fire on a staged second step; a window under 2 beats is
merged into the next. Roles are ordered rules over the signed group deltas (`gap`, `drop`,
`fill`, `groove_in`, `build`, `break`); anything no rule claims is `unknown`, never a guessed
role. `confidence` is `null`: the pooled score is not calibrated against any ground truth.

Added in this port:

* Sweep state as a detector input. A step detector is blind to a slow ramp (Armin bars
  55-58). Inside each `opening` / `closing` run of `sweep_state`, the *onset* of the final
  monotone climb of the bar-median high/low ratio is found by walking back from the run's
  last bar while the series does not fall. A climb of >= SWEEP_MIN_BARS bars and
  >= SWEEP_MIN_RISE_DB makes a point at that bar (`source: "sweep"`, role `build` for
  opening, `break` for closing). A step point within SWEEP_MERGE_BARS bars of it is kept
  instead and tagged with the sweep direction.
* Point time = the beat where the change physically starts. A step point sits on its
  bar's first beat; the half-beat table moves it to the beat that contains the change's
  first half-beat when that is within one beat of the bar edge (`bar_edge_offset_beats`
  -1, 0 or +1). Per channel of the groups that fired (loudness, low/high band, brightness,
  transients, drum hits and kick attacks) the pre state is the median of the 6 half-beats
  before the bar edge less 1 beat, the post state the median of the 6 half-beats from edge
  +1 beat; each half-beat is "post side" if past the midpoint. The boundary whose two
  half-beats before are on the pre side and two after on the post side (most channels
  agreeing) wins, and only if it beats the bar edge by MOVE_MARGIN. The half-beat is then snapped
  to the beat that contains it, so a point is always on the published beat grid and
  never later than the physical onset. A sweep point has no beat-scale onset and stays on the
  bar's first beat. Where the grid is off, the point is on `beats.json`'s beats anyway;
  `irregular_bar` says so.

Thresholds S_THRESHOLD 7 (the highest round value that kept the experiment's 7/8
validation hits), the role rules, the sweep thresholds (HL_SLOPE 1.5, ROLL_SLOPE 0.15,
MIN_CONS 0.6, DROPOUT_DB 6, MIN_RUN_BARS 3) and the SWEEP_MIN_* / MOVE_MARGIN constants were
set while looking at Medicine-MilkInc and Armin - Revolution (and, for the point-time
check, ayuni and Charli-VonDutch): validation songs, not a held-out set.
Deterministic: no randomness, no timestamps.
"""
from __future__ import annotations

import numpy as np

from analyzer.exceptions import AnalysisError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths
from analyzer.stages import kick_attacks as kick_rule

SOURCES = ("mix", "bass", "drums", "harmonic", "vocals")   # == loudness.json source_order
STEMS = SOURCES[1:]
DRUM_TYPES = ("kick", "snare", "hat")
BAND_DECIMALS = 3

# ---- detector (experiments/light_changes) ----
REF_MAX = 8
Z0 = 2.0
STAGE_RISE = 2.5
ZCAP = 5.0
SHORT_BEATS = 2
S_THRESHOLD = 7.0
LOG_EPS = 1e-3
GROUPS = {
    "loudness": ["mix", "bass", "drums", "harmonic"],
    "low_band": ["low_mix", "low_harm", "low_drums"],
    "high_band": ["high_mix", "high_harm", "high_drums"],
    "texture": ["brightness", "transient_mean", "transient_std"],
    "hits": ["kick", "snare", "hat"],
    "vocals": ["vocals", "vocals_cover"],
    "arrangement": ["arrangement"],
    "novelty": ["texture_novelty"],
}
DETECT_GROUPS = {
    "loudness": ["mix"],
    "low_band": ["low_mix"],
    "high_band": ["high_mix"],
    "texture": ["brightness", "transient_mean", "transient_std"],
    "hits": ["kick", "snare", "hat"],
    "vocals": ["vocals_cover"],
    "arrangement": ["arrangement"],
    "novelty": ["texture_novelty"],
}
ONE_SIDED = ("texture_novelty",)
SCALE_FLOOR = {"kick": 1.0, "snare": 1.0, "hat": 1.0, "vocals_cover": 0.25, "arrangement": 1.0}
ARR_Z = 3.0
ROLES = ("groove_in", "build", "break", "drop", "gap", "fill")
NOVELTY_NEAR_S = 0.2
NOVELTY_HOP_S = 0.05
NOVELTY_HALF_WINDOW_S = 1.0

# ---- sweep (experiments/filter_sweep_v2) ----
SWEEP_WINDOWS = (1, 2, 4, 8)
SWEEP_STATE_WINDOWS = (4, 8)
HL_SLOPE = 1.5
ROLL_SLOPE = 0.15
MIN_CONS = 0.6
DROPOUT_DB = 6.0
MIN_RUN_BARS = 3
BRIDGE_BARS = 1
MIN_POINTS = 4
SWEEP_SERIES = {"hl": "hl_db", "roll": "roll_log2", "peak": "peak_log2"}
SWEEP_MIN_BARS = 3
SWEEP_MIN_RISE_DB = HL_SLOPE * MIN_RUN_BARS    # 4.5 dB: the state threshold sustained over the shortest run
SWEEP_MERGE_BARS = 1

# ---- point time (half-beat refinement) ----
PRE_ROWS = range(-8, -2)       # half-beat rows relative to the bar edge
POST_ROWS = range(2, 8)
MIN_SIDE_ROWS = 3
MIN_STEP_SPREAD = 0.1          # a channel counts only if pre->post moved >= this x its song-wide p5-p95 spread
MOVE_MARGIN = 0.15
MAX_HALF_SHIFT = 2             # +- one beat, in half-beat rows

HALF_BEAT_KEYS = ("bar", "beat", "half", "start_s", "end_s", "loud_rms", "bands_mix", "brightness",
                  "transient_mean", "transient_std", "kick", "snare", "hat", "kick_attacks", "kick_present")


# =============================================================== bar table ==

def _need(path):
    if not path.exists():
        raise AnalysisError(f"light-changes input missing: {path}")
    return read_json(path)


def build_windows(beats: list[dict]) -> tuple[list[dict], list[dict]]:
    """(bars, half_beats) from beats.json rows. The last window ends one median beat after the last beat."""
    if len(beats) < 8:
        raise AnalysisError("fewer than 8 beats; cannot build bar windows")
    times = np.array([float(b["time"]) for b in beats])
    beat_len = float(np.median(np.diff(times)))
    ends = list(times[1:]) + [times[-1] + beat_len]
    bars: list[dict] = []
    halves: list[dict] = []
    for i, b in enumerate(beats):
        s, e = float(times[i]), float(ends[i])
        if not bars or bars[-1]["bar"] != b["bar"]:
            bars.append({"bar": b["bar"], "start_s": s, "end_s": e, "beats_in_bar": 0, "beat_index": i})
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


def load_inputs(paths: SongPaths) -> dict:
    loud = _need(paths.loudness_output_path)
    if tuple(loud["source_order"]) != SOURCES:
        raise AnalysisError(f"loudness source_order {loud['source_order']} != {SOURCES}")
    fft = {}
    for src in SOURCES:
        d = _need(paths.artifact("essentia", "fft_bands.json" if src == "mix" else f"fft_bands.{src}.json"))
        fft[src] = {
            "t": np.array([f["time"] for f in d["frames"]], dtype=float),
            "levels": np.array([f["levels"] for f in d["frames"]], dtype=float),
            "bright": np.array([f["brightness_ratio"] for f in d["frames"]], dtype=float),
            "trans": np.array([f["transient_strength"] for f in d["frames"]], dtype=float),
        }
    beats = _need(paths.beats_output_path)
    return {
        "beats": beats["beats"],
        "off_grid": [(s["start"], s["end"]) for s in beats.get("off_grid_spans", [])],
        "loud_t": np.array([f["time"] for f in loud["frames"]], dtype=float),
        "loud_rms": np.array([f["values"] for f in loud["frames"]], dtype=float),
        "loud_norm": np.array([f["normalized_values"] for f in loud["frames"]], dtype=float),
        "fft": fft,
        "drums": _need(paths.drum_events_output_path)["events"],
        "arr": _need(paths.arrangement_state_output_path),
        "kick_attacks": _need(paths.artifact("kick_attacks", "kick_attacks.json"))["events"],
        "spectrum": _need(paths.artifact("harmonic_spectrum", "half_beats.json"))["half_beats"],
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

    def rnd(v, n=4):
        return None if v is None or np.isnan(v) else round(float(v), n)

    rows = []
    for i, w in enumerate(windows):
        s, e = w["start_s"], w["end_s"]
        is_bar = "beats_in_bar" in w
        min_att = min(kick_rule.BAR_MIN_ATTACKS, w["beats_in_bar"]) if is_bar else kick_rule.HALF_MIN_ATTACKS
        n_kick, kick_here = kick_rule.window_counts(inp["kick_attacks"], s, e, min_att)
        mid = (s + e) / 2.0
        entered: list[str] = []
        left: list[str] = []
        for b in blocks:
            if s <= b["start_s"] < e and b["start_s"] > 0:
                entered += [x for x in b["entered"] if x not in entered]
                left += [x for x in b["left"] if x not in left]
        playing = next((b["playing"] for b in blocks if b["start_s"] <= mid < b["end_s"]), None)
        row = dict(w)
        row.update({
            "start_s": round(s, 3), "end_s": round(e, 3),
            "loud_rms": {src: rnd(loud_rms[i, k], 5) for k, src in enumerate(SOURCES)},
            "loud_norm": {src: rnd(loud_norm[i, k], 5) for k, src in enumerate(SOURCES)},
            "bands": {src: [rnd(x, BAND_DECIMALS) for x in bands[src][i]] for src in SOURCES},
            "brightness": rnd(bright[i]),
            "transient_mean": rnd(trans_m[i]), "transient_std": rnd(trans_s[i]),
            "kick": int(counts["kick"][i]), "snare": int(counts["snare"][i]), "hat": int(counts["hat"][i]),
            "kick_attacks": n_kick, "kick_present": kick_here,
            "vocals_cover": round(_cover(voc, s, e), 3),
            "entered": entered, "left": left, "playing": playing,
            "off_grid": _cover(inp["off_grid"], s, e) > 0.5,
        })
        rows.append(row)
    return rows


def _slim_half(row: dict) -> dict:
    row = dict(row)
    row["bands_mix"] = row["bands"]["mix"]
    return {k: row[k] for k in HALF_BEAT_KEYS}


# ================================================================== sweeps ==

def _spectrum_rows(spectrum: list[dict], n_beats: int) -> list[dict]:
    if len(spectrum) != 2 * n_beats:
        raise AnalysisError("harmonic_spectrum half_beats do not match beats.json — rerun extract-harmonic-spectrum")
    nan = float("nan")
    rows = []
    for r in spectrum:
        row = {k: (nan if r[k] is None else float(r[k])) for k in ("peak_hz", "sharpness", "hl_db", "roll_hz", "level_db")}
        row.update({"beat_index": r["beat_index"], "start_s": r["start_s"], "end_s": r["end_s"]})
        row["roll_log2"] = float(np.log2(row["roll_hz"])) if row["roll_hz"] == row["roll_hz"] else nan
        row["peak_log2"] = float(np.log2(row["peak_hz"])) if row["peak_hz"] == row["peak_hz"] else nan
        rows.append(row)
    return rows


def _fit(x: np.ndarray, y: np.ndarray) -> tuple[float | None, float | None]:
    ok = ~np.isnan(y)
    if ok.sum() < MIN_POINTS or np.ptp(x[ok]) == 0:
        return None, None
    x, y = x[ok], y[ok]
    slope = float(np.polyfit(x, y, 1)[0])
    if np.std(y) < 1e-9:
        return slope, 0.0
    return slope, float(abs(np.corrcoef(x, y)[0, 1]))


def bar_slopes(rows: list[dict], row_bar: list[int], n_bars: int, bar_len: float) -> list[dict]:
    """Per bar: {series: {N: (slope, cons)}} over the last N bars (units per bar), plus bar medians
    and a `dropout` flag. A dropout bar carries no state and every window restarts after it."""
    t = np.array([(r["start_s"] + r["end_s"]) / 2.0 for r in rows]) / bar_len
    bar_of = np.array(row_bar)
    vals = {k: np.array([r[c] for r in rows], dtype=float) for k, c in SWEEP_SERIES.items()}
    level = np.array([r["level_db"] for r in rows], dtype=float)
    med_level = [float(np.nanmedian(level[bar_of == i])) if (bar_of == i).any() and not np.all(np.isnan(level[bar_of == i]))
                 else float("nan") for i in range(n_bars)]
    dropout = [False] * n_bars
    for i in range(n_bars):
        ref = np.nanmedian(med_level[max(0, i - 4):i]) if i and not np.all(np.isnan(med_level[max(0, i - 4):i])) else np.nan
        dropout[i] = bool(med_level[i] < ref - DROPOUT_DB)
    out = []
    for i in range(n_bars):
        entry: dict = {"median": {}, "dropout": dropout[i]}
        here = bar_of == i
        for k, v in vals.items():
            entry["median"][k] = float(np.nanmedian(v[here])) if here.any() and not np.all(np.isnan(v[here])) else None
            entry[k] = {}
            for n in SWEEP_WINDOWS:
                first = i - n + 1
                for d in range(first, i + 1):
                    if d >= 0 and dropout[d]:
                        first = d + 1
                m = (bar_of >= first) & (bar_of <= i)
                entry[k][n] = _fit(t[m], v[m])
        out.append(entry)
    return out


def _vote(entry: dict) -> str | None:
    if entry["dropout"]:
        return None
    best: tuple[float, str] | None = None
    for n in SWEEP_STATE_WINDOWS:
        for k, thr in (("hl", HL_SLOPE), ("roll", ROLL_SLOPE)):
            s, c = entry[k][n]
            if s is None or c < MIN_CONS or abs(s) < thr:
                continue
            d = "opening" if s > 0 else "closing"
            if best is None or c > best[0]:
                best = (c, d)
    return best[1] if best else None


def bar_states(slopes: list[dict]) -> list[str | None]:
    st = [_vote(e) for e in slopes]
    for i in range(1, len(st) - BRIDGE_BARS):
        if st[i] is None and st[i - 1] is not None and st[i - 1] == st[i + 1]:
            st[i] = st[i - 1]
    out = list(st)
    for i, j, _ in runs_of(st):
        if j - i + 1 < MIN_RUN_BARS:
            for k in range(i, j + 1):
                out[k] = None
    return out


def runs_of(states: list[str | None]) -> list[tuple[int, int, str]]:
    runs, i = [], 0
    while i < len(states):
        if states[i] is None:
            i += 1
            continue
        j = i
        while j + 1 < len(states) and states[j + 1] == states[i]:
            j += 1
        runs.append((i, j, states[i]))
        i = j + 1
    return runs


def sweep_columns(spectrum: list[dict], beats: list[dict], n_bars: int) -> tuple[list[dict], list[str | None]]:
    """(per-bar slopes, per-bar states) from the half-beat spectrum."""
    rows = _spectrum_rows(spectrum, len(beats))
    beat_t = np.array([float(b["time"]) for b in beats])
    bar_len = 4.0 * float(np.median(np.diff(beat_t)))
    bar_idx, beat_bar, last = -1, [], None
    for b in beats:
        if b["bar"] != last:
            bar_idx += 1
            last = b["bar"]
        beat_bar.append(bar_idx)
    row_bar = [beat_bar[r["beat_index"]] for r in rows]
    slopes = bar_slopes(rows, row_bar, n_bars, bar_len)
    return slopes, bar_states(slopes)


def sweep_onsets(slopes: list[dict], states: list[str | None]) -> list[dict]:
    """One onset per sweep run whose final monotone climb of the bar-median high/low ratio lasts
    >= SWEEP_MIN_BARS bars and rises >= SWEEP_MIN_RISE_DB (sign-flipped for `closing`).
    `i` is the bar index where the climb starts."""
    out = []
    for i, j, direction in runs_of(states):
        sign = 1.0 if direction == "opening" else -1.0
        med = [slopes[k]["median"]["hl"] for k in range(len(slopes))]
        if med[j] is None:
            continue
        start = j
        while start - 1 >= i and med[start - 1] is not None and sign * med[start - 1] <= sign * med[start]:
            start -= 1
        rise = sign * (med[j] - med[start])
        if j - start + 1 >= SWEEP_MIN_BARS and rise >= SWEEP_MIN_RISE_DB:
            out.append({"i": start, "end_i": j, "direction": direction, "rise_db": round(float(rise), 2)})
    return out


# ============================================================ texture novelty ==

def _checkerboard_kernel(half: int) -> np.ndarray:
    size = 2 * half
    g = np.arange(-half, half) + 0.5
    gx, gy = np.meshgrid(g, g)
    gauss = np.exp(-0.5 * (gx**2 + gy**2) / (half / 2.0) ** 2)
    return gauss * (np.sign(gx) * np.sign(gy))


def novelty_curve(features: np.ndarray) -> np.ndarray:
    """Foote checkerboard novelty on a cosine self-similarity matrix, normalised to [0, 1]."""
    half = max(2, int(round(NOVELTY_HALF_WINDOW_S / NOVELTY_HOP_S)))
    unit = features / np.maximum(np.linalg.norm(features, axis=1, keepdims=True), 1e-12)
    s = unit @ unit.T
    k = _checkerboard_kernel(half)
    t = len(s)
    out = np.zeros(t)
    for i in range(t):
        a, b = i - half, i + half
        if a < 0 or b > t:
            continue
        out[i] = float(np.sum(s[a:b, a:b] * k))
    if out.max() > out.min():
        out = (out - out.min()) / (out.max() - out.min())
    return out


def bar_novelty(paths: SongPaths, bar_starts: list[float]) -> list[float]:
    """Peak novelty of the 28-dim per-stem band feature within +-0.2 s of each bar start."""
    times, cols = None, []
    for stem in STEMS:
        d = _need(paths.artifact("essentia", f"fft_bands.{stem}.json"))
        t = np.array([f["time"] for f in d["frames"]], dtype=float)
        if times is None:
            times = t
        elif len(t) != len(times):
            raise AnalysisError(f"stem FFT frame counts differ ({stem})")
        cols.append(np.array([f["levels"] for f in d["frames"]], dtype=np.float32))
    curve = novelty_curve(np.hstack(cols))
    out = []
    for s in bar_starts:
        lo = np.searchsorted(times, s - NOVELTY_NEAR_S, side="left")
        hi = np.searchsorted(times, s + NOVELTY_NEAR_S, side="right")
        out.append(float(curve[lo:hi].max()) if hi > lo else 0.0)
    return out


# ================================================================= detector ==

def channel_matrix(bars: list[dict], texture: list[float] | None) -> tuple[np.ndarray, list[str]]:
    """(n_bars, n_channels). Counts are scaled to a nominal bar so a 1-beat bar is not 'quiet'."""
    dur = np.array([b["end_s"] - b["start_s"] for b in bars], dtype=float)
    nominal = float(np.median(dur))
    k = nominal / np.maximum(dur, 1e-6)
    cols: dict[str, np.ndarray] = {}
    for src in SOURCES:
        cols[src] = np.log(np.array([b["loud_rms"][src] or 0.0 for b in bars], dtype=float) + LOG_EPS)

    def band(src, idx):
        return np.array([np.mean([b["bands"][src][i] for i in idx]) for b in bars], dtype=float)

    cols["low_mix"], cols["low_harm"], cols["low_drums"] = band("mix", (0, 1)), band("harmonic", (0, 1)), band("drums", (0, 1))
    cols["high_mix"], cols["high_harm"], cols["high_drums"] = band("mix", (4, 5, 6)), band("harmonic", (4, 5, 6)), band("drums", (4, 5, 6))
    cols["brightness"] = np.array([b["brightness"] for b in bars], dtype=float)
    cols["transient_mean"] = np.array([b["transient_mean"] for b in bars], dtype=float)
    cols["transient_std"] = np.array([b["transient_std"] for b in bars], dtype=float)
    for c in DRUM_TYPES:
        cols[c] = np.array([b[c] for b in bars], dtype=float) * k
    cols["vocals_cover"] = np.array([b["vocals_cover"] for b in bars], dtype=float)
    cols["arrangement"] = np.array([len(b["entered"]) + len(b["left"]) for b in bars], dtype=float) * ARR_Z
    if texture is not None:
        cols["texture_novelty"] = np.array(texture, dtype=float)
    names = [n for g in GROUPS.values() for n in g if n in cols]
    X = np.stack([cols[n] for n in names], axis=1)
    if np.isnan(X).any():
        raise AnalysisError("bar table has a NaN channel; refusing to guess a value")
    return X, names


def channel_scales(X: np.ndarray, names: list[str]) -> np.ndarray:
    d = np.abs(np.diff(X, axis=0))
    mad = 1.4826 * np.median(np.abs(d - np.median(d, axis=0)), axis=0)
    spread = np.percentile(X, 95, axis=0) - np.percentile(X, 5, axis=0)
    floor = np.array([max(SCALE_FLOOR.get(n, 0.0), 0.1 * s, 1e-6) for n, s in zip(names, spread)])
    for i, n in enumerate(names):
        if n == "arrangement":
            floor[i] = ARR_Z
            mad[i] = 0.0
    return np.maximum(mad, floor)


def group_scores(z: np.ndarray, names: list[str], groups: dict[str, list[str]]) -> dict[str, float]:
    idx = {n: i for i, n in enumerate(names)}
    return {g: float(min(np.abs(z[[idx[m] for m in ms if m in idx]]).max(), 10.0))
            for g, ms in groups.items() if any(m in idx for m in ms)}


def pooled(s_by_group: dict[str, float]) -> float:
    return float(sum(np.clip(s - Z0, 0.0, ZCAP) for s in s_by_group.values()))


def merge_short(X: np.ndarray, names: list[str], bars: list[dict]) -> tuple[np.ndarray, list[dict]]:
    """Merge a window under SHORT_BEATS beats into the next one (a grid slip leaves 1-beat 'bars').
    The merged window keeps the short bar's number and start, so the point lands where the slip starts."""
    dur = np.array([b["end_s"] - b["start_s"] for b in bars], dtype=float)
    nominal = float(np.median(dur))
    arr = names.index("arrangement")
    rows, meta, i = [], [], 0
    while i < len(bars):
        if dur[i] < SHORT_BEATS * nominal / 4.0 and i + 1 < len(bars):
            d0, d1 = dur[i], dur[i + 1]
            row = (X[i] * d0 + X[i + 1] * d1) / (d0 + d1)
            row[arr] = X[i][arr] + X[i + 1][arr]
            rows.append(row)
            meta.append({**bars[i], "end_s": bars[i + 1]["end_s"], "merged": True})
            i += 2
        else:
            rows.append(X[i])
            meta.append({**bars[i], "merged": False})
            i += 1
    return np.stack(rows), meta


def _z(X, names, scale, i, ref):
    z = (X[i] - ref) / scale
    for n in ONE_SIDED:
        if n in names:
            z[names.index(n)] = max(z[names.index(n)], 0.0)
    return z


def segment_walk(X, names, groups, scale, fires, staged: bool = False) -> list[dict]:
    """Walk the bars; `fires(z, s_by_group) -> bool` decides a point. A point starts a new segment.
    `staged`: the bar right after a point also fires if it still differs from the pre-point state and
    some group has escalated by >= STAGE_RISE over what it was at the point."""
    out, seg = [], 0
    last = None
    for i in range(1, len(X)):
        ref = np.median(X[max(seg, i - REF_MAX):i], axis=0)
        z = _z(X, names, scale, i, ref)
        s = group_scores(z, names, groups)
        if fires(z, s):
            out.append({"i": i, "z": z, "s": s, "ref": ref})
            seg, last = i, out[-1]
            continue
        if staged and last is not None and i == last["i"] + 1:
            zp = _z(X, names, scale, i, last["ref"])
            sp = group_scores(zp, names, groups)
            if fires(zp, sp) and any(sp[g] >= Z0 + 2.0 and sp[g] - last["s"].get(g, 0.0) >= STAGE_RISE for g in sp):
                out.append({"i": i, "z": zp, "s": sp, "ref": last["ref"]})
                seg, last = i, out[-1]
    return out


def signed(z: np.ndarray, names: list[str], members: list[str]) -> float:
    idx = [names.index(m) for m in members if m in names]
    if not idx:
        return 0.0
    j = max(idx, key=lambda k: abs(z[k]))
    return float(np.clip(z[j], -10.0, 10.0))


def label_role(i, z, ref, X, names, scale, hit_scale) -> str:
    ix = {n: k for k, n in enumerate(names)}
    zc = lambda *ms: float(np.clip(max((z[ix[m]] for m in ms), key=abs), -10.0, 10.0))  # noqa: E731
    low = zc("low_mix", "bass")
    mix, high = zc("mix"), zc("high_mix")
    bright, trans = zc("brightness"), zc("transient_mean")
    hits, kicksnare = signed(z, names, ["kick", "snare", "hat"]), signed(z, names, ["kick", "snare"])
    drum_lvl = zc("drums", "high_drums")
    nxt = lambda n: float((X[i + 1][ix[n]] - X[i][ix[n]]) / scale[ix[n]]) if i + 1 < len(X) else 0.0  # noqa: E731
    ref_hits = float(sum(ref[ix[c]] for c in DRUM_TYPES))

    if low <= -2.5 and high <= -2.0:
        return "gap" if nxt("low_mix") >= 2.0 else "break"
    if low >= 2.5 and (mix >= 1.5 or zc("bass") >= 2.5 or zc("kick") >= 1.5):
        return "drop"
    if drum_lvl >= 3.0 and nxt("drums") <= -1.0 and kicksnare < 2.0:
        return "fill"
    if hits >= 2.0 and ref_hits <= 0.35 * hit_scale:
        return "groove_in"
    if bright >= 1.5 or high >= 2.0 or trans >= 2.0:
        return "build"
    if bright <= -2.0 or high <= -2.0 or hits <= -2.0 or low <= -2.0 or drum_lvl <= -2.0:
        return "break"
    return "unknown"


def detect(bars: list[dict], texture: list[float] | None, *, threshold: float = S_THRESHOLD) -> list[dict]:
    """Step change points: [{i, bar, beat_index, time_s, end_s, role, score, active, z, ...}] in time order."""
    X, names = channel_matrix(bars, texture)
    X, wins = merge_short(X, names, bars)
    scale = channel_scales(X, names)
    ix = {n: k for k, n in enumerate(names)}
    hit_scale = float(np.percentile(X[:, [ix["kick"], ix["snare"], ix["hat"]]].sum(axis=1), 90))
    rows = segment_walk(X, names, DETECT_GROUPS, scale, lambda z, s: pooled(s) >= threshold, staged=True)
    points = []
    for r in rows:
        i = r["i"]
        points.append({
            "bar": wins[i]["bar"], "beat_index": wins[i]["beat_index"],
            "time_s": wins[i]["start_s"], "end_s": wins[i]["end_s"],
            "role": label_role(i, r["z"], r["ref"], X, names, scale, hit_scale),
            "score": round(pooled(r["s"]), 2),
            "active": sorted(g for g, s in r["s"].items() if s >= Z0 + 1.0),
            "irregular_bar": bool(wins[i]["irregular"] or wins[i]["merged"]),
            "z": {g: round(signed(r["z"], names, ms), 1) for g, ms in GROUPS.items() if any(m in names for m in ms)},
        })
    return points


# ======================================================== point time (beat) ==

def half_series(halves: list[dict]) -> dict[str, np.ndarray]:
    """Per half-beat signals for each detector group that has one."""
    def col(f):
        return np.array([np.nan if (v := f(h)) is None else v for h in halves], dtype=float)

    return {
        "loudness": col(lambda h: np.log((h["loud_rms"]["mix"] or 0.0) + LOG_EPS)),
        "low_band": col(lambda h: None if h["bands_mix"][0] is None else np.mean(h["bands_mix"][0:2])),
        "high_band": col(lambda h: None if h["bands_mix"][4] is None else np.mean(h["bands_mix"][4:7])),
        "brightness": col(lambda h: h["brightness"]),
        "transient_mean": col(lambda h: h["transient_mean"]),
        "hits": col(lambda h: float(h["kick"] + h["snare"] + h["hat"])),
        "kick_attacks": col(lambda h: float(h["kick_attacks"])),
    }


GROUP_SERIES = {
    "loudness": ("loudness",), "low_band": ("low_band",), "high_band": ("high_band",),
    "texture": ("brightness", "transient_mean"), "hits": ("hits", "kick_attacks"),
}


def refine_offset(series: dict[str, np.ndarray], active: list[str], p0: int) -> tuple[int, float, float]:
    """Half-beat shift (-2..+2 rows) of a step point's edge. Returns (shift, score_at_shift, score_at_edge).
    Shift 0 when no group that fired has a half-beat signal or the table is too short around `p0`."""
    names = [s for g in active for s in GROUP_SERIES.get(g, ())]
    n = len(next(iter(series.values())))
    pre = [p0 + k for k in PRE_ROWS if 0 <= p0 + k < n]
    post = [p0 + k for k in POST_ROWS if 0 <= p0 + k < n]
    if not names or len(pre) < MIN_SIDE_ROWS or len(post) < MIN_SIDE_ROWS:
        return 0, 0.0, 0.0
    chans = []
    for name in names:
        x = series[name]
        spread = float(np.nanpercentile(x, 95) - np.nanpercentile(x, 5))
        if np.isnan(x[pre]).all() or np.isnan(x[post]).all():
            continue
        a, b = float(np.nanmedian(x[pre])), float(np.nanmedian(x[post]))
        if abs(b - a) < max(MIN_STEP_SPREAD * spread, 1e-9):
            continue
        chans.append((x, a, b))
    if not chans:
        return 0, 0.0, 0.0

    def score(h: int) -> float:
        hit = tot = 0
        for x, a, b in chans:
            for r, want_post in ((h - 2, False), (h - 1, False), (h, True), (h + 1, True)):
                if not 0 <= r < n or np.isnan(x[r]):
                    continue
                tot += 1
                hit += (((x[r] - a) / (b - a)) >= 0.5) == want_post
        return hit / tot if tot else 0.0

    edge = score(p0)
    best_k, best = 0, edge
    for k in sorted(range(-MAX_HALF_SHIFT, MAX_HALF_SHIFT + 1), key=lambda k: (abs(k), k)):
        if k == 0:
            continue
        s = score(p0 + k)
        if s > best + 1e-12:
            best_k, best = k, s
    if best_k != 0 and best < edge + MOVE_MARGIN:
        return 0, edge, edge
    return best_k, best, edge


def locate(beats: list[dict], beat_index: int, shift_rows: int) -> tuple[int, int]:
    """(beat index the shifted half-beat falls in, whole-beat offset from the bar edge); half-beats floor to their beat."""
    offset = shift_rows // 2
    return min(max(beat_index + offset, 0), len(beats) - 1), offset


def build_points(bars: list[dict], halves: list[dict], texture: list[float] | None,
                 slopes: list[dict], states: list[str | None], beats: list[dict]) -> list[dict]:
    series = half_series(halves)
    bar_index = {b["beat_index"]: n for n, b in enumerate(bars)}
    sweeps = sweep_onsets(slopes, states)
    points: list[dict] = []
    steps = detect(bars, texture)
    step_bars = [bar_index[p["beat_index"]] for p in steps]
    claimed: set[int] = set()
    for p, bi in zip(steps, step_bars):
        shift, s_new, s_edge = refine_offset(series, p["active"], 2 * p["beat_index"])
        bt, offset = locate(beats, p["beat_index"], shift)
        near = next((w for w in sweeps if abs(w["i"] - bi) <= SWEEP_MERGE_BARS), None)
        if near is not None:
            claimed.add(near["i"])
        points.append({
            "time": round(float(beats[bt]["time"]), 3), "bar": beats[bt]["bar"], "beat": beats[bt]["beat"],
            "bar_edge_offset_beats": offset, "bar_edge_time": round(p["time_s"], 3),
            "role": p["role"], "source": "step", "score": p["score"], "features": p["active"], "z": p["z"],
            "sweep": None if near is None else {"direction": near["direction"], "rise_db": near["rise_db"]},
            "sweep_state": states[bi], "irregular_bar": p["irregular_bar"], "confidence": None,
        })
    for w in sweeps:
        if w["i"] in claimed:
            continue
        b = bars[w["i"]]
        bt = b["beat_index"]
        points.append({
            "time": round(float(beats[bt]["time"]), 3), "bar": beats[bt]["bar"], "beat": beats[bt]["beat"],
            "bar_edge_offset_beats": 0, "bar_edge_time": round(b["start_s"], 3),
            "role": "build" if w["direction"] == "opening" else "break", "source": "sweep",
            "score": None, "features": ["sweep"], "z": {},
            "sweep": {"direction": w["direction"], "rise_db": w["rise_db"]},
            "sweep_state": states[w["i"]], "irregular_bar": bool(b["irregular"]), "confidence": None,
        })
    points.sort(key=lambda r: (r["time"], r["source"]))
    return points


# ==================================================================== stage ==

CONFIDENCE_REASON = ("the pooled evidence score is not calibrated against any ground truth beyond two validation "
                     "songs; a sweep point has no score; an honest null, not a guess")


def _provenance(inputs: list[str]) -> dict:
    return {
        "engine": "analyzer.stages.light_changes: sequential change-point walk over the per-bar table (each bar vs the "
                  "median of the previous <= 8 bars of the current segment, per-channel robust z, groups pooled, "
                  "S = sum(clip(group max |z| - Z0, 0, ZCAP))) + sweep-ramp onsets + half-beat point time; rule-based roles",
        "inputs": inputs,
        "params": {"ref_max_bars": REF_MAX, "z0": Z0, "zcap": ZCAP, "score_threshold": S_THRESHOLD,
                   "short_window_beats": SHORT_BEATS, "hl_slope_db_per_bar": HL_SLOPE, "roll_slope_oct_per_bar": ROLL_SLOPE,
                   "min_consistency": MIN_CONS, "min_run_bars": MIN_RUN_BARS, "sweep_min_bars": SWEEP_MIN_BARS,
                   "sweep_min_rise_db": SWEEP_MIN_RISE_DB, "move_margin": MOVE_MARGIN},
    }


INPUT_FILES = ["beats.json", "loudness.json", "drum_events.json", "arrangement_state.json",
               "artifacts/essentia/fft_bands{,.<stem>}.json", "artifacts/kick_attacks/kick_attacks.json",
               "artifacts/harmonic_spectrum/half_beats.json"]


def build_light_changes(paths: SongPaths) -> dict:
    inp = load_inputs(paths)
    beats = inp["beats"]
    bars_w, halves_w = build_windows(beats)
    rows = _rows(bars_w, inp)
    slopes, states = sweep_columns(inp["spectrum"], beats, len(rows))
    for r, sl, st in zip(rows, slopes, states):
        r["sweep_slope"] = {"hl": None if sl["hl"][4][0] is None else round(sl["hl"][4][0], 4),
                            "roll": None if sl["roll"][4][0] is None else round(sl["roll"][4][0], 4)}
        r["sweep_state"] = st
    halves = [_slim_half(r) for r in _rows(halves_w, inp)]
    texture = bar_novelty(paths, [b["start_s"] for b in rows])
    points = build_points(rows, halves, texture, slopes, states, beats)

    bar_payload = {
        "schema_version": SCHEMA_VERSION, "song_name": paths.song_name,
        "generated_from": _provenance(INPUT_FILES),
        "bars": rows, "half_beats": halves,
    }
    lc_payload = {
        "schema_version": SCHEMA_VERSION, "song_name": paths.song_name,
        "generated_from": {**_provenance(INPUT_FILES + ["artifacts/light_changes/bar_features.json"]),
                           "confidence_reason": CONFIDENCE_REASON},
        "points": points,
    }
    write_json(paths.artifact("light_changes", "bar_features.json"), bar_payload)
    write_json(paths.artifact("light_changes", "light_changes.json"), lc_payload)
    return lc_payload
