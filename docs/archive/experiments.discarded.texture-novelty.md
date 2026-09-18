# Texture Novelty — self-similarity novelty over spectral features

[← archive index](experiments_archive.md)

**Archived** 2026-09-14 — ran, measured, negative. v3.4 item 6, killed on its
own kill condition (precision > 0.5 at recall ≥ 0.8): **FAIL for every
feature set**, pooled and per song. Best pooled F1 0.29 (per-stem 28-dim
band weight) against incumbents `sections.json` 0.27 / `arrangement_state`
0.21 — no feature choice lifted precision, confirming the refinement doc's
finding that the texture-change signal fires at non-boundaries as often as
at them. Two follow-ups (per-stem novelty, symbolic drum loop-lock) also
failed. Full tables: `experiments/texture_novelty/README.md`.
