"""Per-bar 16-slot energy profiles per stem, on the essentia downbeat grid.

Method (refinement doc item 3):

  * bar grid  -> from `beats.json` downbeats (period only — never phase; the
    downbeat-phase weakness does not touch a repetition-period measurement).
  * per-stem envelope -> `loudness.json` 20 ms per-stem RMS (already trusted,
    exact, free — preferred over per-stem FFT per the plan).
  * collapse each bar to 16 equally-spaced slots (linear interp of the RMS
    envelope within the bar span).
  * **z-normalise per bar** so the sequence measures shape, not level. This is
    load-bearing: the raw (un-z) variant is the named cheap-baseline ablation.

`compute` re-derives everything from `data/analysis/**` and writes one
`cache/<song>.npz`; `score` / `export` read only that cache.
"""
from __future__ import annotations

import json

import numpy as np

from . import paths

SLOTS = 16
EPS = 1e-12


def _load_downbeats(song: str) -> np.ndarray:
    doc = json.loads(paths.beats_path(song).read_text())
    times = [
        float(b["time"])
        for b in doc["beats"]
        if b.get("type") == "downbeat" or b.get("beat") == 1
    ]
    return np.array(sorted(set(times)), dtype=float)


def _load_stem_env(song: str) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], str]:
    """Per-stem activity envelope, one (times, values) pair per stem.

    Primary source: `fft_bands.<stem>.json` broadband energy (mean of the 7
    per-song-normalised band levels) — this is what the refinement doc measured
    the z-normalisation finding against. Fallback where a song lacks per-stem
    FFT: `loudness.json` 20 ms per-stem RMS (the plan's documented alternative).
    """
    fft_ok = all(
        paths.fft_bands_stem_path(song, s).exists() for s in paths.STEM_IDS
    )
    times: dict[str, np.ndarray] = {}
    envs: dict[str, np.ndarray] = {}
    if fft_ok:
        for stem in paths.STEM_IDS:
            doc = json.loads(paths.fft_bands_stem_path(song, stem).read_text())
            times[stem] = np.array([f["time"] for f in doc["frames"]], dtype=float)
            envs[stem] = np.array(
                [float(np.mean(f["levels"])) for f in doc["frames"]], dtype=float
            )
        return times, envs, "fft_bands.<stem>"
    doc = json.loads(paths.loudness_path(song).read_text())
    order = doc["metadata"]["source_order"]
    t = np.array([f["time"] for f in doc["frames"]], dtype=float)
    for stem in paths.STEM_IDS:
        idx = order.index(stem)
        times[stem] = t
        envs[stem] = np.array([f["values"][idx] for f in doc["frames"]], dtype=float)
    return times, envs, "loudness.json per-stem RMS"


def _bar_profiles(t: np.ndarray, env: np.ndarray, downbeats: np.ndarray) -> np.ndarray:
    """(nbars, 16) raw slot means for one stem."""
    rows = []
    for k in range(len(downbeats) - 1):
        t0, t1 = downbeats[k], downbeats[k + 1]
        if t1 - t0 <= 0:
            continue
        pts = t0 + (np.arange(SLOTS) + 0.5) / SLOTS * (t1 - t0)
        rows.append(np.interp(pts, t, env))
    return np.array(rows, dtype=float) if rows else np.zeros((0, SLOTS))


def _znorm_rows(m: np.ndarray) -> np.ndarray:
    if m.size == 0:
        return m
    mu = m.mean(axis=1, keepdims=True)
    sd = m.std(axis=1, keepdims=True)
    return np.where(sd > EPS, (m - mu) / np.maximum(sd, EPS), 0.0)


def _blocks_for(song: str) -> list[dict]:
    """Operator blocks if hand-marked, else published sections. `source` records
    which — the regime metric only trusts the operator blocks."""
    hp = paths.hints_path(song)
    if hp.exists():
        rows = json.loads(hp.read_text())["human_hints"]
        return [
            {
                "start_s": float(h["start_time"]),
                "end_s": float(h["end_time"]),
                "title": str(h.get("title", "")),
                "source": "human_hints",
            }
            for h in rows
            if h.get("end_time") is not None
        ]
    doc = json.loads(paths.sections_path(song).read_text())
    return [
        {
            "start_s": float(s["start"]),
            "end_s": float(s["end"]),
            "title": str(s.get("label", "")),
            "source": "sections",
        }
        for s in doc["sections"]
    ]


def compute_and_cache(song: str) -> dict:
    downbeats = _load_downbeats(song)
    times, envs, env_source = _load_stem_env(song)

    payload: dict[str, np.ndarray] = {
        "downbeats": downbeats,
        "envelope_source": np.array([env_source], dtype=object),
    }
    raw_sum = None
    for stem in paths.STEM_IDS:
        raw = _bar_profiles(times[stem], envs[stem], downbeats)
        payload[f"raw_{stem}"] = raw
        payload[f"z_{stem}"] = _znorm_rows(raw)
        raw_sum = raw if raw_sum is None else raw_sum + raw
    # composite = all four stems summed then re-z per bar — the regime carrier.
    payload["z_composite"] = _znorm_rows(raw_sum if raw_sum is not None else np.zeros((0, SLOTS)))
    payload["raw_composite"] = raw_sum if raw_sum is not None else np.zeros((0, SLOTS))

    blocks = _blocks_for(song)
    payload["block_starts"] = np.array([b["start_s"] for b in blocks], dtype=float)
    payload["block_ends"] = np.array([b["end_s"] for b in blocks], dtype=float)
    payload["block_titles"] = np.array([b["title"] for b in blocks], dtype=object)
    payload["block_source"] = np.array(
        [b["source"] for b in blocks] or ["none"], dtype=object
    )

    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    np.savez(paths.cache_path(song), **payload)
    return payload


def load_cache(song: str) -> dict:
    data = np.load(paths.cache_path(song), allow_pickle=True)
    return {k: data[k] for k in data.files}
