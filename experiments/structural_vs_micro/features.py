"""Per-song cache: the bar grid, the operator blocks, and the boundary set the
phrase grid is fit against.

`compute` re-derives everything from `data/analysis/**` — including items 6 and
7's `reference/proposals/{texture_novelty,phrase_periodicity}.json` (READ, never
imported) — and writes one `cache/<song>.npz`. `score` / `export` read only that
cache, so the tables reproduce on a checkout with no `data/`.
"""
from __future__ import annotations

import json

import numpy as np

from . import paths

_MERGE_TOL_S = 0.5


def _load_downbeats(song: str) -> np.ndarray:
    doc = json.loads(paths.beats_path(song).read_text())
    times = [
        float(b["time"])
        for b in doc["beats"]
        if b.get("type") == "downbeat" or b.get("beat") == 1
    ]
    return np.array(sorted(set(times)), dtype=float)


def _operator_blocks(song: str) -> list[dict]:
    """Hand-marked hints if present, else published sections. `source` records
    which — the per-kind metric only trusts the operator blocks."""
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
            if h.get("end_time") is not None and float(h["end_time"]) > float(h["start_time"])
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


def _proposal_edges(path) -> list[float]:
    if not path.exists():
        return []
    doc = json.loads(path.read_text())
    out: list[float] = []
    for b in doc.get("blocks", []):
        out.append(float(b["start_s"]))
        out.append(float(b["end_s"]))
    return out


def _merge_edges(raw: list[float], tol: float = _MERGE_TOL_S) -> np.ndarray:
    xs = sorted(x for x in raw if x > 0.0)
    out: list[float] = []
    for x in xs:
        if not out or x - out[-1] > tol:
            out.append(x)
        else:
            out[-1] = (out[-1] + x) / 2.0
    return np.array(out, dtype=float)


def compute_and_cache(song: str) -> dict:
    downbeats = _load_downbeats(song)
    blocks = _operator_blocks(song)

    # boundary set the 4-bar grid phase is fit against: the union of items 6 and
    # 7's proposal edges (the "combination" of the two parent lanes). Falls back
    # to the operator block edges where a parent file is absent (Queen of Kings
    # has no texture_novelty.json — item 6 ran on the 4 gold songs only).
    union = _proposal_edges(paths.texture_novelty_path(song))
    union += _proposal_edges(paths.phrase_periodicity_path(song))
    if not union:
        for b in blocks:
            union += [b["start_s"], b["end_s"]]
    boundary_set = _merge_edges(union)

    payload: dict[str, np.ndarray] = {
        "downbeats": downbeats,
        "boundary_set": boundary_set,
        "block_starts": np.array([b["start_s"] for b in blocks], dtype=float),
        "block_ends": np.array([b["end_s"] for b in blocks], dtype=float),
        "block_titles": np.array([b["title"] for b in blocks], dtype=object),
        "block_source": np.array([blocks[0]["source"] if blocks else "none"], dtype=object),
    }
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    np.savez(paths.cache_path(song), **payload)
    return payload


def load_cache(song: str) -> dict:
    data = np.load(paths.cache_path(song), allow_pickle=True)
    return {k: data[k] for k in data.files}
