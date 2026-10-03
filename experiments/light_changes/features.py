"""Cache: the texture-novelty value per bar (the only expensive input)."""
from __future__ import annotations

import json

from . import paths, texture


def load_bars(song: str) -> list[dict]:
    p = paths.bar_features_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no bar_features proposal for {song!r} — run experiments.bar_features first")
    return json.loads(p.read_text())["bars"]


def compute_and_cache(song: str) -> dict:
    bars = load_bars(song)
    starts = [b["start_s"] for b in bars]
    payload = {"song": song, "bar_starts": starts, "texture_novelty": texture.bar_novelty(song, starts)}
    out = paths.cache_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload) + "\n")
    return payload


def load_cache(song: str, bars: list[dict]) -> dict:
    p = paths.cache_path(song)
    if not p.exists():
        raise FileNotFoundError(f"no cache for {song!r} — run `run compute --song {song!r}` first")
    c = json.loads(p.read_text())
    if c["bar_starts"] != [b["start_s"] for b in bars]:
        raise ValueError(f"{song!r}: cache was computed on a different bar_features table — re-run compute")
    return c
