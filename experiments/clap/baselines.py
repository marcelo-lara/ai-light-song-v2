"""The cheap classical baseline CLAP has to beat — docs/experiments.md.

Same window grid, same pooling, same metric — the only thing that changes is
what the window is described by. Two descriptors, both about twenty lines of
librosa:

* **MFCC** (20 coefficients, mean + standard deviation over the window) —
  timbre. The standard "does this sound like that" feature since the 1990s.
* **Chroma** (12 pitch classes, mean) — harmony. Two sections built on the same
  chord loop look alike here even when the arrangement differs.

If a 512-dimensional learned embedding cannot beat these at deciding whether
two sections are the same part of a song, it is not worth a GPU pass.
"""
from __future__ import annotations

import numpy as np

from .model import HOP_S, SR, WINDOW_S
from .paths import audio_path, cache_path


def baseline_cache_path(song: str):
    return cache_path(song).with_name(cache_path(song).stem + ".baseline.npz")


def compute(song: str, *, window_s: float = WINDOW_S, hop_s: float = HOP_S) -> dict:
    import librosa

    wave, _ = librosa.load(str(audio_path(song)), sr=SR, mono=True)
    wave = wave.astype(np.float32)

    win = int(window_s * SR)
    hop = int(hop_s * SR)
    starts = np.arange(0, max(1, len(wave) - win + hop), hop)
    centres = starts / SR + window_s / 2.0

    mfcc_rows, chroma_rows = [], []
    for s in starts:
        seg = wave[s:s + win]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        m = librosa.feature.mfcc(y=seg, sr=SR, n_mfcc=20)
        mfcc_rows.append(np.concatenate([m.mean(axis=1), m.std(axis=1)]))
        c = librosa.feature.chroma_cqt(y=seg, sr=SR)
        chroma_rows.append(c.mean(axis=1))

    return {
        "times": centres.astype(np.float32),
        "mfcc": np.array(mfcc_rows, dtype=np.float32),
        "chroma": np.array(chroma_rows, dtype=np.float32),
        "window_s": np.array(window_s, dtype=np.float32),
        "hop_s": np.array(hop_s, dtype=np.float32),
    }


def load(song: str, *, rebuild: bool = False) -> dict:
    path = baseline_cache_path(song)
    if rebuild or not path.exists():
        data = compute(song)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **data)
        return data
    return dict(np.load(path, allow_pickle=False))


def cached_songs(songs: list[str]) -> list[str]:
    return [song for song in songs if baseline_cache_path(song).exists()]


def standardised(matrix: np.ndarray) -> np.ndarray:
    """Per-dimension z-score, then L2-normalise, so cosine is comparable to CLAP's.

    Without the z-score the first MFCC coefficient (overall loudness) dominates
    every cosine and the baseline measures volume, not timbre — which would
    hand CLAP an easy and meaningless win.
    """
    out = matrix.astype(np.float32)
    out = (out - out.mean(axis=0, keepdims=True)) / (out.std(axis=0, keepdims=True) + 1e-8)
    return out / (np.linalg.norm(out, axis=-1, keepdims=True) + 1e-8)
