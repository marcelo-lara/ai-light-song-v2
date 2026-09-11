"""Item 3 (v3.5) — Demucs variant ablation.

Re-runs stem separation under three variants (`htdemucs` incumbent,
`htdemucs_ft`, `htdemucs_6s`) and reports the false-vocal rate the way the
shipped `arrangement_state` rule computes it today (stem RMS above a
per-song threshold = voiced), against each variant's own stems instead of
the production `htdemucs` stems. See `README.md` for the measured
recommendation and `docs/experiments.md`'s entry for the TLDR.

Never touches `src/analyzer/stages/stems.py` or `DEMUCS_MODEL_NAME` — the
pin stays `htdemucs` regardless of this item's outcome; a re-pin is a
separate, explicitly-asked-for decision (promotion gate,
`docs/experiments.md`).
"""
