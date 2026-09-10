"""Per-song feature matrices on the incumbent's 50 ms frame grid.

Feature sets 1 and 3 are read straight out of the published FFT-band artifacts
(`fft_bands.json` / `fft_bands.<stem>.json`) — same 44100 Hz / 4096-sample Hann
frame / 50 ms hop the analyzer's `stages/fft_bands.py` uses, so no re-derivation
of the spectrogram is needed (the approach `experiments/reactive_bands`
established). Feature set 2's chroma and the MFCC baseline are computed with
librosa on the mix at the identical hop and then snapped to the band grid.

`compute` re-derives everything from `data/analysis/**` and writes one
`cache/<song>.npz`; `score` / `export` read only that cache, so the numbers
reproduce on a checkout with no `data/` and no audio.
"""
from __future__ import annotations

import json

import numpy as np

from . import paths

SR = 44100
HOP = 2205  # 50 ms — matches src/analyzer/stages/fft_bands.py
EPS = 1e-12

# mix band index -> id: sub, bass, low_mid, mid, upper_mid, presence, brilliance
PERC_BANDS = (4, 5, 6)  # upper_mid / presence / brilliance — the percussive weight


def _load_bands(path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    doc = json.loads(path.read_text())
    frames = doc["frames"]
    times = np.array([f["time"] for f in frames], dtype=float)
    levels = np.array([f["levels"] for f in frames], dtype=float)
    transient = np.array([f.get("transient_strength", 0.0) for f in frames], dtype=float)
    return times, levels, transient


def _snap(src_times: np.ndarray, src_vals: np.ndarray, dst_times: np.ndarray) -> np.ndarray:
    """Nearest-frame resample of (Tsrc, D) onto dst_times."""
    if src_vals.ndim == 1:
        return np.interp(dst_times, src_times, src_vals)
    idx = np.clip(np.searchsorted(src_times, dst_times), 0, len(src_times) - 1)
    return src_vals[idx]


def _edges_from_hints(song: str) -> np.ndarray:
    path = paths.hints_path(song)
    if not path.exists():
        return np.array([])
    rows = json.loads(path.read_text())["human_hints"]
    raw = []
    for h in rows:
        raw.append(float(h["start_time"]))
        if h.get("end_time") is not None:
            raw.append(float(h["end_time"]))
    return _dedup_edges(raw)


def _edges_from_sections(song: str) -> np.ndarray:
    path = paths.sections_path(song)
    if not path.exists():
        return np.array([])
    doc = json.loads(path.read_text())
    raw = []
    for s in doc["sections"]:
        raw.append(float(s["start"]))
        raw.append(float(s["end"]))
    return _dedup_edges(raw)


def _edges_from_arrangement(song: str) -> np.ndarray:
    path = paths.arrangement_state_path(song)
    if not path.exists():
        return np.array([])
    doc = json.loads(path.read_text())
    raw = []
    for b in doc["blocks"]:
        raw.append(float(b["start_s"]))
        raw.append(float(b["end_s"]))
    return _dedup_edges(raw)


def _dedup_edges(raw: list[float], tol: float = 0.5, floor: float = 0.5) -> np.ndarray:
    """Collapse edges within `tol` s; drop the trivial song-start edge."""
    xs = sorted(x for x in raw if x >= floor)
    out: list[float] = []
    for x in xs:
        if not out or x - out[-1] > tol:
            out.append(x)
        else:
            out[-1] = (out[-1] + x) / 2.0
    return np.array(out)


def compute_and_cache(song: str) -> dict:
    import librosa

    b_times, mix_levels, mix_transient = _load_bands(paths.fft_bands_path(song))
    duration = float(b_times[-1]) + HOP / SR

    stems = []
    for stem in paths.STEM_IDS:
        _, lv, _ = _load_bands(paths.fft_bands_stem_path(song, stem))
        stems.append(_snap(_, lv, b_times) if len(_) != len(b_times) else lv)
    stems28 = np.hstack(stems)

    y, _sr = librosa.load(str(paths.mix_audio_path(song)), sr=SR, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP).T  # (Tc, 12)
    mfcc = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=20, hop_length=HOP).T  # (Tc, 20)
    c_times = librosa.frames_to_time(np.arange(len(chroma)), sr=SR, hop_length=HOP)
    chroma_mix = _snap(c_times, chroma, b_times)
    mfcc_mix = _snap(c_times, mfcc, b_times)

    loud = json.loads(paths.loudness_path(song).read_text())
    mix_i = loud["metadata"]["source_order"].index("mix")
    l_times = np.array([f["time"] for f in loud["frames"]], dtype=float)
    l_mix = np.array([f["values"][mix_i] for f in loud["frames"]], dtype=float)
    mix_rms = _snap(l_times, l_mix, b_times)

    payload = {
        "song": song,
        "times": b_times,
        "duration": np.array([duration]),
        "bands7_mix": mix_levels,
        "stems28": stems28,
        "chroma_mix": chroma_mix,
        "perc_weight": mix_levels[:, PERC_BANDS].mean(axis=1),
        "transient": mix_transient,
        "mfcc_mix": mfcc_mix,
        "mix_rms": mix_rms,
        "edges_hint": _edges_from_hints(song),
        "edges_sections": _edges_from_sections(song),
        "edges_arrangement": _edges_from_arrangement(song),
    }
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    np.savez(paths.cache_path(song), **{k: np.asarray(v) for k, v in payload.items() if k != "song"})
    return payload


def load_cache(song: str) -> dict:
    data = np.load(paths.cache_path(song), allow_pickle=False)
    return {k: data[k] for k in data.files}


# --- the feature-set vectors, tried IN ORDER (refinement doc item 2) -----------

def feature_matrix(cache: dict, feature_set: int) -> np.ndarray:
    """(T, D) float matrix for one of the three feature sets."""
    if feature_set == 1:
        # (1) raw 7-band MIX vector — the measured baseline.
        return _l2(cache["bands7_mix"])
    if feature_set == 2:
        # (2) chroma/HPCP on the MIX against percussive-band weight. NEVER the
        # harmonic stem (0.009 RMS at the Queen of Kings drop) — chroma here is
        # librosa chroma_cqt on the mix, not the harmonic-stem hpcp.json (D6.1).
        chroma = _l2(cache["chroma_mix"])
        w = _unit(cache["perc_weight"])[:, None]
        return np.hstack([chroma, w])
    if feature_set == 3:
        # (3) per-stem band weight — 28-dim (4 stems x 7 bands) from item 1's
        # fft_bands.<stem>.json.
        return _l2(cache["stems28"])
    raise ValueError(feature_set)


def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(n, EPS)


def _unit(x: np.ndarray) -> np.ndarray:
    s = x.std()
    return (x - x.mean()) / (s + EPS) if s > 0 else x * 0.0
