"""Structure from a learned representation: self-similarity, novelty, and a
repetition-aware segment labelling.

Two different things are wanted from a structural read and they need different
machinery:

* **boundaries** — where the arrangement changes. Foote novelty over a
  beat-synchronous self-similarity matrix.
* **identity** — which parts are *the same* part. Spectral clustering of the
  combined recurrence/path graph (McFee & Ellis), so the three choruses of a
  song get one label instead of three unrelated mood adjectives.

Identity is the half the current pipeline has no answer for, and it is the half
that lets a light show reuse a look when a section returns.
"""
from __future__ import annotations

import numpy as np

from .common import peak_pick


def normalise(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


def ssm(emb: np.ndarray) -> np.ndarray:
    e = normalise(emb.astype(np.float32))
    return e @ e.T


def checkerboard(size: int) -> np.ndarray:
    """Gaussian-tapered checkerboard kernel of side 2*size."""
    grid = np.arange(-size, size)
    xx, yy = np.meshgrid(grid, grid, indexing="ij")
    sign = np.sign(xx) * np.sign(yy)
    taper = np.exp(-(xx ** 2 + yy ** 2) / (2 * (size / 2.0) ** 2))
    kernel = sign * taper
    return kernel / np.abs(kernel).sum()


def novelty(sim: np.ndarray, size: int) -> np.ndarray:
    kernel = checkerboard(size)
    pad = np.pad(sim, size, mode="edge")
    out = np.zeros(len(sim))
    for i in range(len(sim)):
        out[i] = float((pad[i:i + 2 * size, i:i + 2 * size] * kernel).sum())
    out -= out.min()
    return out / (out.max() + 1e-9)


def multiscale_novelty(emb: np.ndarray, sizes=(4, 8, 16, 32)) -> np.ndarray:
    """Mean of normalised novelty curves over several kernel widths (in beats).

    A single width forces a choice between fine (one-bar) and coarse (16-bar)
    change; a song has both, and lighting cares about both.
    """
    sim = ssm(emb)
    return np.mean([novelty(sim, s) for s in sizes if 2 * s < len(sim)], axis=0)


def pick_boundaries(nov: np.ndarray, times: np.ndarray, *, min_gap_s: float = 6.0,
                    prominence: float = 0.06, per_minute: float = 4.0) -> np.ndarray:
    """Prominent local maxima, thinned to at most `per_minute` per minute.

    Requiring a local maximum matters: a plain "everything above a threshold,
    NMS'd" rule degenerates into a uniform grid whenever the curve spends most
    of its time above the threshold, which is what a normalised novelty curve
    does.
    """
    from scipy.signal import find_peaks

    nov = np.asarray(nov, dtype=float)
    span = float(nov.max() - nov.min())
    nov = (nov - nov.min()) / (span + 1e-9)      # so `prominence` means the same
    idx, props = find_peaks(nov, prominence=prominence)      # thing for every curve
    if len(idx) == 0:
        return np.array([])
    order = idx[np.argsort(props["prominences"])[::-1]]
    budget = int(round(per_minute * (times[-1] - times[0]) / 60.0)) or 1
    chosen: list[int] = []
    for i in order:
        if any(abs(times[i] - times[c]) < min_gap_s for c in chosen):
            continue
        chosen.append(int(i))
        if len(chosen) >= budget:
            break
    return times[sorted(chosen)]


def boundaries(emb: np.ndarray, beats: np.ndarray, *, sizes=(4, 8, 16, 32),
               **kwargs) -> tuple[np.ndarray, np.ndarray]:
    nov = multiscale_novelty(emb, sizes)
    n = min(len(nov), len(beats))
    return pick_boundaries(nov[:n], beats[:n], **kwargs), nov[:n]


def segment_labels(emb: np.ndarray, n_types: int = 5, width: int = 4) -> np.ndarray:
    """Per-beat cluster id from the Laplacian of a recurrence+path affinity."""
    import scipy.linalg
    from sklearn.cluster import KMeans

    e = normalise(emb.astype(np.float32))
    sim = e @ e.T
    n = len(sim)

    # k-nearest-neighbour recurrence, symmetrised.
    k = max(3, int(round(np.sqrt(n))))
    rec = np.zeros_like(sim)
    for i in range(n):
        order = np.argsort(sim[i])[::-1][1:k + 1]
        rec[i, order] = sim[i, order]
    rec = np.maximum(rec, rec.T)

    # local path affinity keeps neighbouring beats in the same component.
    path = np.zeros_like(sim)
    for offset in range(1, width + 1):
        idx = np.arange(n - offset)
        path[idx, idx + offset] = path[idx + offset, idx] = 1.0

    mu = rec.sum() / (rec.sum() + path.sum() + 1e-9)
    affinity = mu * path + (1 - mu) * rec

    deg = affinity.sum(1)
    inv = np.diag(1.0 / np.sqrt(deg + 1e-9))
    lap = np.eye(n) - inv @ affinity @ inv
    vals, vecs = scipy.linalg.eigh(lap)
    feats = normalise(vecs[:, 1:n_types + 1])
    return KMeans(n_clusters=n_types, n_init=10, random_state=0).fit_predict(feats)


def label_runs(labels: np.ndarray, beats: np.ndarray, *, min_beats: int = 8) -> list[tuple[float, float, int]]:
    """Contiguous runs of one cluster id, with short runs absorbed."""
    runs: list[list] = []
    start = 0
    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[start]:
            runs.append([start, i, int(labels[start])])
            start = i
    merged = True
    while merged and len(runs) > 1:
        merged = False
        for i, run in enumerate(runs):
            if run[1] - run[0] >= min_beats:
                continue
            if i == 0:
                runs[1][0] = run[0]
            elif i == len(runs) - 1:
                runs[-2][1] = run[1]
            elif runs[i - 1][1] - runs[i - 1][0] >= runs[i + 1][1] - runs[i + 1][0]:
                runs[i - 1][1] = run[1]
            else:
                runs[i + 1][0] = run[0]
            runs.pop(i)
            merged = True
            break
    tail = beats[-1] + float(np.median(np.diff(beats)))
    return [(float(beats[a]), float(beats[b]) if b < len(beats) else tail, c) for a, b, c in runs]
