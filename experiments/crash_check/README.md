# Crash Check — is a `crash` label an isolated accent, or a bright-hat/ride stream?

## TLDR

**Question.** The v3.4 crash/hat brightness split over-fires: 17/23 songs
publish >15 crashes/min (up to 108/min), where a real crash is a few accents
per section (open bug, product-refinement v3.9). Can shape + regularity tell
a real crash from a steady bright pattern, per hit?

**Method.** Two joint gates on every omnizart `crash`:
1. **Not a stream continuation** — reject if spaced from the *previous*
   crash by ~1 or ~2 beats (`drum_hit_shape.is_stream_continuation`,
   `STREAM_TOL_FRAC=0.15`). Memoryless: a run's first hit is never caught by
   this alone.
2. **Decay shape** — `drum_hit_shape.bright_decay_ratio` (400 ms, 2-16 kHz)
   must fall to `<=0.15` of its own peak. A real crash rings and goes quiet;
   a hit inside a busy hat/ride pattern never does (the next hit keeps the
   envelope up).

Both constants and the two-gate design are documented in
`experiments/drum_hit_shape.py` and `verdict.py`.

**Run.**
```
docker compose run --rm app python3 -m experiments.crash_check.run compute --song "Rapture - Nadia Ali"
docker compose run --rm app python3 -m experiments.crash_check.run export  --song "Rapture - Nadia Ali"
docker compose run --rm app python3 -m experiments.crash_check.run score
```

**Results (2026-09-30).**

`Rapture - Nadia Ali` — the six isolated accents:

| time | expected | got | result |
| --- | --- | --- | --- |
| 66.23 | keep | keep | PASS |
| 68.07 | keep | keep | PASS |
| 69.92 | keep | keep | PASS |
| 180.69 | keep | keep | PASS |
| 182.53 | keep | keep | PASS |
| 184.38 | keep | **reject** | **FAIL** |

`184.38`'s decay ratio measures 0.19 — just above the 0.15 cutoff. It is a
real crash with a slightly longer resonant tail than its five siblings
(0.01-0.07); a single global threshold cannot fit both without either losing
this hit or letting more of Cinderella's stream survivors through (see
below). Not re-tuned to force this one pass, per the task's own instruction.

`Cinderella - Ella Lee`:

| fact | result |
| --- | --- |
| 222.37 kept as one accent | **PASS** |
| 223.33 (next hit, same run) rejected | **PASS** |
| stream 176-207s rejected | **partial** — 37/50 (74%) rejected, 13 survive |
| stream 269-297s rejected | **partial** — 51/56 (91%) rejected, 5 survive |

The surviving false keeps are hits whose gap to the *immediately preceding*
crash happens to fall outside the 1-2 beat tolerance (a syncopated or
double-hit moment inside an otherwise steady run breaks gate 1's
one-gap-back memory) and whose decay ratio also happens to read low in that
instant. Both facts pass on their explicit spot checks (222.37 / 223.33);
the bulk-rejection facts are a strong majority, not total. A run-level
(rather than gap-to-previous) periodicity test — flagging any hit inside a
locally dense cluster of matching-period hits, not just ones directly
adjacent to a match — would likely close this gap; out of scope for this
pass, noted for whoever picks this back up.

## Output

`reference/proposals/crash_check.json` — `crashes: [{time, verdict,
is_stream_continuation, decay_ratio}]`, one row per omnizart `crash` event.
Rendered as the **Crash Check** debugger lane (keep vs reject shown
distinctly).
