"""crash keep/reject rule — the "crash over-fires on bright hats/rides" bug
(product-refinement v3.9 Bugs). A crash is an isolated accent: a decaying
broadband hit, never a member of a regular stream. Two independent gates,
both measured on `Rapture - Nadia Ali` (isolated, kept) and
`Cinderella - Ella Lee` (streams, rejected) — see README:

1. **Not a stream continuation** — `drum_hit_shape.is_stream_continuation`:
   reject if this hit is spaced from the *previous* crash-labelled hit by
   ~1 or ~2 beats (the refinement's own "steady ~1-2 beat period" definition
   of a regular stream). Memoryless by design: a run's first hit is never
   caught by this on its own (either there is no preceding hit in range, or
   the preceding gap breaks the pattern) — every hit after it that keeps
   matching the period is.
2. **Decay shape** — `drum_hit_shape.bright_decay_ratio` (400 ms window,
   2-16 kHz): must fall to `<= DECAY_MAX` of its own peak by the end of the
   window. A real crash rings and then goes quiet (isolated Rapture hits
   measure ~0.01-0.07); a hit embedded in a busy hi-hat/ride pattern never
   goes quiet because the next hit in the pattern keeps the envelope up
   (measured ~0.3-0.6 on Cinderella's rejected stream members).

Both gates must pass to keep the `crash` label. This is why
`Cinderella - Ella Lee`'s 222.37 survives as "one accent" while every other
member of the same steady-period run after it is rejected by gate 1 alone,
and why the *whole* of the two long streams this bug report names
(176-207 s, 269-297 s) are rejected: their own nominal "run-starters" also
fail gate 2 (embedded in continuous hi-hat/ride activity, no clean decay).
"""
from __future__ import annotations

from dataclasses import dataclass

DECAY_MAX = 0.15
STREAM_TOL_FRAC = 0.15  # fraction of one beat length


@dataclass(frozen=True)
class CrashFeatures:
    time: float
    is_stream_continuation: bool
    decay_ratio: float | None


def keep(features: CrashFeatures) -> bool:
    if features.is_stream_continuation:
        return False
    if features.decay_ratio is None:
        return False
    return features.decay_ratio <= DECAY_MAX
