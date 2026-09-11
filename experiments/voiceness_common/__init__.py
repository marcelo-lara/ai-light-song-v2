"""Shared voiceness scorer and proposal schema.

Not itself an experiment — no `compute`/`export`, no queue row, no debugger
lane. Items 4-7 (`vocal_voiceness`, `clap_voiceness`, `svd_tagger`,
`whisperx_vad`) import this package directly so every candidate is scored
against the same incumbents, on the same metrics, at a matched firing budget.
See `docs/implementation-plan-v3.5.md` item 2 and
`docs/product-refinement-v3.5.md` section 2.
"""
