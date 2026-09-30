"""Checks the product-refinement v3.9 item 2 Done-when facts directly
(never tunes against them — a fact that fails is reported as a fail, with
why).

  Queen of Kings - Alessandra:
    - all 7 break claps (bars 42-48 beat 3) detected as claps
    - no clap at 97.29 (the rejected machine hit)
    - no clap on the drop backbeat (beat 3 of the first Drop section)
  Gabry Ponte - Tutta L'Italia:
    - claps on beats 2 and 4, bars 20-25
    - a clap in bar 80
"""
from __future__ import annotations

import json

from . import export as export_mod
from . import paths

TOL_S = 0.05


def _clap_times(song: str) -> list[float]:
    cache = export_mod.load_cache(song)
    return [row["time"] for row in cache["candidates"] if row["is_clap"]]


def _near(times: list[float], target: float, tol: float = TOL_S) -> bool:
    return any(abs(t - target) <= tol for t in times)


def _beats(song: str) -> list[dict]:
    return json.loads((paths.ANALYSIS_ROOT / song / "beats.json").read_text())["beats"]


def score_queen_of_kings() -> list[tuple[str, bool, str]]:
    song = "Queen of Kings - Alessandra"
    claps = _clap_times(song)
    beats = _beats(song)
    break_beat3 = sorted(
        b["time"] for b in beats if b["type"] == "beat" and b["beat"] == 3 and 42 <= b["bar"] <= 48
    )
    results = []
    hits = [t for t in break_beat3 if _near(claps, t)]
    results.append((
        f"7 break claps (bars 42-48 beat 3) detected",
        len(hits) == 7 == len(break_beat3),
        f"{len(hits)}/{len(break_beat3)} matched within {TOL_S}s: grid={break_beat3}, claps={claps}",
    ))
    results.append((
        "no clap at 97.29 (rejected machine hit)",
        not _near(claps, 97.29),
        f"nearest clap: {min(claps, key=lambda t: abs(t-97.29)) if claps else None}",
    ))
    drop1_beat3 = sorted(
        b["time"] for b in beats if b["type"] == "beat" and b["beat"] == 3 and 48.72 <= b["time"] < 62.04
    )
    backbeat_hits = [t for t in drop1_beat3 if _near(claps, t)]
    results.append((
        "no clap on the drop-1 backbeat (beat 3)",
        len(backbeat_hits) == 0,
        f"backbeat grid={drop1_beat3}, false positives={backbeat_hits}",
    ))
    return results


def score_tutta_italia() -> list[tuple[str, bool, str]]:
    song = "Gabry Ponte - Tutta L'Italia"
    claps = _clap_times(song)
    beats = _beats(song)
    grid = sorted(
        b["time"] for b in beats
        if b["type"] == "beat" and b["beat"] in (2, 4) and 20 <= b["bar"] <= 25
    )
    hits = [t for t in grid if _near(claps, t)]
    results = [(
        "claps on beats 2 and 4, bars 20-25",
        len(hits) == len(grid),
        f"{len(hits)}/{len(grid)} matched: grid={grid}, claps in range="
        f"{[t for t in claps if 37 <= t <= 49]}",
    )]
    bar80 = [b["time"] for b in beats if b["bar"] == 80 and b["beat"] == 1]
    results.append((
        "a clap in bar 80",
        bool(bar80) and any(bar80[0] <= t < bar80[0] + 2.0 for t in claps),
        f"bar 80 starts {bar80}, claps nearby={[t for t in claps if bar80 and bar80[0]-1 <= t <= bar80[0]+3]}",
    ))
    return results


def run() -> None:
    print("=== Queen of Kings - Alessandra ===")
    for name, passed, detail in score_queen_of_kings():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}\n        {detail}")
    print("=== Gabry Ponte - Tutta L'Italia ===")
    for name, passed, detail in score_tutta_italia():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}\n        {detail}")
