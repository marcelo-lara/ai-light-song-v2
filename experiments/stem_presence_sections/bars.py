"""Bar grid from `beats.json` downbeats.

Decision (per the task brief): use the pipeline's own downbeat track, not a
synthetic `bpm`-derived grid. `beats.json` bars come from allin1's downbeat
activation and already carry the corpus's real (sometimes irregular — e.g.
`Rapture - Nadia Ali` bars 26-30 run ~1.4 s instead of ~1.85 s) bar spacing;
building a second, bpm-only grid on top would silently disagree with it. A
song's beat grid is read once by `src/analyzer` per CLAUDE.md's "time in
seconds, bars 1-indexed" rule; this module just groups that same grid into
bar spans for aggregation. `downbeat_confidence` is carried through per bar,
`null` when allin1 did not score it, per the no-silent-fallback rule — never
snapped to a guessed confidence.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import paths


@dataclass(frozen=True)
class Bar:
    bar: int
    start: float
    end: float
    downbeat_confidence: float | None


def load_bar_grid(song: str) -> list[Bar]:
    """One `Bar` per downbeat-to-downbeat span, the last extended to the
    song's `info.json` duration. Fails loud (no silent fallback) if
    `beats.json` carries no downbeats at all — that is a corpus-declaration
    bug for a 4/4 song, not a skippable gap."""
    beats = json.loads(paths.beats_path(song).read_text())["beats"]
    downbeats = sorted(
        (b for b in beats if b.get("type") == "downbeat"), key=lambda b: b["time"]
    )
    if not downbeats:
        raise ValueError(f"{song!r}: beats.json has no downbeats — cannot build a bar grid")

    duration = json.loads(paths.info_path(song).read_text())["duration"]

    bars: list[Bar] = []
    for i, db in enumerate(downbeats):
        start = float(db["time"])
        end = float(downbeats[i + 1]["time"]) if i + 1 < len(downbeats) else float(duration)
        bars.append(
            Bar(
                bar=int(db["bar"]),
                start=start,
                end=end,
                downbeat_confidence=db.get("downbeat_confidence"),
            )
        )
    return bars
