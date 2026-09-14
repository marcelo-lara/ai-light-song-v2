"""segment_seeds — v3.6 item 4 (refinement item 6 "Seeds first").

Infers `energy` / `tension` / `rhythm` for every segment span of a song and
writes them as *unreviewed drafts* to `reference/human/segments.seed.json`.
This is the one experiment allowed to write under `reference/human/`, and only
to the `*.seed.json` filename — it never touches the operator's own
`segments.json`.

`src/` never imports this package (docs/experiments.md sandbox rule).
"""
