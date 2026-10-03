"""Phase-2 stage `detect-kick-attacks` (v3.12 item 32; ported from `experiments/kick_attacks`, item 29).

Writes `artifacts/kick_attacks/kick_attacks.json`: kick *attacks* read off the MIX audio
(never the drums stem, never omnizart's label). A claim, so each event carries a
numeric `confidence`. The phase-3 `light-changes` stage reads this artifact for its
`kick_attacks` / `kick_present` bar columns; phase 3 never reads audio, which is why this
measurement lives here and not there. `src/` never imports `experiments/`: this is a port.

Method. A kick is an *attack*, not a band's level:

1. `env_low`  = 5 ms RMS of the 40-120 Hz band-pass. A candidate is a local maximum of
   `rise_db` = 20 log10(peak of env_low in the next RISE_WIN_S / mean of env_low over
   [t-PRE_FAR_S, t-PRE_NEAR_S]) >= LOW_RISE_DB, at least MIN_SEP_S from the next one, with
   `peak >= LEVEL_FLOOR x` the song's own p95 of env_low (silence/noise never fires). A held
   bass note has rise ~0 dB, so it never becomes a candidate.
2. Click: `env_click` = 5 ms RMS of the 2-5 kHz band-pass; `click_db` = peak in
   [t-5 ms, t+15 ms] over the median in [t-60 ms, t-15 ms]. Needs `click_db >= CLICK_DB`;
   between CLICK_MIN_DB and CLICK_DB the pitch drop breaks the tie: the dominant frequency of
   the first 30 ms must exceed that of the next 30 ms by PITCH_DROP_RATIO.
3. Echo: a candidate weaker (low attack = peak - previous level < ECHO_WEAKER x) *and* duller (click peak <
   ECHO_WEAKER x) than an earlier non-echo candidate 40 ms - 1.5 beats before it, at an offset
   that recurs (>= ECHO_MIN_PAIRS such pairs within ECHO_TOL_S in the song), is `echo` with
   `echo_of` = the parent's time, not a kick.
4. Off-grid: a non-echo attack further than 1/4 beat from the nearest `beats.json` beat keeps
   the event with confidence x OFF_GRID_PENALTY. Inside `off_grid_spans` the grid itself is
   untrusted, so nothing is penalised there (flag `grid: "untrusted"`).

Every threshold below was set by looking at Medicine-MilkInc (bars 9-18 kick, 19-22 none) and
sanity-checking against omnizart kicks on a handful of songs: validation songs, not a held-out
set. Kick-attack recall is near zero where a hat bed hides the click (Armin, Sash, Charli-VonDutch).
Deterministic: no randomness, no timestamps.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, sosfiltfilt

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

SR = 44100
HOP = 128                      # env sampled every ~2.9 ms
LOW_BAND = (40.0, 120.0)
CLICK_BAND = (2000.0, 5000.0)
ENV_WIN_S = 0.005
RISE_WIN_S = 0.020
PRE_NEAR_S = 0.005
PRE_FAR_S = 0.040
LOW_RISE_DB = 6.0
LOW_SAT_DB = 24.0
LEVEL_FLOOR = 0.15
MIN_SEP_S = 0.060
CLICK_DB = 6.5
CLICK_MIN_DB = 4.0
CLICK_SAT_DB = 12.0
PITCH_DROP_RATIO = 1.15
ECHO_WEAKER = 0.7
ECHO_MIN_PAIRS = 3
ECHO_TOL_S = 0.012
ECHO_MIN_OFFSET_S = 0.040
ECHO_MAX_BEATS = 1.5
OFF_GRID_FRAC = 0.25
OFF_GRID_PENALTY = 0.4
EPS = 1e-9


def _band_env(y: np.ndarray, sr: int, band: tuple[float, float]) -> np.ndarray:
    sos = butter(4, list(band), btype="bandpass", fs=sr, output="sos")
    x = sosfiltfilt(sos, y)
    p = uniform_filter1d(x * x, size=max(1, int(round(ENV_WIN_S * sr))), mode="nearest")
    return np.sqrt(np.maximum(p, 0.0))[::HOP]


def _dominant_hz(seg: np.ndarray, sr: int, lo: float = 30.0, hi: float = 200.0) -> float | None:
    if len(seg) < 16 or float(np.abs(seg).max()) < EPS:
        return None
    n = 1 << 14
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), n=n))
    freqs = np.fft.rfftfreq(n, 1.0 / sr)
    m = (freqs >= lo) & (freqs <= hi)
    return float(freqs[m][int(np.argmax(spec[m]))])


def _pitch_dropped(y_low: np.ndarray, sr: int, t: float) -> bool:
    a = int(t * sr)
    w = int(0.030 * sr)
    f1 = _dominant_hz(y_low[a:a + w], sr)
    f2 = _dominant_hz(y_low[a + w:a + 2 * w], sr)
    return f1 is not None and f2 is not None and f1 >= PITCH_DROP_RATIO * f2


def candidates(y: np.ndarray, sr: int = SR) -> list[dict]:
    """Steep-rise candidates with their click and pitch evidence, before echo/grid rules."""
    fs = sr / HOP
    low = _band_env(y, sr, LOW_BAND)
    click = _band_env(y, sr, CLICK_BAND)
    if len(low) < 16 or float(low.max()) < EPS:
        return []
    near, far = int(round(PRE_NEAR_S * fs)), int(round(PRE_FAR_S * fs))
    win = max(1, int(round(RISE_WIN_S * fs)))
    n = len(low)
    cs = np.concatenate([[0.0], np.cumsum(low)])
    rise = np.full(n, -np.inf)
    pre_mean = np.zeros(n)
    post_max = np.zeros(n)
    for i in range(far, n - win):
        pre_mean[i] = (cs[i - near + 1] - cs[i - far]) / (far - near + 1)
        post_max[i] = low[i:i + win].max()
    ok = np.arange(n) >= far
    ok[n - win:] = False
    rise[ok] = 20 * np.log10((post_max[ok] + EPS) / (pre_mean[ok] + EPS))
    floor = LEVEL_FLOOR * float(np.percentile(low, 95))
    sep = max(1, int(round(MIN_SEP_S * fs)))

    # greedy peak pick on rise, strongest first, enforcing min separation
    idx = np.where((rise >= LOW_RISE_DB) & (post_max >= floor))[0]
    idx = idx[np.argsort(-rise[idx])]
    taken: list[int] = []
    blocked = np.zeros(n, dtype=bool)
    for i in idx:
        if blocked[i]:
            continue
        taken.append(int(i))
        blocked[max(0, i - sep):i + sep + 1] = True
    taken.sort()

    sos_low = butter(4, 200.0, btype="lowpass", fs=sr, output="sos")
    y_low = sosfiltfilt(sos_low, y)
    out = []
    for i in taken:
        pk = i + int(np.argmax(low[i:i + win]))
        target = pre_mean[i] + 0.25 * (post_max[i] - pre_mean[i])
        lo_i = max(0, i - int(round(0.015 * fs)))
        onset_i = next((j for j in range(lo_i, pk + 1) if low[j] >= target), pk)
        t = onset_i / fs
        c0 = max(0, int(round((t - 0.005) * fs)))
        c1 = min(n, int(round((t + 0.015) * fs)) + 1)
        b0 = max(0, int(round((t - 0.060) * fs)))
        b1 = max(b0 + 1, int(round((t - 0.015) * fs)))
        click_peak = float(click[c0:c1].max())
        click_base = float(np.median(click[b0:b1]))
        click_db = 20 * np.log10((click_peak + EPS) / (click_base + EPS))
        drop = _pitch_dropped(y_low, sr, t)
        if click_db >= CLICK_DB or (click_db >= CLICK_MIN_DB and drop):
            out.append({"time": float(t), "rise_db": float(rise[i]), "low_peak": float(post_max[i]), "low_attack": float(post_max[i] - pre_mean[i]),
                        "click_db": float(click_db), "click_peak": click_peak, "pitch_drop": bool(drop),
                        "level": float(post_max[i] / (floor / LEVEL_FLOOR + EPS))})
    return out


def mark_echoes(cands: list[dict], beat_len: float) -> None:
    """Sets `echo_of` (parent time or None) on each candidate, in place."""
    for c in cands:
        c["echo_of"] = None
    pairs: list[tuple[int, int, float]] = []  # (j, i, offset): every weaker+duller follower of an earlier attack
    for j, cj in enumerate(cands):
        for i in range(j - 1, -1, -1):
            off = cj["time"] - cands[i]["time"]
            if off > ECHO_MAX_BEATS * beat_len:
                break
            if off < ECHO_MIN_OFFSET_S:
                continue
            ci = cands[i]
            if cj["low_attack"] < ECHO_WEAKER * ci["low_attack"] and cj["click_peak"] < ECHO_WEAKER * ci["click_peak"]:
                pairs.append((j, i, off))
    offs = np.array([p[2] for p in pairs])
    for j, i, off in sorted(pairs, key=lambda p: (p[0], p[2])):
        if cands[j]["echo_of"] is None and cands[i]["echo_of"] is None \
                and int(np.sum(np.abs(offs - off) <= ECHO_TOL_S)) >= ECHO_MIN_PAIRS:
            cands[j]["echo_of"] = cands[i]["time"]


def confidence(c: dict) -> float:
    s = (0.4 * min(c["rise_db"] / LOW_SAT_DB, 1.0)
         + 0.3 * min(max(c["click_db"], 0.0) / CLICK_SAT_DB, 1.0)
         + 0.2 * (1.0 if c["pitch_drop"] else 0.0)
         + 0.1 * min(c["level"], 1.0))
    return float(min(max(s, 0.0), 1.0))


def grid_offset_frac(t: float, beat_times: np.ndarray, beat_len: float) -> float:
    k = int(np.searchsorted(beat_times, t))
    near = [abs(t - beat_times[j]) for j in (k - 1, k) if 0 <= j < len(beat_times)]
    return min(near) / beat_len


def detect(y: np.ndarray, sr: int, beat_times: np.ndarray, beat_len: float,
           off_grid: list[tuple[float, float]]) -> list[dict]:
    """Final events `{time, confidence, echo_of, on_grid, grid, ...evidence}`."""
    cands = candidates(y, sr)
    mark_echoes(cands, beat_len)
    events = []
    for c in cands:
        conf = confidence(c)
        untrusted = any(a <= c["time"] < b for a, b in off_grid)
        frac = grid_offset_frac(c["time"], beat_times, beat_len)
        on_grid = frac <= OFF_GRID_FRAC
        if c["echo_of"] is not None:
            conf = min(conf, 0.2)
        elif not on_grid and not untrusted:
            conf *= OFF_GRID_PENALTY
        events.append({
            "time": round(c["time"], 3), "confidence": round(conf, 3),
            "echo_of": None if c["echo_of"] is None else round(c["echo_of"], 3),
            "on_grid": bool(on_grid), "grid": "untrusted" if untrusted else "trusted",
            "rise_db": round(c["rise_db"], 1), "click_db": round(c["click_db"], 1),
            "pitch_drop": c["pitch_drop"],
        })
    return events


# ---------------------------------------------------------------- present --
# `kick_attacks` / `kick_present` for a window (used by the light-changes bar table).
# `kick_attacks` = non-echo events in [start, end). `kick_present` = at least `min_attacks`
# of them with confidence >= PRESENT_MIN_CONF: 2 for a bar (one hit is not a groove), 1 for a
# half-beat window; a bar under 2 beats (a grid slip) needs one per beat instead. An attack
# belongs to the window its time + ASSIGN_LEAD_S falls in (band-pass smear, tracker latency).
PRESENT_MIN_CONF = 0.25
BAR_MIN_ATTACKS = 2
HALF_MIN_ATTACKS = 1
ASSIGN_LEAD_S = 0.05


def window_counts(events: list[dict], start: float, end: float, min_attacks: int) -> tuple[int, bool]:
    kicks = [e for e in events if e["echo_of"] is None and start <= e["time"] + ASSIGN_LEAD_S < end]
    sure = sum(1 for e in kicks if e["confidence"] >= PRESENT_MIN_CONF)
    return len(kicks), sure >= min_attacks


# ------------------------------------------------------------------ stage --
STAGE_ENGINE = ("mix audio: 40-120 Hz 5 ms-RMS rise >= %.0f dB over the previous 5-40 ms with a coincident 2-5 kHz click "
                "(pitch drop as tie-break); weaker+duller repeats at a recurring offset labelled echo; "
                "attacks > 1/4 beat off beats.json kept at x%.1f confidence" % (LOW_RISE_DB, OFF_GRID_PENALTY))


def detect_kick_attacks(paths: SongPaths) -> dict:
    """Needs the mix audio and the published `beats.json`; raises when either is missing."""
    if not paths.song_path.exists():
        raise DependencyError(f"mix audio missing for kick-attack detection: {paths.song_path}")
    if not paths.beats_output_path.exists():
        raise AnalysisError("detect-kick-attacks requires the published beats.json (run build-ui-data first).")
    import librosa

    y, sr = librosa.load(str(paths.song_path), sr=SR, mono=True)
    beats = read_json(paths.beats_output_path)
    times = np.array(sorted(b["time"] for b in beats["beats"]), dtype=float)
    beat_len = float(np.median(np.diff(times)))
    off_grid = [(s["start"], s["end"]) for s in beats.get("off_grid_spans", [])]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "engine": STAGE_ENGINE,
            "inputs": ["<song>.mp3", "beats.json"],
            "params": {"low_rise_db": LOW_RISE_DB, "click_db": CLICK_DB, "click_min_db": CLICK_MIN_DB,
                       "level_floor": LEVEL_FLOOR, "echo_weaker": ECHO_WEAKER,
                       "echo_min_pairs": ECHO_MIN_PAIRS, "off_grid_frac": OFF_GRID_FRAC},
            "confidence_reason": "weighted rise/click/pitch/level evidence, not calibrated against ground truth",
        },
        "beat_len": round(beat_len, 4),
        "events": detect(y, sr, times, beat_len, off_grid),
    }
    write_json(paths.artifact("kick_attacks", "kick_attacks.json"), payload)
    return payload
