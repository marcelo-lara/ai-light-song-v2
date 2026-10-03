"""What the next 1-2 bars do after a sweep end, from `experiments/bar_features` rows.

Reference level = mean mix RMS (`loud_rms.mix`) of the run's last two bars. A bar is a
`hole` when its mix RMS is under HOLE_RATIO of that. Bar e is the first bar after the run,
e+1 the next:

  gap    e is a hole and e+1 is not (a one-bar dropout, then the music is back)
  break  e and e+1 are both holes (the energy stays out)
  drop   e is not a hole and in e or e+1 the mix RMS reaches DROP_RATIO of the reference, or
         kick_present turns on after a run without kick
  none   none of the above: the end is followed by nothing, a suspect detection

Thresholds chosen on Armin (bar 59 mix RMS .037 vs .055 before, back to .052 at 60) and
Medicine (bar 17 .033 vs .023 and kick on).
"""
from __future__ import annotations

HOLE_RATIO = 0.75
DROP_RATIO = 1.25


def classify(bars: list[dict], run_last: int) -> str:
    e = run_last + 1
    if e >= len(bars):
        return "none"
    lo = max(0, run_last - 1)
    ref = sum(b["loud_rms"]["mix"] for b in bars[lo:run_last + 1]) / (run_last + 1 - lo)
    if not ref:
        return "none"
    after = bars[e:e + 2]
    hole = [b["loud_rms"]["mix"] / ref < HOLE_RATIO for b in after]
    if hole[0]:
        return "break" if len(hole) > 1 and hole[1] else "gap"
    kick_before = any(b["kick_present"] for b in bars[lo:run_last + 1])
    for b in after:
        if b["loud_rms"]["mix"] / ref >= DROP_RATIO or (b["kick_present"] and not kick_before):
            return "drop"
    return "none"
