"""`texture_novelty`'s signal, as one per-bar input.

Reuses `experiments/texture_novelty/novelty.py` unchanged (Foote checkerboard
novelty, 1.0 s half-window, cosine self-similarity) on its best-measured
feature set — the 28-dim per-stem band weight (4 stems x 7 FFT bands, 50 ms
frames). It was archived negative as a *section-boundary* detector (F1 0.29);
here it is one input to a light-change scorer, and `score.py` measures it with
and without. The per-bar value is the peak novelty within +-0.2 s of the bar start.
"""
from __future__ import annotations

import json

import numpy as np

from experiments.texture_novelty import novelty

from . import paths

NEAR_S = 0.2


def stem_matrix(song: str) -> tuple[np.ndarray, np.ndarray]:
    times = None
    cols = []
    for stem in paths.STEMS:
        d = json.loads(paths.fft_stem_path(song, stem).read_text())
        t = np.array([f["time"] for f in d["frames"]], dtype=float)
        if times is None:
            times = t
        elif len(t) != len(times):
            raise ValueError(f"{song}: stem FFT frame counts differ ({stem})")
        cols.append(np.array([f["levels"] for f in d["frames"]], dtype=np.float32))
    return times, np.hstack(cols)


def bar_novelty(song: str, bar_starts: list[float]) -> list[float]:
    times, feats = stem_matrix(song)
    curve = novelty.novelty_curve(feats)
    out = []
    for s in bar_starts:
        lo = np.searchsorted(times, s - NEAR_S, side="left")
        hi = np.searchsorted(times, s + NEAR_S, side="right")
        out.append(float(curve[lo:hi].max()) if hi > lo else 0.0)
    return out
