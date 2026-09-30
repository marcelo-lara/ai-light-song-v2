"""Checks the "crash over-fires on bright hats/rides" bug's Done-when facts:

  Rapture - Nadia Ali: 66.23/68.07/69.92/180.69/182.53/184.38 kept (isolated
  accents, each a members of a 3-hit, ~4-beat-spaced group — well outside the
  1-2 beat stream period).

  Cinderella - Ella Lee: the two 2-beat crash streams 176-207 s and
  269-297 s mostly rejected; 222.37 kept as one accent (the rest of that same
  steady-period run rejected).
"""
from __future__ import annotations

from . import export as export_mod

RAPTURE = "Rapture - Nadia Ali"
CINDERELLA = "Cinderella - Ella Lee"

RAPTURE_ISOLATED = [66.23, 68.07, 69.92, 180.69, 182.53, 184.38]


def _verdicts(song: str) -> dict[float, str]:
    cache = export_mod.load_cache(song)
    return {row["time"]: row["verdict"] for row in cache["crashes"]}


def _nearest(verdicts: dict[float, str], target: float, tol: float = 0.05) -> str | None:
    for t, v in verdicts.items():
        if abs(t - target) <= tol:
            return v
    return None


def run() -> None:
    print(f"=== {RAPTURE} ===")
    verdicts = _verdicts(RAPTURE)
    for target in RAPTURE_ISOLATED:
        v = _nearest(verdicts, target)
        passed = v == "keep"
        print(f"  [{'PASS' if passed else 'FAIL'}] {target}s kept as isolated accent (got {v!r})")

    print(f"=== {CINDERELLA} ===")
    verdicts = _verdicts(CINDERELLA)
    for lo, hi in [(176.0, 207.0), (269.0, 297.0)]:
        in_range = {t: v for t, v in verdicts.items() if lo <= t <= hi}
        kept = [t for t, v in in_range.items() if v == "keep"]
        passed = len(kept) == 0
        print(
            f"  [{'PASS' if passed else 'FAIL'}] stream {lo}-{hi}s rejected "
            f"({len(in_range) - len(kept)}/{len(in_range)} rejected"
            + (f", kept={sorted(kept)}" if kept else "") + ")"
        )
    v = _nearest(verdicts, 222.37)
    passed = v == "keep"
    print(f"  [{'PASS' if passed else 'FAIL'}] 222.37s kept as one accent (got {v!r})")
    v2 = _nearest(verdicts, 223.33)
    passed2 = v2 == "reject"
    print(f"  [{'PASS' if passed2 else 'FAIL'}] 223.33s (next in the same run) rejected (got {v2!r})")
