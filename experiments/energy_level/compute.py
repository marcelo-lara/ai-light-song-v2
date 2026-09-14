"""compute — item 5/6 candidate producer: `energy` (1-5) from segment
loudness level + arrangement-state stems-playing fraction.

Method: `0.5 * mean(loudness.json mix normalized_values in span) + 0.5 *
(arrangement_state.json stems-playing fraction in span)`, song-relative
quintile-binned to 1-5 — the same raw signal as `segment_seeds.features.
compute_seed`'s `energy` rule (item 4's seed writer), but computed here as a
*candidate* with a per-row confidence: the quintile-bin margin
(`rhythm_energy_common.quintile_with_margin` — distance from the nearest bin
boundary, never a constant).

No silent fallbacks: if a song has no `loudness.json` or no segment spans,
`compute` returns an empty list rather than a guessed row.
"""
from __future__ import annotations

import json

from experiments.rhythm_energy_common import quintile_with_margin
from experiments.segment_seeds import features as seed_features
from experiments.segment_seeds import paths as seed_paths

from . import paths


def compute(song: str) -> list[dict]:
    loudness = seed_features.load_json(paths.loudness_path(song))
    arrangement = seed_features.load_json(paths.arrangement_state_path(song))
    spans = paths.spans(song)
    if not spans or loudness is None:
        return []

    mix_idx = seed_features.source_index(loudness, "mix")
    total_stems = len(seed_paths.STEM_IDS)

    raw: list[float] = []
    evidence: list[dict] = []
    for span in spans:
        start, end = span["start"], span["end"]
        mix_mean = seed_features.mean_in_span(loudness, mix_idx, start, end)
        stems_frac = seed_features.stems_playing_fraction(arrangement, start, end, total_stems)
        raw.append(0.5 * mix_mean + 0.5 * stems_frac)
        evidence.append({"mix_mean": round(mix_mean, 4), "stems_fraction": round(stems_frac, 4)})

    binned = quintile_with_margin(raw)
    rows: list[dict] = []
    for span, (bin_val, conf), ev in zip(spans, binned, evidence):
        rows.append({
            "start_s": round(span["start"], 3),
            "end_s": round(span["end"], 3),
            "energy": int(bin_val),
            "confidence": conf,
            "evidence": ev,
        })
    return rows


def compute_and_cache(song: str) -> list[dict]:
    rows = compute(song)
    path = paths.cache_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def load_cache(song: str) -> list[dict]:
    path = paths.cache_path(song)
    if not path.exists():
        return compute_and_cache(song)
    return json.loads(path.read_text())
