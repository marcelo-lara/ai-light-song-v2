"""Write `reference/proposals/structural_vs_micro.json` — the timeline lane input.

One block per operator hint (or published section where no hints exist), each
carrying:

  * `kind`           -> "structural" | "micro", by 4-bar phrase-grid fit;
  * `grid_fit_bars`  -> the better-locking edge's distance to the nearest
    phrase-grid line, in bars, so a reviewer sees how marginal the call was.

A proposal to audition against Human Hints, never ground truth. This is NOT a
precision filter for item 6 (see docs/experiments.md) — it is a two-class split
the pipeline currently cannot express.
"""
from __future__ import annotations

import datetime
import json

from . import features as feat_mod
from . import grid as grid_mod
from . import paths

SCHEMA_VERSION = "1.0"


def export(song: str) -> dict:
    cache = feat_mod.load_cache(song)
    db = cache["downbeats"]
    bar_len = grid_mod.bar_length(db)
    phase_s, phrase_len_s = grid_mod.fit_phrase_grid(
        cache["boundary_set"], db, paths.PHRASE_BARS
    )
    source = str(cache["block_source"][0]) if len(cache["block_source"]) else "none"

    blocks = []
    for s, e, title in zip(
        cache["block_starts"], cache["block_ends"], [str(t) for t in cache["block_titles"]]
    ):
        s, e = float(s), float(e)
        kind, fit_bars = grid_mod.classify_block(s, e, phase_s, phrase_len_s, bar_len)
        blocks.append(
            {
                "start_s": round(s, 3),
                "end_s": round(e, 3),
                "title": title,
                "kind": kind,
                "grid_fit_bars": fit_bars,
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/structural_vs_micro",
            "engine": "4-bar phrase grid fit to items 6+7 boundary edges; block kind by grid lock",
            "bar_grid": "beats.json downbeats (period only)",
            "boundary_set": "union of texture_novelty.json + phrase_periodicity.json edges",
            "block_source": source,
            "structural_max_bars": grid_mod.STRUCTURAL_MAX_BARS,
            "bar_len_s": round(bar_len, 3),
            "phrase_len_s": round(phrase_len_s, 3),
            "grid_phase_s": round(phase_s, 3),
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "blocks": blocks,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        n_struct = sum(1 for b in payload["blocks"] if b["kind"] == "structural")
        print(
            f"exported {song} — {len(payload['blocks'])} blocks "
            f"({n_struct} structural, {len(payload['blocks']) - n_struct} micro)"
        )
