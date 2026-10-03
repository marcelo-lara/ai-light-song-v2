"""Light change points on the per-bar feature table (item 1), with a role each.

Detector. Channels come from `bar_features.json` bars (log stem loudness, FFT
band groups, brightness, transients, hit counts per beat-normalised bar, vocal
cover, arrangement entries, texture novelty). Walk the bars; each bar is compared
with the median of the previous 4..8 bars *of the current segment* (a point
resets the segment, so a settled new state is not re-flagged). Per channel
z = (bar - ref) / scale, scale = robust spread (1.4826 MAD) of the song's own
bar-to-bar differences, floored. Channels are pooled into groups so correlated
columns count once; a bar fires when

    S = sum over groups of clip(max |z| in group - Z0, 0, ZCAP) >= S_THRESHOLD

so one group has to be extreme or several moderately moved: loudness is one
group of eight. No fixed bar grid anywhere: a point sits wherever the features
change.

Roles are rules over the signed group deltas at the point plus the next bar
(is the change a blip, does the drum energy fall away again). They were written
against the validation songs' described behaviour (docs/product-refinement-v3.12.md),
so those two songs are not an independent test of the role rules; the
thresholds below are a-priori round numbers, not fitted.
"""
from __future__ import annotations

import numpy as np

REF_MAX = 8        # compare with up to 8 previous bars of the segment (>= 1 right after a point)
Z0 = 2.0
STAGE_RISE = 2.5   # a group must rise this much (sigmas) over the point's own score to count as a second step
ZCAP = 5.0
SHORT_BEATS = 2     # a window under this many beats is merged into the next one for detection
S_THRESHOLD = 7.0
LOG_EPS = 1e-3

# Role rules read every channel (stems included); the detector pools only mix-level channels,
# because a stem's own level moving (a fill's drum decay, a pad filtering) is not a light
# change unless the mix moves with it.
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
ONE_SIDED = ("texture_novelty",)   # novelty is a change signal already: only a rise counts
# floors on a channel's scale so a near-constant channel cannot fire on noise
SCALE_FLOOR = {"kick": 1.0, "snare": 1.0, "hat": 1.0, "vocals_cover": 0.25, "arrangement": 1.0}
ARR_Z = 3.0        # one stem entering or leaving counts as 3 z

ROLES = ("groove_in", "build", "break", "drop", "gap", "fill")


def channel_matrix(bars: list[dict], texture: list[float] | None) -> tuple[np.ndarray, list[str]]:
    """(n_bars, n_channels). Counts are scaled to a nominal bar so a 1-beat bar is not 'quiet'."""
    dur = np.array([b["end_s"] - b["start_s"] for b in bars], dtype=float)
    nominal = float(np.median(dur))
    k = nominal / np.maximum(dur, 1e-6)
    cols: dict[str, np.ndarray] = {}
    lg = lambda src: np.log(np.array([b["loud_rms"][src] or 0.0 for b in bars], dtype=float) + LOG_EPS)
    for src in ("mix", "bass", "drums", "harmonic", "vocals"):
        cols[src] = lg(src)

    def band(src, idx):
        return np.array([np.mean([b["bands"][src][i] for i in idx]) for b in bars], dtype=float)

    cols["low_mix"], cols["low_harm"], cols["low_drums"] = band("mix", (0, 1)), band("harmonic", (0, 1)), band("drums", (0, 1))
    cols["high_mix"], cols["high_harm"], cols["high_drums"] = band("mix", (4, 5, 6)), band("harmonic", (4, 5, 6)), band("drums", (4, 5, 6))
    cols["brightness"] = np.array([b["brightness"] for b in bars], dtype=float)
    cols["transient_mean"] = np.array([b["transient_mean"] for b in bars], dtype=float)
    cols["transient_std"] = np.array([b["transient_std"] for b in bars], dtype=float)
    for c in ("kick", "snare", "hat"):
        cols[c] = np.array([b[c] for b in bars], dtype=float) * k
    cols["vocals_cover"] = np.array([b["vocals_cover"] for b in bars], dtype=float)
    cols["arrangement"] = np.array([len(b["entered"]) + len(b["left"]) for b in bars], dtype=float) * ARR_Z
    if texture is not None:
        cols["texture_novelty"] = np.array(texture, dtype=float)
    names = [n for g in GROUPS.values() for n in g if n in cols]
    X = np.stack([cols[n] for n in names], axis=1)
    if np.isnan(X).any():
        raise ValueError("bar_features table has a NaN channel; refusing to guess a value")
    return X, names


def channel_scales(X: np.ndarray, names: list[str]) -> np.ndarray:
    d = np.abs(np.diff(X, axis=0))
    mad = 1.4826 * np.median(np.abs(d - np.median(d, axis=0)), axis=0)
    spread = np.percentile(X, 95, axis=0) - np.percentile(X, 5, axis=0)
    floor = np.array([max(SCALE_FLOOR.get(n, 0.0), 0.1 * s, 1e-6) for n, s in zip(names, spread)])
    # the arrangement channel is an event count, not a continuous series: its scale is one event
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
    """Merge a window under SHORT_BEATS beats into the next one (a grid slip leaves 1-beat 'bars' whose
    features are too brief to read). Rate-like channels are duration-weighted, arrangement events add.
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


def _z(X: np.ndarray, names: list[str], scale: np.ndarray, i: int, ref: np.ndarray) -> np.ndarray:
    z = (X[i] - ref) / scale
    for n in ONE_SIDED:
        if n in names:
            z[names.index(n)] = max(z[names.index(n)], 0.0)
    return z


def segment_walk(X: np.ndarray, names: list[str], groups: dict[str, list[str]], scale: np.ndarray,
                 fires, staged: bool = False) -> list[dict]:
    """Walk the bars; `fires(z, s_by_group) -> bool` decides a point. A point starts a new segment.

    `staged`: a change can arrive in steps (a fill, then the groove lands on the next bar). For the
    bar right after a point the pre-point reference is kept too: it also fires when it still differs
    from the pre-point state and some group has *escalated* by >= STAGE_RISE over what it was at the point.
    """
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
    """z of the member that moved most (its sign kept)."""
    idx = [names.index(m) for m in members if m in names]
    if not idx:
        return 0.0
    j = max(idx, key=lambda k: abs(z[k]))
    return float(np.clip(z[j], -10.0, 10.0))


def label_role(i: int, z: np.ndarray, ref: np.ndarray, X: np.ndarray, names: list[str],
               scale: np.ndarray, hit_scale: float) -> str:
    ix = {n: k for k, n in enumerate(names)}
    zc = lambda *ms: float(np.clip(max((z[ix[m]] for m in ms), key=abs), -10.0, 10.0))
    low = zc("low_mix", "bass")                       # sub/bass energy
    mix, high = zc("mix"), zc("high_mix")
    bright, trans = zc("brightness"), zc("transient_mean")
    hits, kicksnare = signed(z, names, ["kick", "snare", "hat"]), signed(z, names, ["kick", "snare"])
    drum_lvl = zc("drums", "high_drums")
    nxt = lambda n: float((X[i + 1][ix[n]] - X[i][ix[n]]) / scale[ix[n]]) if i + 1 < len(X) else 0.0
    ref_hits = float(sum(ref[ix[c]] for c in ("kick", "snare", "hat")))

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


def detect(bars: list[dict], texture: list[float] | None, *, groups: dict[str, list[str]] | None = None,
           threshold: float = S_THRESHOLD) -> list[dict]:
    """Light change points: [{bar, time_s, end_s, role, score, active, z}] in time order."""
    groups = groups or DETECT_GROUPS
    X, names = channel_matrix(bars, texture)
    X, wins = merge_short(X, names, bars)
    scale = channel_scales(X, names)
    ix = {n: k for k, n in enumerate(names)}
    hit_scale = float(np.percentile(X[:, [ix["kick"], ix["snare"], ix["hat"]]].sum(axis=1), 90))
    rows = segment_walk(X, names, groups, scale, lambda z, s: pooled(s) >= threshold, staged=True)
    points = []
    for r in rows:
        i = r["i"]
        points.append({
            "bar": wins[i]["bar"], "time_s": wins[i]["start_s"], "end_s": wins[i]["end_s"],
            "role": label_role(i, r["z"], r["ref"], X, names, scale, hit_scale),
            "score": round(pooled(r["s"]), 2),
            "active": sorted(g for g, s in r["s"].items() if s >= Z0 + 1.0),
            "irregular_bar": bool(wins[i]["irregular"] or wins[i]["merged"]),
            "z": {g: round(signed(r["z"], names, ms), 1) for g, ms in GROUPS.items() if any(m in names for m in ms)},
        })
    return points


def detect_loudness_only(bars: list[dict], z_threshold: float = 3.0) -> list[dict]:
    """Cheap baseline: same walk and reference, but only the mix loudness and a plain |z| gate."""
    X, names = channel_matrix(bars, None)
    X, wins = merge_short(X, names, bars)
    scale = channel_scales(X, names)
    mix = names.index("mix")
    rows = segment_walk(X, names, {"loudness": ["mix"]}, scale, lambda z, s: abs(z[mix]) >= z_threshold)
    return [{"bar": wins[r["i"]]["bar"], "time_s": wins[r["i"]]["start_s"], "end_s": wins[r["i"]]["end_s"]} for r in rows]
