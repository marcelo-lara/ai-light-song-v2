"""Vocal-presence scorer — folded from the prior standalone vocal-presence scorer
into `truth_common` (plan v3.6 item 3) so every truth family lives under one
package. Not itself an experiment — no `compute`/`export`, no queue row, no
debugger lane. `vocal_voiceness`, `clap_voiceness`, `svd_tagger`,
`demucs_ablation` import this package directly so every candidate is scored
against the same incumbents, on the same metrics, at a matched firing budget.
See `docs/experiments.md`.
"""
