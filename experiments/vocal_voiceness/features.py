"""Three DSP cues over the vocal stem: vibrato, portamento, sibilance.

No model. `vibrato`/`portamento` reuse `experiments/vocal_phrases`'s cached
pYIN f0 track (same algorithm, same hop — falls back to computing it fresh via
`vocal_phrases.detector.compute_envelope` when no cache file exists yet, so
this experiment has no hard dependency on that one's `cache/` being
populated). `sibilance` reads the published, trusted
`artifacts/essentia/fft_bands.vocals.json` — no new FFT.

Output grid: `fft_bands.vocals.json`'s own 50 ms frame grid (`FRAME_INTERVAL_S`)
— chosen as canonical because sibilance is read directly off that file, and it
matches `voiceness_common.schema.VoicenessFrame`'s default `interval_ms=50`.
The f0 track (pYIN, ~11.6 ms hop @ 44100 Hz / 512-sample hop) is read into a
sliding window centred on each 50 ms grid point, not point-sampled — vibrato
and portamento are properties of a short window, not an instant.

**None of the three cues, or the thresholds below, are fit against ground
truth.** Item 1's `type: "vocal"` hints are empty on every song in this
environment (same finding as item 3's `demucs_ablation`). Vibrato/portamento
bands are the general vibrato-acoustics literature's typical singing range
(vibrato ~4-7 Hz / tens-to-~150 cents extent; portamento glides on the order
of 100s of ms), not corpus-tuned. `score.py` reports this honestly rather than
implying a validated threshold.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import numpy as np

from . import paths

FRAME_INTERVAL_S = 0.05  # matches fft_bands.vocals.json's 50ms grid

# -- vibrato ------------------------------------------------------------
VIBRATO_WINDOW_S = 0.40          # centred window used to measure one vibrato frame
VIBRATO_DETREND_S = 0.15         # moving-average window subtracted to remove pitch bends
VIBRATO_MIN_VOICED_FRACTION = 0.7  # below this, not enough pitch evidence in the window
VIBRATO_DEPTH_RANGE_CENTS = (15.0, 150.0)   # target extent; ramps 10 cents outside each edge
VIBRATO_DEPTH_RAMP_CENTS = 10.0
VIBRATO_RATE_RANGE_HZ = (3.0, 8.0)          # target rate; ramps 1 Hz outside each edge
VIBRATO_RATE_RAMP_HZ = 1.0

# -- portamento -----------------------------------------------------------
PORTAMENTO_WINDOW_S = 0.15
PORTAMENTO_MIN_VOICED_FRACTION = 0.7
PORTAMENTO_SLOPE_RANGE_CENTS_S = (200.0, 2000.0)  # a continuous glide, not a held tone or a jump
PORTAMENTO_SLOPE_RAMP_CENTS_S = 150.0

# -- sibilance ------------------------------------------------------------
# fft_bands.vocals.json band ids, in order: sub, bass, low_mid, mid,
# upper_mid, presence (2.5-6kHz), brilliance (6-16kHz). The published split
# doesn't land exactly on 4/10kHz -- presence+brilliance is the documented
# proxy for "4-10kHz consonant burst" rather than a new FFT off vocals.wav.
SIBILANCE_BAND_IDS = ("presence", "brilliance")
SIBILANCE_BASELINE_WEIGHT = 0.4   # score at zero transient_strength (pure brightness)
SIBILANCE_BURST_WEIGHT = 0.6      # additional score unlocked by a burst-like onset


def _triangular(x: np.ndarray, lo: float, hi: float, ramp: float) -> np.ndarray:
    """1.0 inside [lo, hi], linear ramp to 0.0 over `ramp` outside each edge."""
    out = np.zeros_like(x, dtype=float)
    out = np.where((x >= lo) & (x <= hi), 1.0, out)
    left = (x >= lo - ramp) & (x < lo)
    out = np.where(left, (x - (lo - ramp)) / ramp, out)
    right = (x > hi) & (x <= hi + ramp)
    out = np.where(right, ((hi + ramp) - x) / ramp, out)
    return np.clip(out, 0.0, 1.0)


@dataclass
class VoicenessFeatures:
    song: str
    times: list[float]
    vibrato: list[float]
    portamento: list[float]
    sibilance: list[float]
    #: honest per-frame flags: was there enough pitch evidence in the window
    #: to compute vibrato/portamento at all (vs. a silent/unpitched frame,
    #: which is scored 0.0, not "no data").
    vibrato_has_evidence: list[bool]
    portamento_has_evidence: list[bool]


def _load_f0_track(song: str) -> tuple[np.ndarray, np.ndarray]:
    """pYIN f0 track, reused from `vocal_phrases`'s cache when present, else
    computed fresh via its own `compute_envelope` (never written back to that
    experiment's cache — this experiment stays independently deletable)."""
    from experiments.vocal_phrases import paths as vp_paths
    from experiments.vocal_phrases import detector as vp_detector

    cache_file = vp_paths.cache_path(song)
    if cache_file.exists():
        raw = json.loads(cache_file.read_text())
        times = np.array(raw["times"], dtype=float)
        f0 = np.array(raw["f0_hz"], dtype=float)
        return times, f0

    env = vp_detector.compute_envelope(song)
    return np.array(env.times, dtype=float), np.array(env.f0_hz, dtype=float)


def _output_grid(song: str) -> np.ndarray:
    doc = json.loads(paths.fft_bands_vocals_path(song).read_text())
    return np.array([f["time"] for f in doc["frames"]], dtype=float)


def _vibrato_frame(f0_win: np.ndarray, t_win: np.ndarray) -> tuple[float, bool]:
    voiced = f0_win > 0
    if len(f0_win) == 0 or voiced.mean() < VIBRATO_MIN_VOICED_FRACTION:
        return 0.0, False

    ref = float(np.median(f0_win[voiced]))
    if ref <= 0:
        return 0.0, False
    cents = 1200.0 * np.log2(np.where(voiced, f0_win, ref) / ref)

    # detrend: subtract a short moving average to remove the underlying pitch
    # bend/glide, leaving only the fast vibrato oscillation.
    n = len(cents)
    dt = float(np.median(np.diff(t_win))) if n > 1 else 0.0116
    win_n = max(1, int(round(VIBRATO_DETREND_S / dt)))
    if win_n % 2 == 0:
        win_n += 1
    if win_n >= n:
        trend = np.full(n, cents.mean())
    else:
        kernel = np.ones(win_n) / win_n
        trend = np.convolve(cents, kernel, mode="same")
    residual = cents - trend

    depth = float(np.std(residual))
    depth_score = _triangular(
        np.array([depth]), *VIBRATO_DEPTH_RANGE_CENTS, VIBRATO_DEPTH_RAMP_CENTS
    )[0]
    if depth_score <= 0.0:
        return 0.0, True

    zero_crossings = int(np.sum(np.diff(np.sign(residual)) != 0))
    duration = t_win[-1] - t_win[0] if n > 1 else VIBRATO_WINDOW_S
    rate_hz = zero_crossings / (2.0 * duration) if duration > 0 else 0.0
    rate_score = _triangular(
        np.array([rate_hz]), *VIBRATO_RATE_RANGE_HZ, VIBRATO_RATE_RAMP_HZ
    )[0]

    return float(np.clip(depth_score * rate_score, 0.0, 1.0)), True


def _portamento_frame(f0_win: np.ndarray, t_win: np.ndarray) -> tuple[float, bool]:
    voiced = f0_win > 0
    if len(f0_win) < 3 or voiced.mean() < PORTAMENTO_MIN_VOICED_FRACTION:
        return 0.0, False

    idx = np.where(voiced)[0]
    t = t_win[idx]
    f = f0_win[idx]
    ref = float(f[0])
    if ref <= 0:
        return 0.0, False
    cents = 1200.0 * np.log2(f / ref)

    # linear fit: slope (cents/s) + goodness of fit (a real glide is smooth;
    # a stepped/quantised reading of a discrete instrument's note changes
    # fits a line poorly across the step).
    if len(t) < 2 or np.ptp(t) <= 0:
        return 0.0, True
    slope, intercept = np.polyfit(t, cents, 1)
    fitted = slope * t + intercept
    ss_res = float(np.sum((cents - fitted) ** 2))
    ss_tot = float(np.sum((cents - cents.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 1.0
    r2 = float(np.clip(r2, 0.0, 1.0))

    slope_score = _triangular(
        np.array([abs(slope)]), *PORTAMENTO_SLOPE_RANGE_CENTS_S, PORTAMENTO_SLOPE_RAMP_CENTS_S
    )[0]
    return float(np.clip(slope_score * r2, 0.0, 1.0)), True


def compute_vibrato_portamento(song: str, grid: np.ndarray) -> tuple[list[float], list[bool], list[float], list[bool]]:
    times, f0 = _load_f0_track(song)
    vibrato: list[float] = []
    vibrato_evidence: list[bool] = []
    portamento: list[float] = []
    portamento_evidence: list[bool] = []

    if len(times) == 0:
        n = len(grid)
        return [0.0] * n, [False] * n, [0.0] * n, [False] * n

    half_v = VIBRATO_WINDOW_S / 2.0
    half_p = PORTAMENTO_WINDOW_S / 2.0
    for t in grid:
        vi = np.searchsorted(times, t - half_v)
        vj = np.searchsorted(times, t + half_v)
        v_score, v_ev = _vibrato_frame(f0[vi:vj], times[vi:vj])
        vibrato.append(v_score)
        vibrato_evidence.append(v_ev)

        pi = np.searchsorted(times, t - half_p)
        pj = np.searchsorted(times, t + half_p)
        p_score, p_ev = _portamento_frame(f0[pi:pj], times[pi:pj])
        portamento.append(p_score)
        portamento_evidence.append(p_ev)

    return vibrato, vibrato_evidence, portamento, portamento_evidence


def compute_sibilance(song: str, grid: np.ndarray) -> list[float]:
    doc = json.loads(paths.fft_bands_vocals_path(song).read_text())
    band_ids = [b["id"] for b in doc["bands"]]
    idxs = [band_ids.index(b) for b in SIBILANCE_BAND_IDS if b in band_ids]
    frames = doc["frames"]
    out: list[float] = []
    fi = 0
    n = len(frames)
    for t in grid:
        while fi + 1 < n and abs(frames[fi + 1]["time"] - t) <= abs(frames[fi]["time"] - t):
            fi += 1
        f = frames[fi]
        levels = f["levels"]
        spectral = float(np.mean([levels[i] for i in idxs])) if idxs else 0.0
        spectral = float(np.clip(spectral, 0.0, 1.0))
        transient = float(np.clip(f.get("transient_strength", 0.0), 0.0, 1.0))
        score = spectral * (SIBILANCE_BASELINE_WEIGHT + SIBILANCE_BURST_WEIGHT * transient)
        out.append(float(np.clip(score, 0.0, 1.0)))
    return out


def compute_features(song: str) -> VoicenessFeatures:
    grid = _output_grid(song)
    vibrato, vibrato_ev, portamento, portamento_ev = compute_vibrato_portamento(song, grid)
    sibilance = compute_sibilance(song, grid)
    return VoicenessFeatures(
        song=song,
        times=[round(float(t), 3) for t in grid],
        vibrato=[round(v, 4) for v in vibrato],
        portamento=[round(p, 4) for p in portamento],
        sibilance=[round(s, 4) for s in sibilance],
        vibrato_has_evidence=vibrato_ev,
        portamento_has_evidence=portamento_ev,
    )


def save_features(feat: VoicenessFeatures) -> None:
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    paths.cache_path(feat.song).write_text(json.dumps(asdict(feat)))


def load_features(song: str) -> VoicenessFeatures:
    raw = json.loads(paths.cache_path(song).read_text())
    return VoicenessFeatures(**raw)
