"""Self-similarity novelty — the measured-baseline method (refinement item 2).

    cosine self-similarity matrix
    -> Foote checkerboard novelty kernel, 1.0 s half-window
    -> peak-pick the novelty curve into boundary times

The method config is fixed here, not swept. The kill condition is about which
*feature* feeds it, so tuning the peak-picker to chase a number would defeat the
point (docs/implementation-plan-v3.4.md item 6 / standing rules).
"""
from __future__ import annotations

import numpy as np

HOP_S = 0.05  # 50 ms frame grid
HALF_WINDOW_S = 1.0  # checkerboard kernel half-width


def ssm(features: np.ndarray) -> np.ndarray:
    """Cosine self-similarity. Rows are already L2-normalised upstream, but
    re-normalise defensively (feature set 2 concatenates an unnormalised col)."""
    n = np.linalg.norm(features, axis=1, keepdims=True)
    unit = features / np.maximum(n, 1e-12)
    return unit @ unit.T


def _checkerboard_kernel(half: int) -> np.ndarray:
    """Gaussian-tapered checkerboard kernel of size (2*half, 2*half)."""
    size = 2 * half
    g = np.arange(-half, half) + 0.5
    gx, gy = np.meshgrid(g, g)
    gauss = np.exp(-0.5 * (gx**2 + gy**2) / (half / 2.0) ** 2)
    sign = np.sign(gx) * np.sign(gy)
    return gauss * sign


def novelty_curve(features: np.ndarray) -> np.ndarray:
    half = max(2, int(round(HALF_WINDOW_S / HOP_S)))
    s = ssm(features)
    k = _checkerboard_kernel(half)
    t = len(s)
    out = np.zeros(t)
    for i in range(t):
        a, b = i - half, i + half
        if a < 0 or b > t:
            continue
        out[i] = float(np.sum(s[a:b, a:b] * k))
    # normalise to [0, 1] for a stable, feature-agnostic peak threshold
    if out.max() > out.min():
        out = (out - out.min()) / (out.max() - out.min())
    return out


def pick_boundaries(times: np.ndarray, curve: np.ndarray,
                    min_gap_s: float = 2.0, k_std: float = 1.0) -> np.ndarray:
    """Local maxima above mean + k_std*std, spaced >= min_gap_s.

    Fixed, principled defaults — not tuned per feature set or per song."""
    thr = curve.mean() + k_std * curve.std()
    gap = int(round(min_gap_s / HOP_S))
    peaks = []
    for i in range(1, len(curve) - 1):
        if curve[i] < thr:
            continue
        lo, hi = max(0, i - gap), min(len(curve), i + gap + 1)
        if curve[i] == curve[lo:hi].max() and curve[i] > curve[i - 1] and curve[i] >= curve[i + 1]:
            if not peaks or (i - peaks[-1]) >= gap:
                peaks.append(i)
    return times[np.array(peaks, dtype=int)] if peaks else np.array([])


def boundary_f1(pred: np.ndarray, ref: np.ndarray, tol: float = 1.0) -> tuple[float, float, float, int, int, int]:
    """Greedy one-to-one match at +-tol s. Returns (P, R, F1, tp, n_pred, n_ref)."""
    n_pred, n_ref = len(pred), len(ref)
    if n_ref == 0:
        return 0.0, 0.0, 0.0, 0, n_pred, 0
    used = set()
    tp = 0
    for p in pred:
        cand = [(abs(p - r), j) for j, r in enumerate(ref) if j not in used and abs(p - r) <= tol]
        if cand:
            cand.sort()
            used.add(cand[0][1])
            tp += 1
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_ref
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1, tp, n_pred, n_ref


# --- cheap baselines ---------------------------------------------------------

def rms_delta_boundaries(times: np.ndarray, mix_rms: np.ndarray, min_gap_s: float = 2.0) -> np.ndarray:
    """mix-RMS delta: |d/dt| of a lightly smoothed mix RMS, peak-picked."""
    w = 5
    kern = np.ones(w) / w
    smooth = np.convolve(mix_rms, kern, mode="same")
    d = np.abs(np.gradient(smooth))
    if d.max() > d.min():
        d = (d - d.min()) / (d.max() - d.min())
    return pick_boundaries(times, d, min_gap_s=min_gap_s)
