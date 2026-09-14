"""One curated-truth scorer per signal family, all reading ground truth only
from `reference/human/` (plus `reference/moises/` rows whose `confidence` is
exactly `"0.99"`) — never `artifacts/`, never a published top-level file.

Families, one module each: `structure`, `drop_stages`, `vocal_presence`
(a subpackage — port of the prior single-family vocal-presence scorer), `texture`,
`energy_tension`, `rhythm`, `vocal_rhythm`. Every experiment scores through
here so verdicts are comparable (`docs/product-refinement-v3.6.md` item 2).

Not itself an experiment — no `compute`/`export`, no queue row, no debugger
lane. `src/` never imports from `experiments/` (sandbox rule,
`docs/experiments.md`).
"""
