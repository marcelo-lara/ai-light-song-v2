"""Checks the product-refinement v3.9 item 2 kick-check Done-when facts on
`Rapture - Nadia Ali`, sections read from the published `sections.json`
(Breakdown, Chorus, and both Drops):

  - <=5 kept kicks/min in the Breakdown (96-125.54) and Chorus (125.55-155.07)
  - >=100 kept kicks/min in both drops
"""
from __future__ import annotations

import json

from . import export as export_mod
from . import paths

SONG = "Rapture - Nadia Ali"


def _sections() -> dict[str, tuple[float, float]]:
    sections = json.loads((paths.ANALYSIS_ROOT / SONG / "sections.json").read_text())["sections"]
    by_name = {s["function"]: (s["start"], s["end"]) for s in sections}
    return {
        "Breakdown": by_name["Breakdown"],
        "Chorus": by_name["Chorus"],
        "Drop 1": [s for s in sections if s["function"] == "Drop"][0],
        "Drop 2": [s for s in sections if s["function"] == "Drop"][1],
    }


def _span(v):
    if isinstance(v, tuple):
        return v
    return v["start"], v["end"]


def run() -> None:
    cache = export_mod.load_cache(SONG)
    kicks = cache["kicks"]
    sections = _sections()
    print(f"=== {SONG} ===")
    for name, spec in sections.items():
        lo, hi = _span(spec)
        in_range = [k for k in kicks if lo <= k["time"] < hi]
        kept = [k for k in in_range if k["verdict"] == "keep"]
        mins = (hi - lo) / 60
        rate = len(kept) / mins
        if name in ("Breakdown", "Chorus"):
            passed = rate <= 5.0
            target = "<=5/min"
        else:
            passed = rate >= 100.0
            target = ">=100/min"
        print(
            f"  [{'PASS' if passed else 'FAIL'}] {name} ({lo:.2f}-{hi:.2f}s) "
            f"kept {len(kept)}/{len(in_range)} kicks = {rate:.1f}/min (target {target})"
        )
