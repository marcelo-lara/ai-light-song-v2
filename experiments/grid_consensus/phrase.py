"""Phrase grid: 8- or 16-bar boundaries anchored on the resolved downbeat
phase, with the phrase length picked by which one better explains section and
gesture-impact boundaries (the same musical-evidence approach as the bar
phase, one level up)."""
from __future__ import annotations

import numpy as np


def _bars(essentia_beats: list[dict], winning_phase: int) -> list[dict]:
    """Re-bar the essentia sequence using the resolved phase: beat index i is
    a downbeat iff i % 4 == winning_phase."""
    bars = []
    bar_num = 0
    for i, b in enumerate(essentia_beats):
        if i % 4 == winning_phase:
            bar_num += 1
        bars.append({"time": b["time"], "bar": bar_num, "beat_index": i})
    return bars


def derive_phrase_grid(essentia_beats: list[dict], winning_phase: int, evidence_times: list[float]) -> dict:
    bars = _bars(essentia_beats, winning_phase)
    if not bars:
        return {"phrase_length_bars": None, "boundaries": [], "confidence": 0.0}

    bar_start_time = {}
    for row in bars:
        bar_start_time.setdefault(row["bar"], row["time"])
    max_bar = max(bar_start_time)

    def score_length(n: int) -> float:
        boundaries = [bar_start_time[b] for b in range(1, max_bar + 1, n) if b in bar_start_time]
        if not boundaries or not evidence_times:
            return 0.0
        hits = sum(1 for e in evidence_times if any(abs(e - t) <= 1.0 for t in boundaries))
        return hits / len(evidence_times)

    scores = {n: score_length(n) for n in (8, 16)}
    best_n = max(scores, key=scores.get) if any(scores.values()) else 8
    boundaries = [
        {"bar": b, "time": round(bar_start_time[b], 3), "confidence": round(min(1.0, 0.3 + scores[best_n]), 3)}
        for b in range(1, max_bar + 1, best_n) if b in bar_start_time
    ]
    return {
        "phrase_length_bars": best_n,
        "boundaries": boundaries,
        "length_scores": scores,
        "confidence": round(min(1.0, 0.3 + scores.get(best_n, 0.0)), 3),
    }
