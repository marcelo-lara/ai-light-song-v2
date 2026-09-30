# Vocal cadence — line timing, rests/held notes, cadence repeats, calls

[← archive index](experiments_archive.md)

**Promoted v3.9 item 1**, into `src/analyzer/stages/vocal_cadence.py` (the
`publish-vocal-cadence` phase-4 stage, top-level `vocal_cadence.json`).
Timing-only: no lyric token text survives parsing (`lyrics.py`-style
structural exclusion — only whether a token is a `<SOL>`/`<EOL>` marker or
fully parenthesised, e.g. `(hey)`, is ever read from `text`).

**12/12 on Queen of Kings' named facts** (v3.9's "Done when"): `lead_in_bars`
0 / −1 / −1 on drop1 / drop2 / final chorus; drop2 repeats drop1 at
`bar_offset` −1 (0.897 match fraction, 35/39 onsets); final chorus repeats
drop2 at offset 0 (best, 0.842, 16/19) and drop1 at −1; all 4 calls
(99.62/107.21/131.87/139.62 s) exact. Not yet a corpus metric — only Queen of
Kings carries the fact set to score against.

`lead_in_bars` is anchored on which downbeat a line *resolves on*
(`resolve_downbeat`: earliest downbeat within 80 ms of a token onset —
everything before it is the pickup), not on raw line-start distance, which
reads a same-shaped entry as different amounts and mishandles a short
Fill/Pre-Drop section sitting in front of the real boundary (Queen of Kings
drop 2: the cadence line starts at 94.88s, before the Fill section even
begins, and still counts as drop 2's lead-in).

Superseded the raw whole-line-start `lead_in_beats` metric and a
141.52 s call expectation from an earlier revision — both were wrong; the
operator corrected the call to 139.62 s and the metric to the
downbeat-anchored form above.

`experiments/vocal_cadence/` (its README carried the detailed derivation),
its `queue.toml` row and its `docs/experiments.md` entry are deleted as of
this promotion — this file, `src/analyzer/stages/vocal_cadence.py` and
`tests/test_vocal_cadence.py` are the record now.
